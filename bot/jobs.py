from datetime import datetime, timedelta
import gc  # For explicit garbage collection
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest
from telegram.ext import ContextTypes

from .config import logger
from .db import query_db, execute_db
from .panel import VpnPanelAPI
from .utils import bytes_to_gb
from .memory_optimizer import cleanup_memory, log_memory_stats, check_memory_threshold


async def check_expirations(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running daily expiration check job...")
    log_memory_stats()  # Log initial memory state
    
    st_global = {s['key']: s['value'] for s in (query_db("SELECT key, value FROM settings WHERE key IN ('reminder_job_enabled')") or [])}
    if (st_global.get('reminder_job_enabled') or '1') != '1':
        logger.info("Reminder job disabled by settings. Skipping run.")
        return
    today_str = datetime.now().strftime('%Y-%m-%d')
    reminder_msg_data = query_db("SELECT text FROM messages WHERE message_name = 'renewal_reminder_text'", one=True)
    if not reminder_msg_data:
        logger.error("Renewal reminder message template not found in DB. Skipping job.")
        return
    reminder_msg_template = reminder_msg_data['text']

    # Process orders in batches to reduce memory usage
    BATCH_SIZE = 100
    offset = 0
    orders_map = {}
    
    while True:
        active_orders = query_db(
            "SELECT id, user_id, marzban_username, panel_id, plan_id, last_reminder_date, last_traffic_alert_date FROM orders "
            "WHERE status = 'approved' AND marzban_username IS NOT NULL AND panel_id IS NOT NULL "
            f"LIMIT {BATCH_SIZE} OFFSET {offset}"
        )
        
        if not active_orders:
            break
            
        for order in active_orders:
            if order['marzban_username'] not in orders_map:
                orders_map[order['marzban_username']] = []
            orders_map[order['marzban_username']].append(order)
        
        offset += BATCH_SIZE
        
        # Free memory for processed batch
        del active_orders

    # Deactivate expired resellers daily
    try:
        expired = query_db("SELECT user_id, expires_at FROM resellers WHERE status='active' AND expires_at IS NOT NULL AND expires_at < datetime('now')") or []
        for r in expired:
            execute_db("UPDATE resellers SET status='inactive' WHERE user_id = ?", (r['user_id'],))
            try:
                await context.bot.send_message(r['user_id'], "نمایندگی شما به دلیل اتمام مدت، غیرفعال شد.")
            except Exception:
                pass
        if expired:
            logger.info(f"Deactivated {len(expired)} expired resellers")
    except Exception as e:
        logger.error(f"Reseller expiry check failed: {e}")

    # Load alert settings once
    st = {s['key']: s['value'] for s in (query_db("SELECT key, value FROM settings WHERE key IN ('traffic_alert_enabled','traffic_alert_value_gb','time_alert_enabled','time_alert_days')") or [])}
    alert_enabled = (st.get('traffic_alert_enabled') or '0') == '1'
    try:
        alert_gb = float(st.get('traffic_alert_value_gb') or 5)
    except Exception:
        alert_gb = 5.0
    time_alert_on = (st.get('time_alert_enabled') or '1') == '1'
    try:
        time_alert_days = int(st.get('time_alert_days') or 3)
    except Exception:
        time_alert_days = 3

    all_panels = query_db("SELECT id FROM panels WHERE COALESCE(enabled,1)=1")
    for panel_data in all_panels:
        # Check memory threshold before processing each panel
        check_memory_threshold(threshold_mb=400)
        
        try:
            panel_api = VpnPanelAPI(panel_id=panel_data['id'])
            all_users, msg = await panel_api.get_all_users()

            async def _process_user_record(username: str, m_user: dict):
                if username not in orders_map:
                    return
                user_orders = orders_map[username]
                # Deletion policy: if expired > 2 days -> delete; if plan is trial -> delete immediately after expiry
                try:
                    exp_ts = int(m_user.get('expire') or 0)
                except Exception:
                    exp_ts = 0
                now_ts = int(datetime.now().timestamp())
                should_delete = False
                is_trial = False
                # Determine trial by plan duration heuristic (<= 3 days) when plan info is available
                try:
                    # Use the shortest plan among this username's orders as heuristic
                    durations = []
                    for o in user_orders:
                        if o.get('plan_id'):
                            p = query_db("SELECT duration_days, name FROM plans WHERE id = ?", (o['plan_id'],), one=True)
                            if p:
                                durations.append(int(p.get('duration_days') or 0))
                    if durations:
                        is_trial = min(durations) <= 3
                except Exception:
                    is_trial = False
                if exp_ts > 0:
                    if is_trial and exp_ts < now_ts:
                        should_delete = True
                    elif exp_ts < (now_ts - 2 * 86400):
                        should_delete = True
                # Execute deletion once per username if needed
                if should_delete:
                    # Use panel of the first order tied to this username
                    target_order = None
                    for o in user_orders:
                        if o.get('panel_id'):
                            target_order = o
                            break
                    if target_order:
                        try:
                            p_api = VpnPanelAPI(panel_id=target_order['panel_id'])
                            ok = False
                            msg_d = None
                            if hasattr(p_api, 'delete_user'):
                                try:
                                    ok, msg_d = p_api.delete_user(username)
                                except Exception as e:
                                    ok = False; msg_d = str(e)
                            if ok:
                                # Mark all matching orders as deleted
                                for o in user_orders:
                                    execute_db("UPDATE orders SET status='deleted' WHERE id = ?", (o['id'],))
                                logger.info(f"Deleted expired service {username} on panel {target_order['panel_id']}")
                                return  # stop further processing for this username
                            else:
                                logger.warning(f"Panel delete not supported or failed for {username}: {msg_d}")
                        except Exception as e:
                            logger.error(f"Deletion attempt failed for {username}: {e}")
                for order in user_orders:
                    if order['last_reminder_date'] == today_str:
                        pass
                    details_str = ""
                    # Time-based check (configurable)
                    if m_user.get('expire') and time_alert_on:
                        expire_dt = datetime.fromtimestamp(m_user['expire'])
                        days_left = (expire_dt - datetime.now()).days
                        if 0 <= days_left <= max(0, time_alert_days):
                            details_str = f"تنها **{days_left+1} روز** تا پایان اعتبار زمانی سرویس شما باقی مانده است."
                    # Usage-based check (GB remaining)
                    if not details_str and alert_enabled and m_user.get('data_limit', 0) > 0:
                        total = float(m_user.get('data_limit') or 0)
                        used = float(m_user.get('used_traffic') or 0)
                        remain = max(0.0, total - used)
                        if (remain / (1024**3)) <= alert_gb:
                            details_str = f"حجم باقی‌مانده سرویس شما کمتر از **{alert_gb} گیگابایت** شده است."
                    if details_str:
                        try:
                            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                            final_msg = reminder_msg_template.format(details=details_str)
                            kb = [
                                [InlineKeyboardButton("📦 مشاهده سرویس", callback_data=f"view_service_{order['id']}")],
                                [InlineKeyboardButton("🔁 تمدید سریع", callback_data=f"renew_service_{order['id']}")],
                                [InlineKeyboardButton("🔗 دریافت لینک مجدد", callback_data=f"refresh_service_link_{order['id']}")],
                                [InlineKeyboardButton("🔐 تغییر کلید اتصال", callback_data=f"revoke_key_{order['id']}")],
                                [InlineKeyboardButton("🕘 یادآوری فردا", callback_data=f"alert_snooze_{order['id']}")],
                            ]
                            await context.bot.send_message(order['user_id'], final_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
                            execute_db("UPDATE orders SET last_reminder_date = ? WHERE id = ?", (today_str, order['id']))
                            logger.info(f"Sent reminder to user {order['user_id']} for service {username}")
                        except (Forbidden, BadRequest):
                            logger.warning(f"Could not send reminder to blocked user {order['user_id']}")
                        except Exception as e:
                            logger.error(f"Error sending reminder to {order['user_id']}: {e}")
                        import asyncio as _asyncio
                        await _asyncio.sleep(0.5)
                    else:
                        # If only traffic alert is enabled, use a separate per-day guard (GB only)
                        if alert_enabled and m_user.get('data_limit', 0) > 0:
                            total = float(m_user.get('data_limit') or 0)
                            used = float(m_user.get('used_traffic') or 0)
                            remain = max(0.0, total - used)
                            should_alert = False
                            msg_text = None
                            if (remain / (1024**3)) <= alert_gb:
                                msg_text = f"حجم باقی‌مانده سرویس شما کمتر از **{alert_gb} گیگابایت** شده است."
                                should_alert = True
                            if should_alert and order.get('last_traffic_alert_date') != today_str:
                                try:
                                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                                    final_msg = reminder_msg_template.format(details=msg_text)
                                    kb = [
                                        [InlineKeyboardButton("📦 مشاهده سرویس", callback_data=f"view_service_{order['id']}")],
                                        [InlineKeyboardButton("🔁 تمدید سریع", callback_data=f"renew_service_{order['id']}")],
                                        [InlineKeyboardButton("🔗 دریافت لینک مجدد", callback_data=f"refresh_service_link_{order['id']}")],
                                        [InlineKeyboardButton("🔐 تغییر کلید اتصال", callback_data=f"revoke_key_{order['id']}")],
                                        [InlineKeyboardButton("🕘 یادآوری فردا", callback_data=f"alert_snooze_{order['id']}")],
                                    ]
                                    await context.bot.send_message(order['user_id'], final_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
                                    execute_db("UPDATE orders SET last_traffic_alert_date = ? WHERE id = ?", (today_str, order['id']))
                                    logger.info(f"Sent traffic alert to user {order['user_id']} for service {username}")
                                except Exception as e:
                                    logger.error(f"Error sending traffic alert to {order['user_id']}: {e}")

            if not all_users:
                # Fallback path for panels that don't support get_all_users (e.g., 3x-UI)
                logger.info(f"Panel ID {panel_data['id']} does not support get_all_users: {msg}. Falling back to per-order query.")
                # For this panel, gather usernames from orders
                panel_usernames = []
                for uname, ords in orders_map.items():
                    try:
                        if any(int(o.get('panel_id') or 0) == int(panel_data['id']) for o in ords):
                            panel_usernames.append(uname)
                    except Exception:
                        continue
                # Query each username individually
                for uname in panel_usernames:
                    try:
                        uinfo, _m = await panel_api.get_user(uname)
                        if isinstance(uinfo, dict):
                            # Normalize to expected keys
                            m_user = {
                                'username': uname,
                                'expire': uinfo.get('expire') or 0,
                                'data_limit': uinfo.get('data_limit') or 0,
                                'used_traffic': uinfo.get('used_traffic') or 0,
                            }
                            await _process_user_record(uname, m_user)
                    except Exception as e:
                        logger.warning(f"Per-user fetch failed for {uname} on panel {panel_data['id']}: {e}")
                continue

            for m_user in all_users:
                username = m_user.get('username')
                if not username:
                    continue
                await _process_user_record(username, m_user)
        except Exception as e:
            logger.error(f"Failed to process reminders for panel ID {panel_data['id']}: {e}")
        finally:
            # Cleanup memory after each panel
            if 'all_users' in locals():
                del all_users
            if 'panel_api' in locals():
                del panel_api
            gc.collect()
    
    # Final cleanup and garbage collection
    logger.info("Daily expiration check job completed. Running garbage collection...")
    orders_map.clear()
    cleanup_memory(force=True)
    log_memory_stats()  # Log final memory state


async def backup_and_send_to_admins(context: ContextTypes.DEFAULT_TYPE):
    """Create a backup archive and send it to admins periodically."""
    try:
        import tempfile, os, io, json, zipfile, shutil
        from .config import DB_NAME, ADMIN_ID
        # Create temp directory and zip file
        tmpdir = tempfile.mkdtemp()
        zip_path = os.path.join(tmpdir, 'wingsbot_backup.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
            # Include DB
            if os.path.exists(DB_NAME):
                z.write(DB_NAME, arcname=os.path.basename(DB_NAME))
            # Include .env if present at project root
            proj_root = os.path.dirname(os.path.dirname(__file__))
            env_path = os.path.join(proj_root, '.env')
            if os.path.exists(env_path):
                z.write(env_path, arcname='.env')
            # Include settings dump
            settings = query_db("SELECT key, value FROM settings") or []
            dump = json.dumps(settings, ensure_ascii=False, indent=2)
            z.writestr('settings.json', data=dump)
        # Prepare recipients: primary admin + extra admins
        admins = [ADMIN_ID] if ADMIN_ID else []
        extra = query_db("SELECT user_id FROM admins") or []
        for r in extra:
            try:
                uid = int(r.get('user_id'))
                if uid not in admins:
                    admins.append(uid)
            except Exception:
                continue
        # Send zip to each admin
        if not admins:
            logger.info("No admins found to send backup")
        else:
            with open(zip_path, 'rb') as f:
                data = f.read()
            from telegram import InputFile
            for uid in admins:
                try:
                    await context.bot.send_document(chat_id=uid, document=InputFile(io.BytesIO(data), filename='wingsbot_backup.zip'), caption='پشتیبان خودکار ربات')
                except Exception as e:
                    logger.warning(f"Could not send backup to admin {uid}: {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception as e:
        logger.error(f"backup_and_send_to_admins failed: {e}")