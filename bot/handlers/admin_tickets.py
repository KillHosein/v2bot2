from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, ApplicationHandlerStop

from ..db import query_db, execute_db
from ..helpers.tg import safe_edit_text as _safe_edit_text
from ..config import ADMIN_ID
from ..states import ADMIN_MAIN_MENU, ADMIN_AWAIT_TICKET_REPLY


async def admin_tickets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    rows = query_db("SELECT id, user_id, created_at FROM tickets WHERE status = 'pending' ORDER BY id DESC LIMIT 50")
    text = "\U0001F4AC تیکت‌های پاسخ‌داده‌نشده\n\n"
    kb = []
    if not rows:
        text += "درخواستی برای بررسی وجود ندارد."
    else:
        for r in rows:
            kb.append([InlineKeyboardButton(f"#{r['id']} از {r['user_id']} - {r['created_at']}", callback_data=f"ticket_view_{r['id']}")])
    kb.append([InlineKeyboardButton("\U0001F519 بازگشت", callback_data='admin_main')])
    if update.callback_query:
        await update.callback_query.answer()
        await context.bot.send_message(chat_id=update.callback_query.message.chat_id, text=text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_MAIN_MENU


async def admin_ticket_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split('_')[-1])
    t = query_db("SELECT * FROM tickets WHERE id = ?", (ticket_id,), one=True)
    if not t:
        await query.answer("یافت نشد", show_alert=True)
        return ADMIN_MAIN_MENU
    kb = [
        [InlineKeyboardButton("✉️ پاسخ", callback_data=f"ticket_reply_{ticket_id}"), InlineKeyboardButton("🗑 حذف", callback_data=f"ticket_delete_{ticket_id}")],
        [InlineKeyboardButton("📝 پاسخ‌های آماده", callback_data=f"ticket_quick_{ticket_id}")],
        [InlineKeyboardButton("\U0001F519 بازگشت", callback_data='admin_tickets_menu')]
    ]
    if t.get('content_type') == 'photo' and t.get('file_id'):
        await context.bot.send_photo(chat_id=query.message.chat_id, photo=t['file_id'], caption=t.get('text') or '', reply_markup=InlineKeyboardMarkup(kb))
    elif t.get('content_type') == 'document' and t.get('file_id'):
        await context.bot.send_document(chat_id=query.message.chat_id, document=t['file_id'], caption=t.get('text') or '', reply_markup=InlineKeyboardMarkup(kb))
    elif t.get('content_type') == 'video' and t.get('file_id'):
        await context.bot.send_video(chat_id=query.message.chat_id, video=t['file_id'], caption=t.get('text') or '', reply_markup=InlineKeyboardMarkup(kb))
    elif t.get('content_type') == 'voice' and t.get('file_id'):
        await context.bot.send_voice(chat_id=query.message.chat_id, voice=t['file_id'], reply_markup=InlineKeyboardMarkup(kb))
    elif t.get('content_type') == 'audio' and t.get('file_id'):
        await context.bot.send_audio(chat_id=query.message.chat_id, audio=t['file_id'], caption=t.get('text') or '', reply_markup=InlineKeyboardMarkup(kb))
    else:
        await context.bot.send_message(chat_id=query.message.chat_id, text=t.get('text') or '(بدون متن)', reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_MAIN_MENU


async def admin_ticket_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split('_')[-1])
    execute_db("UPDATE tickets SET status = 'deleted' WHERE id = ?", (ticket_id,))
    await query.answer("حذف شد", show_alert=True)
    await admin_tickets_menu(update, context)
    return ADMIN_MAIN_MENU


async def admin_ticket_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split('_')[-1])
    t = query_db("SELECT user_id FROM tickets WHERE id = ?", (ticket_id,), one=True)
    if not t:
        await query.answer("یافت نشد", show_alert=True)
        return ADMIN_MAIN_MENU
    context.user_data['reply_target_user_id'] = int(t['user_id'])
    await context.bot.send_message(chat_id=query.message.chat_id, text=f"لطفاً پیام خود را برای کاربر `{t['user_id']}` ارسال کنید.", parse_mode=ParseMode.MARKDOWN)
    return ADMIN_AWAIT_TICKET_REPLY


async def admin_ticket_receive_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data.get('reply_target_user_id') is None:
        return ConversationHandler.END
    target_chat_id = int(context.user_data.get('reply_target_user_id'))
    try:
        await context.bot.copy_message(chat_id=target_chat_id, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
        await update.message.reply_text("✅ پیام برای کاربر ارسال شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ ارسال ناموفق بود: {e}")
        return ConversationHandler.END
    # log message minimal
    execute_db("INSERT INTO ticket_messages (ticket_id, sender, content_type, text, file_id, created_at) SELECT id, 'admin', CASE WHEN ? != '' THEN ? ELSE 'text' END, ?, ?, ? FROM tickets WHERE user_id = ? ORDER BY id DESC LIMIT 1",
               (update.message.photo[-1].file_id if update.message.photo else '', 'photo' if update.message.photo else 'text', update.message.caption or update.message.text or '', (update.message.document.file_id if update.message.document else None), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), target_chat_id))
    context.user_data.pop('reply_target_user_id', None)
    return ConversationHandler.END


async def admin_ticket_quick_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split('_')[-1])
    # Common quick replies
    quick = [
        ("راهنمای اتصال", "لطفاً مطابق آموزش اتصال اقدام کنید و در صورت مشکل، اسکرین‌شات خطا را ارسال نمایید."),
        ("رسید پرداخت", "لطفاً رسید/اسکرین‌شات پرداخت خود را ارسال کنید تا بررسی شود."),
        ("اطلاعات نسخه", "لطفاً نوع دستگاه، نسخه اپ و سیستم‌عامل خود را اعلام کنید."),
        ("بازنشانی کلید", "کلید اتصال شما بازنشانی می‌شود. اگر مایل هستید تایید کنید."),
    ]
    kb = []
    for code, _ in quick:
        kb.append([InlineKeyboardButton(code, callback_data=f"ticket_quick_send_{ticket_id}_{code}")])
    kb.append([InlineKeyboardButton("\U0001F519 بازگشت", callback_data=f"ticket_view_{ticket_id}")])
    await update.callback_query.message.reply_text("یک پاسخ آماده انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_MAIN_MENU


async def admin_ticket_quick_reply_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')  # ticket_quick_send_{id}_{code...}
    if len(parts) < 4:
        return ADMIN_MAIN_MENU
    ticket_id = int(parts[3])
    code = query.data.replace(f"ticket_quick_send_{ticket_id}_", "")
    t = query_db("SELECT user_id FROM tickets WHERE id = ?", (ticket_id,), one=True)
    if not t:
        await query.answer("یافت نشد", show_alert=True)
        return ADMIN_MAIN_MENU
    text_map = {
        "راهنمای اتصال": "لطفاً مطابق آموزش اتصال اقدام کنید و در صورت مشکل، اسکرین‌شات خطا را ارسال نمایید.",
        "رسید پرداخت": "لطفاً رسید/اسکرین‌شات پرداخت خود را ارسال کنید تا بررسی شود.",
        "اطلاعات نسخه": "لطفاً نوع دستگاه، نسخه اپ و سیستم‌عامل خود را اعلام کنید.",
        "بازنشانی کلید": "کلید اتصال شما بازنشانی می‌شود. اگر مایل هستید تایید کنید.",
    }
    msg = text_map.get(code, code)
    try:
        await context.bot.send_message(chat_id=t['user_id'], text=msg)
        await query.message.reply_text("✅ پیام ارسال شد.")
    except Exception as e:
        await query.message.reply_text(f"❌ ارسال ناموفق بود: {e}")
    return ADMIN_MAIN_MENU