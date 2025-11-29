from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..db import query_db, execute_db
from ..helpers.tg import safe_edit_text as _safe_edit_text
from ..states import BROADCAST_SELECT_AUDIENCE, BROADCAST_SELECT_MODE, BROADCAST_AWAIT_MESSAGE, ADMIN_MAIN_MENU
from ..states import ADMIN_STATS_MENU


async def admin_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("ارسال به همه", callback_data="broadcast_all")],
        [InlineKeyboardButton("ارسال به خریداران", callback_data="broadcast_buyers")],
        [InlineKeyboardButton("\U0001F519 بازگشت", callback_data="admin_main")],
    ]
    await _safe_edit_text(query.message, "📣 ارسال همگانی:", reply_markup=InlineKeyboardMarkup(keyboard))
    return BROADCAST_SELECT_AUDIENCE


async def admin_broadcast_ask_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    context.user_data['broadcast_audience'] = query.data.split('_')[-1]
    keyboard = [
        [InlineKeyboardButton("ارسال به صورت کپی", callback_data="broadcast_mode_copy")],
        [InlineKeyboardButton("ارسال به صورت فوروارد", callback_data="broadcast_mode_forward")],
        [InlineKeyboardButton("\U0001F519 بازگشت", callback_data="admin_main")],
    ]
    await _safe_edit_text(query.message, "لطفا نوع ارسال را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return BROADCAST_SELECT_MODE


async def admin_broadcast_set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    context.user_data['broadcast_mode'] = query.data.replace('broadcast_mode_', '')
    await _safe_edit_text(query.message, "لطفا پیام خود را برای ارسال، در قالب متن یا عکس ارسال کنید. (برای لغو /cancel را بفرستید)")
    return BROADCAST_AWAIT_MESSAGE


async def admin_broadcast_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    audience = context.user_data.get('broadcast_audience')
    mode = context.user_data.get('broadcast_mode', 'copy')
    if not audience:
        await update.message.reply_text("ابتدا مخاطب ارسال را انتخاب کنید.")
        return ADMIN_MAIN_MENU
    users = []
    if audience == 'buyers':
        users = query_db("SELECT DISTINCT user_id FROM orders WHERE status='approved'")
    else:
        users = query_db("SELECT user_id FROM users")
    sent = 0
    for u in users or []:
        uid = u['user_id']
        try:
            if mode == 'forward':
                await context.bot.forward_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            else:
                await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ ارسال انجام شد. ({sent} نفر)")
    context.user_data.pop('broadcast_audience', None)
    return ADMIN_MAIN_MENU


async def admin_stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    total_users = (query_db("SELECT COUNT(*) AS c FROM users", one=True) or {}).get('c', 0)
    buyers = (query_db("SELECT COUNT(DISTINCT user_id) AS c FROM orders WHERE status='approved'", one=True) or {}).get('c', 0)
    enabled_panels = (query_db("SELECT COUNT(*) AS c FROM panels WHERE COALESCE(enabled,1)=1", one=True) or {}).get('c', 0)
    total_services = (query_db("SELECT COUNT(*) AS c FROM orders WHERE status='approved'", one=True) or {}).get('c', 0)
    pending_orders = (query_db("SELECT COUNT(*) AS c FROM orders WHERE status='pending'", one=True) or {}).get('c', 0)
    daily_rev = (query_db(
        """
        SELECT COALESCE(SUM(CASE WHEN o.final_price IS NOT NULL THEN o.final_price ELSE p.price END),0) AS rev
        FROM orders o
        JOIN plans p ON p.id = o.plan_id
        WHERE o.status='approved' AND date(o.timestamp) = date('now','localtime')
        """,
        one=True,
    ) or {}).get('rev', 0)
    monthly_rev = (query_db(
        """
        SELECT COALESCE(SUM(CASE WHEN o.final_price IS NOT NULL THEN o.final_price ELSE p.price END),0) AS rev
        FROM orders o
        JOIN plans p ON p.id = o.plan_id
        WHERE o.status='approved' AND strftime('%Y-%m', o.timestamp) = strftime('%Y-%m', 'now','localtime')
        """,
        one=True,
    ) or {}).get('rev', 0)
    last7_rev = (query_db(
        """
        SELECT COALESCE(SUM(CASE WHEN o.final_price IS NOT NULL THEN o.final_price ELSE p.price END),0) AS rev
        FROM orders o
        JOIN plans p ON p.id = o.plan_id
        WHERE o.status='approved' AND date(o.timestamp) >= date('now','-6 day','localtime')
        """,
        one=True,
    ) or {}).get('rev', 0)

    # Payment stats
    total_payments = (query_db("SELECT COUNT(*) AS c FROM orders WHERE status='approved'", one=True) or {}).get('c', 0)
    today_payments = (query_db("SELECT COUNT(*) AS c FROM orders WHERE status='approved' AND date(timestamp) = date('now','localtime')", one=True) or {}).get('c', 0)
    
    text = (
        "📊 <b>آمار ربات</b>\n\n"
        f"👥 <b>کاربران:</b> {int(total_users):,}\n"
        f"🛒 <b>خریداران:</b> {int(buyers):,}\n"
        f"🌐 <b>پنل‌های فعال:</b> {int(enabled_panels)}\n"
        f"📱 <b>سرویس‌های فعال:</b> {int(total_services):,}\n"
        f"⏳ <b>سفارشات در انتظار:</b> {int(pending_orders):,}\n\n"
        f"💰 <b>درآمد امروز:</b> {int(daily_rev):,} تومان\n"
        f"📅 <b>درآمد 7 روز اخیر:</b> {int(last7_rev):,} تومان\n"
        f"📆 <b>درآمد این ماه:</b> {int(monthly_rev):,} تومان\n\n"
        f"💳 <b>پرداخت‌های امروز:</b> {int(today_payments):,}\n"
        f"💵 <b>کل پرداخت‌ها:</b> {int(total_payments):,}"
    )
    keyboard = [
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="stats_refresh")],
        [InlineKeyboardButton("\U0001F519 بازگشت", callback_data="admin_main")],
    ]
    # Always prefer sending a fresh message to avoid edit race conditions
    try:
        await query.message.delete()
    except Exception:
        pass
    sent_ok = False
    try:
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        sent_ok = True
    except Exception:
        sent_ok = False
    if not sent_ok:
        # Fallback: try sending directly to the admin user DM
        try:
            await context.bot.send_message(chat_id=query.from_user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
            sent_ok = True
        except Exception:
            sent_ok = False
    if not sent_ok:
        try:
            await query.answer("ارسال آمار انجام نشد.", show_alert=True)
        except Exception:
            pass
    return ADMIN_STATS_MENU


async def admin_stats_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer("در حال بروزرسانی...")
    try:
        return await admin_stats_menu(update, context)
    except Exception:
        try:
            await context.bot.send_message(chat_id=query.message.chat_id, text="بروزرسانی آمار انجام نشد. دوباره تلاش کنید.")
        except Exception:
            pass
        return ADMIN_STATS_MENU