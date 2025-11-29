from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..db import query_db, execute_db
from ..states import ADMIN_CRON_MENU, ADMIN_CRON_AWAIT_HOUR
from ..helpers.tg import safe_edit_text as _safe_edit_text, answer_safely as _ans

async def admin_cron_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from ..config import logger
    logger.info("admin_cron_menu called")
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"Failed to answer callback in cron menu: {e}")
        pass  # Ignore expired callback queries
    st = {s['key']: s['value'] for s in (query_db("SELECT key, value FROM settings WHERE key IN ('reminder_job_enabled','daily_job_hour')") or [])}
    enabled = (st.get('reminder_job_enabled') or '1') == '1'
    hour = int((st.get('daily_job_hour') or '9') or 9)

    text = (
        "⏱️ تنظیمات کرون و زمان‌بندی\n\n"
        f"- وضعیت یادآوری‌ها: {'فعال' if enabled else 'غیرفعال'}\n"
        f"- ساعت اجرای روزانه: `{hour}:00` (به وقت سرور)\n\n"
        "یادداشت: تغییر ساعت پس از راه‌اندازی مجدد ربات اعمال می‌شود."
    )
    kb = [
        [InlineKeyboardButton(("غیرفعال کردن یادآوری‌ها" if enabled else "فعال کردن یادآوری‌ها"), callback_data=f"cron_toggle_reminders_{0 if enabled else 1}")],
        [InlineKeyboardButton("تغییر ساعت اجرای روزانه", callback_data="cron_set_hour_start")],
        [InlineKeyboardButton("بازگشت", callback_data="admin_main")],
    ]
    try:
        await _safe_edit_text(query.message, text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        # If edit fails, try deleting and sending new message
        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
        except Exception:
            # Last resort: send to chat directly
            try:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(kb)
                )
            except Exception:
                pass
    return ADMIN_CRON_MENU

async def admin_cron_toggle_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    val = query.data.split('_')[-1]
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('reminder_job_enabled', ?)", (val,))
    await _ans(query, "ذخیره شد.")
    return await admin_cron_menu(update, context)

async def admin_cron_set_hour_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await _safe_edit_text(query.message, "ساعت اجرای روزانه را وارد کنید (0 تا 23):")
    return ADMIN_CRON_AWAIT_HOUR

async def admin_cron_set_hour_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = (update.message.text or '').strip()
    try:
        hour = int(txt)
        if not (0 <= hour <= 23):
            raise ValueError("range")
    except Exception:
        await update.message.reply_text("عدد نامعتبر. ساعتی بین 0 تا 23 وارد کنید.")
        return ADMIN_CRON_AWAIT_HOUR
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('daily_job_hour', ?)", (str(hour),))
    await update.message.reply_text("ذخیره شد. تغییر ساعت پس از ری‌استارت اعمال می‌شود.")
    # Return to menu with proper async answer
    import asyncio
    async def noop_answer(*args, **kwargs):
        return
    fake_query = type('obj', (object,), {'data': 'admin_cron_menu', 'message': update.message, 'answer': noop_answer})
    fake_update = type('obj', (object,), {'callback_query': fake_query, 'effective_user': update.effective_user})
    return await admin_cron_menu(fake_update, context)
