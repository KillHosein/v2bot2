"""User notification jobs for traffic and expiry warnings"""

from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from ..db import query_db, execute_db
from ..config import logger
from ..panel import VpnPanelAPI
import gc


async def check_low_traffic_and_expiry(context):
    """
    Unified job: Check for low traffic AND time-based expiry alerts.
    Grouped by panel to minimize API calls.
    """
    try:
        await check_low_traffic(context)
        await check_near_expiry(context)
    except Exception as e:
        logger.error(f"Error in check_low_traffic_and_expiry: {e}")
    finally:
        # Force garbage collection to free memory
        gc.collect()


async def check_low_traffic(context):
    """
    Check services with low traffic and notify users
    Notification at 80% and 95% usage
    Optimized: fetch all users per panel once, then lookup
    """
    try:
        logger.info("[Notification Job] Starting traffic check...")
        # Get active orders
        orders = query_db("""
            SELECT o.id, o.user_id, o.marzban_username, o.panel_id,
                   p.name as plan_name, p.traffic_gb,
                   o.notified_traffic_80, o.notified_traffic_95
            FROM orders o
            LEFT JOIN plans p ON o.plan_id = p.id
            WHERE o.status = 'approved'
            AND o.marzban_username IS NOT NULL
            AND o.panel_id IS NOT NULL
        """) or []
        
        if not orders:
            logger.info("[Notification Job] No active orders to check")
            return
        
        # Group orders by panel_id to minimize API calls
        orders_by_panel = {}
        for order in orders:
            panel_id = order['panel_id']
            if panel_id not in orders_by_panel:
                orders_by_panel[panel_id] = []
            orders_by_panel[panel_id].append(order)
        
        # For each panel, fetch all users once (or individually for 3x-UI)
        for panel_id, panel_orders in orders_by_panel.items():
            try:
                # Check panel type first
                panel_info = query_db("SELECT panel_type FROM panels WHERE id = ?", (panel_id,), one=True)
                panel_type = panel_info.get('panel_type') if panel_info else 'marzban'
                
                if panel_type == '3xui':
                    # For 3x-UI, fetch each user individually (doesn't support bulk fetch)
                    logger.info(f"[Notification Job] Processing panel {panel_id} (3x-UI) - fetching users individually...")
                    api = VpnPanelAPI(panel_id=panel_id)
                    
                    for order in panel_orders:
                        try:
                            username = order['marzban_username']
                            result = await api.get_user(username)
                            
                            # Handle both tuple (user_data, message) and dict returns
                            if isinstance(result, tuple):
                                user_data, _ = result
                            else:
                                user_data = result
                            
                            if not user_data or not isinstance(user_data, dict):
                                continue
                            
                            # Calculate usage percentage
                            used = user_data.get('used_traffic', 0) / (1024**3)  # Convert to GB
                            total = float(order['traffic_gb'] or 0)
                            
                            if total == 0:  # Unlimited traffic
                                continue
                            
                            usage_percent = (used / total) * 100
                            
                            # Check thresholds
                            if usage_percent >= 80 and not order.get('notified_traffic_80'):
                                await send_traffic_warning(
                                    context.bot, order['user_id'], order['id'],
                                    order['plan_name'], usage_percent, used, total, level='warning'
                                )
                                execute_db("UPDATE orders SET notified_traffic_80 = 1 WHERE id = ?", (order['id'],))
                            elif usage_percent >= 95 and not order.get('notified_traffic_95'):
                                await send_traffic_warning(
                                    context.bot, order['user_id'], order['id'],
                                    order['plan_name'], usage_percent, used, total, level='critical'
                                )
                                execute_db("UPDATE orders SET notified_traffic_95 = 1 WHERE id = ?", (order['id'],))
                        except Exception as e:
                            logger.error(f"Error checking traffic for 3x-UI order {order['id']}: {e}")
                            continue
                    
                    continue  # Move to next panel
                
                # For Marzban/other panels: fetch all users at once
                logger.info(f"[Notification Job] Fetching users from panel {panel_id} (using cache if available)...")
                api = VpnPanelAPI(panel_id=panel_id)
                all_users, msg = await api.get_all_users()
                
                if not all_users:
                    logger.warning(f"[Notification Job] Could not fetch users from panel {panel_id}: {msg}")
                    continue
                
                # Build lookup dict by username
                users_dict = {}
                for u in all_users:
                    username = u.get('username') or u.get('email')
                    if username:
                        users_dict[username] = u
                
                # Check each order against the fetched data
                for order in panel_orders:
                    try:
                        username = order['marzban_username']
                        user_data = users_dict.get(username)
                        
                        if not user_data:
                            continue
                        
                        # Calculate usage percentage
                        used = user_data.get('used_traffic', 0) / (1024**3)  # Convert to GB
                        total = float(order['traffic_gb'] or 0)
                        
                        if total == 0:  # Unlimited traffic
                            continue
                        
                        usage_percent = (used / total) * 100
                        
                        # Check 80% threshold
                        if usage_percent >= 80 and not order.get('notified_traffic_80'):
                            await send_traffic_warning(
                                context.bot,
                                order['user_id'],
                                order['id'],
                                order['plan_name'],
                                usage_percent,
                                used,
                                total,
                                level='warning'
                            )
                            execute_db("UPDATE orders SET notified_traffic_80 = 1 WHERE id = ?", (order['id'],))
                        
                        # Check 95% threshold
                        elif usage_percent >= 95 and not order.get('notified_traffic_95'):
                            await send_traffic_warning(
                                context.bot,
                                order['user_id'],
                                order['id'],
                                order['plan_name'],
                                usage_percent,
                                used,
                                total,
                                level='critical'
                            )
                            execute_db("UPDATE orders SET notified_traffic_95 = 1 WHERE id = ?", (order['id'],))
                        
                    except Exception as e:
                        logger.error(f"Error checking traffic for order {order['id']}: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"Error processing panel {panel_id} in traffic check: {e}")
                continue
        
        logger.info(f"[Notification Job] Traffic check completed for {len(orders)} orders")
        
    except Exception as e:
        logger.error(f"Error in check_low_traffic: {e}")


async def check_near_expiry(context):
    """
    Check services near expiry and notify users
    Notification at 3 days and 1 day before expiry
    """
    try:
        now = datetime.now()
        three_days = now + timedelta(days=3)
        one_day = now + timedelta(days=1)
        
        # Get orders expiring in 3 days
        orders_3d = query_db("""
            SELECT o.id, o.user_id, o.marzban_username,
                   p.name as plan_name, o.timestamp, p.duration_days,
                   o.notified_expiry_3d, o.notified_expiry_1d
            FROM orders o
            LEFT JOIN plans p ON o.plan_id = p.id
            WHERE o.status = 'approved'
            AND datetime(o.timestamp, '+' || p.duration_days || ' days') <= ?
            AND datetime(o.timestamp, '+' || p.duration_days || ' days') > ?
            AND o.notified_expiry_3d != 1
        """, (three_days.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S'))) or []
        
        for order in orders_3d:
            try:
                expiry = datetime.strptime(order['timestamp'], '%Y-%m-%d %H:%M:%S') + timedelta(days=order['duration_days'])
                days_left = (expiry - now).days
                
                await send_expiry_warning(
                    context.bot,
                    order['user_id'],
                    order['id'],
                    order['plan_name'],
                    days_left,
                    expiry,
                    level='warning'
                )
                execute_db("UPDATE orders SET notified_expiry_3d = 1 WHERE id = ?", (order['id'],))
                
            except Exception as e:
                logger.error(f"Error sending 3-day expiry for order {order['id']}: {e}")
        
        # Get orders expiring in 1 day
        orders_1d = query_db("""
            SELECT o.id, o.user_id, o.marzban_username,
                   p.name as plan_name, o.timestamp, p.duration_days,
                   o.notified_expiry_1d
            FROM orders o
            LEFT JOIN plans p ON o.plan_id = p.id
            WHERE o.status = 'approved'
            AND datetime(o.timestamp, '+' || p.duration_days || ' days') <= ?
            AND datetime(o.timestamp, '+' || p.duration_days || ' days') > ?
            AND o.notified_expiry_1d != 1
        """, (one_day.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S'))) or []
        
        for order in orders_1d:
            try:
                expiry = datetime.strptime(order['timestamp'], '%Y-%m-%d %H:%M:%S') + timedelta(days=order['duration_days'])
                hours_left = int((expiry - now).total_seconds() / 3600)
                
                await send_expiry_warning(
                    context.bot,
                    order['user_id'],
                    order['id'],
                    order['plan_name'],
                    0,
                    expiry,
                    level='critical',
                    hours=hours_left
                )
                execute_db("UPDATE orders SET notified_expiry_1d = 1 WHERE id = ?", (order['id'],))
                
            except Exception as e:
                logger.error(f"Error sending 1-day expiry for order {order['id']}: {e}")
        
        logger.info(f"Expiry check completed: {len(orders_3d)} 3-day, {len(orders_1d)} 1-day")
        
    except Exception as e:
        logger.error(f"Error in check_near_expiry: {e}")


async def send_traffic_warning(bot, user_id, order_id, plan_name, usage_percent, used_gb, total_gb, level='warning'):
    """Send traffic warning notification"""
    
    if level == 'warning':
        icon = "⚠️"
        title = "هشدار حجم"
        message = f"حجم سرویس شما به <b>{usage_percent:.1f}%</b> رسیده است."
    else:  # critical
        icon = "🚨"
        title = "هشدار مهم - حجم تقریباً تمام شده"
        message = f"حجم سرویس شما به <b>{usage_percent:.1f}%</b> رسیده است و به زودی تمام خواهد شد!"
    
    text = (
        f"{icon} <b>{title}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{message}\n\n"
        f"📦 <b>پلن:</b> {plan_name}\n"
        f"📊 <b>حجم مصرفی:</b> {used_gb:.2f} GB / {total_gb:.0f} GB\n"
        f"📈 <b>درصد مصرف:</b> {usage_percent:.1f}%\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>برای جلوگیری از قطعی سرویس، همین حالا تمدید کنید!</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 تمدید سرویس", callback_data=f"renew_service_{order_id}")],
        [InlineKeyboardButton("📱 سرویس‌های من", callback_data="my_services")]
    ]
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"Traffic warning sent to user {user_id}, order {order_id}")
    except Exception as e:
        logger.error(f"Failed to send traffic warning to {user_id}: {e}")


async def send_expiry_warning(bot, user_id, order_id, plan_name, days_left, expiry_date, level='warning', hours=None):
    """Send expiry warning notification"""
    
    if level == 'warning':
        icon = "⏰"
        title = "یادآوری انقضای سرویس"
        time_text = f"{days_left} روز"
    else:  # critical
        icon = "🚨"
        title = "هشدار - سرویس به زودی منقضی می‌شود"
        time_text = f"{hours} ساعت" if hours else "کمتر از ۱ روز"
    
    expiry_str = expiry_date.strftime('%Y-%m-%d %H:%M')
    
    text = (
        f"{icon} <b>{title}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>پلن:</b> {plan_name}\n"
        f"⏳ <b>زمان باقیمانده:</b> <code>{time_text}</code>\n"
        f"📅 <b>تاریخ انقضا:</b> <code>{expiry_str}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>برای ادامه استفاده، سرویس خود را تمدید کنید!</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 تمدید سرویس", callback_data=f"renew_service_{order_id}")],
        [InlineKeyboardButton("📱 سرویس‌های من", callback_data="my_services")]
    ]
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"Expiry warning sent to user {user_id}, order {order_id}")
    except Exception as e:
        logger.error(f"Failed to send expiry warning to {user_id}: {e}")
