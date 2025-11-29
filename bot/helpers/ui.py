"""UI Helper functions for consistent user interface"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def add_cancel_button(keyboard, cancel_text="❌ انصراف", cancel_callback="cancel_flow"):
    """
    Add cancel button to any keyboard
    
    Args:
        keyboard: List of button rows
        cancel_text: Text for cancel button
        cancel_callback: Callback data for cancel
    
    Returns:
        Modified keyboard with cancel button
    """
    keyboard.append([InlineKeyboardButton(cancel_text, callback_data=cancel_callback)])
    return keyboard


def add_back_and_cancel(keyboard, back_callback="start_main", cancel_callback="cancel_flow"):
    """
    Add both back and cancel buttons
    
    Args:
        keyboard: List of button rows
        back_callback: Callback data for back button
        cancel_callback: Callback data for cancel
    
    Returns:
        Modified keyboard with both buttons
    """
    keyboard.append([
        InlineKeyboardButton("🔙 بازگشت", callback_data=back_callback),
        InlineKeyboardButton("❌ انصراف", callback_data=cancel_callback)
    ])
    return keyboard


def create_confirmation_keyboard(confirm_callback, cancel_callback="cancel_flow"):
    """
    Create Yes/No confirmation keyboard
    
    Args:
        confirm_callback: Callback for confirm action
        cancel_callback: Callback for cancel
    
    Returns:
        InlineKeyboardMarkup with confirmation buttons
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ تأیید", callback_data=confirm_callback),
            InlineKeyboardButton("❌ انصراف", callback_data=cancel_callback)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
