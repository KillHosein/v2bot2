# -*- coding: utf-8 -*-
"""Admin notification helpers for purchase logs and other events"""

from telegram import Bot
from telegram.constants import ParseMode
from ..config import ADMIN_ID, logger
from ..db import query_db


async def send_purchase_log(bot: Bot, order_id: int, user_id: int, plan_name: str, final_price: int, payment_method: str = "نامشخص"):
    """
    Send purchase notification to admin
    
    Args:
        bot: Telegram bot instance
        order_id: Order ID
        user_id: User ID who made the purchase
        plan_name: Plan name
        final_price: Final price paid
        payment_method: Payment method used
    """
    try:
        # Get user info from Telegram API
        try:
            telegram_user = await bot.get_chat(user_id)
            first_name = telegram_user.first_name or 'نامشخص'
            last_name = telegram_user.last_name or ''
            username = telegram_user.username or None
            full_name = f"{first_name} {last_name}".strip()
            user_mention = f"@{username}" if username else full_name
        except Exception:
            user_info = query_db("SELECT first_name FROM users WHERE user_id = ?", (user_id,), one=True)
            first_name = user_info.get('first_name', 'نامشخص') if user_info else 'نامشخص'
            full_name = first_name
            username = None
            user_mention = first_name
        
        # Get purchase logs chat
        settings = query_db("SELECT key, value FROM settings WHERE key IN ('purchase_logs_enabled', 'purchase_logs_chat_id')")
        settings_dict = {s['key']: s['value'] for s in settings} if settings else {}
        
        enabled = settings_dict.get('purchase_logs_enabled', '1') == '1'
        if not enabled:
            return
        
        # Determine target chat
        chat_id_raw = settings_dict.get('purchase_logs_chat_id', '').strip()
        if chat_id_raw:
            target_chat = chat_id_raw if chat_id_raw.startswith('@') else (int(chat_id_raw) if chat_id_raw.lstrip('-').isdigit() else ADMIN_ID)
        else:
            target_chat = ADMIN_ID
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Get order details  
        order_details = query_db(
            """SELECT o.*, p.duration_days, p.traffic_gb, u.first_name
               FROM orders o
               LEFT JOIN plans p ON p.id = o.plan_id
               LEFT JOIN users u ON u.user_id = o.user_id
               WHERE o.id = ?""",
            (order_id,),
            one=True
        )
        
        duration = order_details.get('duration_days', '-') if order_details else '-'
        traffic = order_details.get('traffic_gb', '-') if order_details else '-'
        panel_type = order_details.get('panel_type', 'نامشخص') if order_details else 'نامشخص'
        marzban_user = order_details.get('marzban_username', '-') if order_details else '-'
        
        text = (
            f"🛒 <b>خرید جدید</b>\n\n"
            f"👤 <b>کاربر:</b> {user_mention}\n"
            f"📝 <b>نام کامل:</b> {full_name}\n"
            f"🔖 <b>یوزرنیم تلگرام:</b> {'@' + username if username else '-'}\n"
            f"🆔 <b>یوزر آیدی:</b> <code>{user_id}</code>\n"
            f"📦 <b>پلن:</b> {plan_name}\n"
            f"⏰ <b>مدت:</b> {duration} روز\n"
            f"📊 <b>حجم:</b> {traffic} GB\n"
            f"💰 <b>مبلغ:</b> {final_price:,} تومان\n"
            f"💳 <b>روش پرداخت:</b> {payment_method}\n"
            f"🌐 <b>پنل:</b> {panel_type}\n"
            f"👨‍💻 <b>یوزرنیم سرویس:</b> <code>{marzban_user}</code>\n"
            f"🔢 <b>شماره سفارش:</b> #{order_id}\n"
            f"🕐 <b>زمان:</b> <code>{timestamp}</code>"
        )
        
        await bot.send_message(chat_id=target_chat, text=text, parse_mode=ParseMode.HTML)
        logger.info(f"Purchase log sent for order {order_id} to chat {target_chat}")
        
    except Exception as e:
        logger.error(f"Failed to send purchase log for order {order_id}: {e}", exc_info=True)
        # Fallback to admin DM with better formatting
        try:
            fallback_text = (
                f"🛒 <b>خرید جدید</b>\n\n"
                f"👤 <b>کاربر:</b> {user_mention}\n"
                f"📝 <b>نام:</b> {full_name}\n"
                f"🆔 <b>یوزر آیدی:</b> <code>{user_id}</code>\n"
                f"📦 <b>پلن:</b> {plan_name}\n"
                f"💰 <b>مبلغ:</b> {final_price:,} تومان\n"
                f"💳 <b>روش پرداخت:</b> {payment_method}\n"
                f"🔢 <b>سفارش:</b> #{order_id}"
            )
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=fallback_text,
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


async def send_renewal_log(bot: Bot, order_id: int, user_id: int, plan_name: str, final_price: int, payment_method: str = "نامشخص"):
    """
    Send renewal notification to admin
    
    Args:
        bot: Telegram bot instance
        order_id: Order ID
        user_id: User ID who renewed
        plan_name: Plan name
        final_price: Final price paid
        payment_method: Payment method used
    """
    try:
        # Get user info from Telegram API
        try:
            telegram_user = await bot.get_chat(user_id)
            first_name = telegram_user.first_name or 'نامشخص'
            last_name = telegram_user.last_name or ''
            username = telegram_user.username or None
            full_name = f"{first_name} {last_name}".strip()
            user_mention = f"@{username}" if username else full_name
        except Exception:
            user_info = query_db("SELECT first_name FROM users WHERE user_id = ?", (user_id,), one=True)
            first_name = user_info.get('first_name', 'نامشخص') if user_info else 'نامشخص'
            full_name = first_name
            username = None
            user_mention = first_name
        
        # Get purchase logs chat
        settings = query_db("SELECT key, value FROM settings WHERE key IN ('purchase_logs_enabled', 'purchase_logs_chat_id')")
        settings_dict = {s['key']: s['value'] for s in settings} if settings else {}
        
        enabled = settings_dict.get('purchase_logs_enabled', '1') == '1'
        if not enabled:
            return
        
        # Determine target chat
        chat_id_raw = settings_dict.get('purchase_logs_chat_id', '').strip()
        if chat_id_raw:
            target_chat = chat_id_raw if chat_id_raw.startswith('@') else (int(chat_id_raw) if chat_id_raw.lstrip('-').isdigit() else ADMIN_ID)
        else:
            target_chat = ADMIN_ID
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Get order details
        order_details = query_db(
            """SELECT o.*, p.duration_days, p.traffic_gb, u.first_name
               FROM orders o
               LEFT JOIN plans p ON p.id = o.plan_id
               LEFT JOIN users u ON u.user_id = o.user_id
               WHERE o.id = ?""",
            (order_id,),
            one=True
        )
        
        duration = order_details.get('duration_days', '-') if order_details else '-'
        traffic = order_details.get('traffic_gb', '-') if order_details else '-'
        panel_type = order_details.get('panel_type', 'نامشخص') if order_details else 'نامشخص'
        marzban_user = order_details.get('marzban_username', '-') if order_details else '-'
        expiry = order_details.get('expiry_date', '-') if order_details else '-'
        
        text = (
            f"🔄 <b>تمدید سرویس</b>\n\n"
            f"👤 <b>کاربر:</b> {user_mention}\n"
            f"📝 <b>نام کامل:</b> {full_name}\n"
            f"🔖 <b>یوزرنیم تلگرام:</b> {'@' + username if username else '-'}\n"
            f"🆔 <b>یوزر آیدی:</b> <code>{user_id}</code>\n"
            f"📦 <b>پلن:</b> {plan_name}\n"
            f"⏰ <b>مدت اضافه شده:</b> {duration} روز\n"
            f"📊 <b>حجم اضافه شده:</b> {traffic} GB\n"
            f"💰 <b>مبلغ:</b> {final_price:,} تومان\n"
            f"💳 <b>روش پرداخت:</b> {payment_method}\n"
            f"🌐 <b>پنل:</b> {panel_type}\n"
            f"👨‍💻 <b>یوزرنیم سرویس:</b> <code>{marzban_user}</code>\n"
            f"📅 <b>انقضای جدید:</b> {expiry}\n"
            f"🔢 <b>شماره سفارش:</b> #{order_id}\n"
            f"🕐 <b>زمان:</b> <code>{timestamp}</code>"
        )
        
        await bot.send_message(chat_id=target_chat, text=text, parse_mode=ParseMode.HTML)
        logger.info(f"Renewal log sent for order {order_id} to chat {target_chat}")
        
    except Exception as e:
        logger.error(f"Failed to send renewal log for order {order_id}: {e}", exc_info=True)
        # Fallback to admin DM with better formatting
        try:
            fallback_text = (
                f"🔄 <b>تمدید سرویس</b>\n\n"
                f"👤 <b>کاربر:</b> {user_mention}\n"
                f"📝 <b>نام:</b> {full_name}\n"
                f"🆔 <b>یوزر آیدی:</b> <code>{user_id}</code>\n"
                f"📦 <b>پلن:</b> {plan_name}\n"
                f"💰 <b>مبلغ:</b> {final_price:,} تومان\n"
                f"💳 <b>روش پرداخت:</b> {payment_method}\n"
                f"🔢 <b>سفارش:</b> #{order_id}"
            )
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=fallback_text,
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


async def send_join_log(bot: Bot, user_id: int, referrer_id: int = None):
    """
    Send new user join notification to admin
    
    Args:
        bot: Telegram bot instance
        user_id: User ID who joined
        referrer_id: User ID of referrer (optional)
    """
    try:
        # Get user info from Telegram API
        try:
            telegram_user = await bot.get_chat(user_id)
            first_name = telegram_user.first_name or 'نامشخص'
            last_name = telegram_user.last_name or ''
            username = telegram_user.username or None
            full_name = f"{first_name} {last_name}".strip()
            user_mention = f"@{username}" if username else full_name
        except Exception:
            user_info = query_db("SELECT first_name FROM users WHERE user_id = ?", (user_id,), one=True)
            first_name = user_info.get('first_name', 'نامشخص') if user_info else 'نامشخص'
            full_name = first_name
            username = None
            user_mention = first_name
        
        # Get join logs chat
        settings = query_db("SELECT key, value FROM settings WHERE key IN ('join_logs_enabled', 'join_logs_chat_id')")
        settings_dict = {s['key']: s['value'] for s in settings} if settings else {}
        
        enabled = settings_dict.get('join_logs_enabled', '1') == '1'
        if not enabled:
            return
        
        # Determine target chat
        chat_id_raw = settings_dict.get('join_logs_chat_id', '').strip()
        if chat_id_raw:
            target_chat = chat_id_raw if chat_id_raw.startswith('@') else (int(chat_id_raw) if chat_id_raw.lstrip('-').isdigit() else ADMIN_ID)
        else:
            target_chat = ADMIN_ID
        
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Get referrer info if exists
        referrer_text = ""
        if referrer_id:
            try:
                referrer_user = await bot.get_chat(referrer_id)
                ref_name = referrer_user.first_name or 'نامشخص'
                ref_username = referrer_user.username
                referrer_text = f"\n🔗 <b>معرف:</b> {ref_name} {'@' + ref_username if ref_username else ''} (<code>{referrer_id}</code>)"
            except Exception:
                referrer_text = f"\n🔗 <b>معرف:</b> ID: <code>{referrer_id}</code>"
        
        # Get total users count
        total_users = query_db("SELECT COUNT(*) as count FROM users", one=True)
        user_count = total_users['count'] if total_users else 0
        
        text = (
            f"👋 <b>کاربر جدید</b>\n\n"
            f"👤 <b>کاربر:</b> {user_mention}\n"
            f"📝 <b>نام کامل:</b> {full_name}\n"
            f"🔖 <b>یوزرنیم تلگرام:</b> {'@' + username if username else '-'}\n"
            f"🆔 <b>یوزر آیدی:</b> <code>{user_id}</code>{referrer_text}\n"
            f"👥 <b>تعداد کل کاربران:</b> {user_count:,}\n"
            f"🕐 <b>زمان عضویت:</b> <code>{timestamp}</code>"
        )
        
        await bot.send_message(chat_id=target_chat, text=text, parse_mode=ParseMode.HTML)
        logger.info(f"Join log sent for user {user_id} to chat {target_chat}")
        
    except Exception as e:
        logger.error(f"Failed to send join log for user {user_id}: {e}", exc_info=True)
