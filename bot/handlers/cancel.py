"""Cancel flow handler"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler


async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Cancel any ongoing conversation/flow
    Clear user data and return to main menu
    """
    query = update.callback_query
    await query.answer()
    
    # Clear all user data
    context.user_data.clear()
    
    # Send cancellation message
    keyboard = [
        [
            InlineKeyboardButton("🏠 منوی اصلی", callback_data="start_main"),
            InlineKeyboardButton("📱 سرویس‌ها", callback_data="my_services")
        ],
        [
            InlineKeyboardButton("💰 کیف پول", callback_data="wallet_menu"),
            InlineKeyboardButton("💬 پشتیبانی", callback_data="support_menu")
        ]
    ]
    
    try:
        await query.message.edit_text(
            "❌ <b>عملیات لغو شد</b>\n\n"
            "می‌توانید از منوی زیر اقدام کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    except Exception:
        try:
            await query.message.reply_text(
                "❌ <b>عملیات لغو شد</b>\n\n"
                "می‌توانید از منوی زیر اقدام کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        except Exception:
            pass
    
    return ConversationHandler.END


async def cancel_admin_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Cancel admin conversation/flow
    """
    query = update.callback_query
    await query.answer()
    
    # Clear user data
    context.user_data.clear()
    
    keyboard = [[InlineKeyboardButton("🏠 پنل ادمین", callback_data="admin_main")]]
    
    try:
        await query.message.edit_text(
            "❌ <b>عملیات لغو شد</b>\n\n"
            "بازگشت به پنل ادمین...",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    except Exception:
        try:
            await query.message.reply_text(
                "❌ <b>عملیات لغو شد</b>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        except Exception:
            pass
    
    return ConversationHandler.END
