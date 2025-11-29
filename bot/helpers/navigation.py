# -*- coding: utf-8 -*-
"""Navigation helpers for better user interaction"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def quick_menu_keyboard(current_page=None):
    """
    Returns a quick access menu keyboard
    Args:
        current_page: Current page to exclude from menu (optional)
    """
    buttons = []
    
    # Row 1: Main services
    row1 = []
    if current_page != 'buy':
        row1.append(InlineKeyboardButton("🛒 خرید سرویس", callback_data='buy_config_main'))
    if current_page != 'services':
        row1.append(InlineKeyboardButton("📱 سرویس‌های من", callback_data='my_services'))
    if row1:
        buttons.append(row1)
    
    # Row 2: Wallet and Support
    row2 = []
    if current_page != 'wallet':
        row2.append(InlineKeyboardButton("💰 کیف پول", callback_data='wallet_menu'))
    if current_page != 'support':
        row2.append(InlineKeyboardButton("💬 پشتیبانی", callback_data='support_menu'))
    if row2:
        buttons.append(row2)
    
    # Row 3: Tutorials and Main Menu
    row3 = []
    if current_page != 'tutorials':
        row3.append(InlineKeyboardButton("📚 آموزش‌ها", callback_data='tutorials_menu'))
    if current_page != 'main':
        row3.append(InlineKeyboardButton("🏠 منوی اصلی", callback_data='start_main'))
    if row3:
        buttons.append(row3)
    
    return InlineKeyboardMarkup(buttons) if buttons else None


def add_back_button(keyboard, back_to, back_label="🔙 بازگشت"):
    """
    Add a back button to existing keyboard
    Args:
        keyboard: List of button rows or InlineKeyboardMarkup
        back_to: Callback data for back button
        back_label: Label for back button
    Returns:
        InlineKeyboardMarkup with back button added
    """
    if isinstance(keyboard, InlineKeyboardMarkup):
        buttons = keyboard.inline_keyboard.copy()
    elif isinstance(keyboard, list):
        buttons = keyboard.copy()
    else:
        buttons = []
    
    buttons.append([InlineKeyboardButton(back_label, callback_data=back_to)])
    return InlineKeyboardMarkup(buttons)


def add_quick_menu(keyboard, current_page=None, show_back=True, back_to='start_main'):
    """
    Add quick menu row to existing keyboard
    Args:
        keyboard: List of button rows or InlineKeyboardMarkup
        current_page: Current page identifier
        show_back: Whether to show back button
        back_to: Where back button should go
    Returns:
        InlineKeyboardMarkup with quick menu added
    """
    if isinstance(keyboard, InlineKeyboardMarkup):
        buttons = keyboard.inline_keyboard.copy()
    elif isinstance(keyboard, list):
        buttons = keyboard.copy()
    else:
        buttons = []
    
    # Add divider comment
    # buttons.append([InlineKeyboardButton("━━━━━━━━━━", callback_data='noop')])
    
    # Quick access buttons
    quick_row = []
    if current_page != 'services':
        quick_row.append(InlineKeyboardButton("📱 سرویس‌ها", callback_data='my_services'))
    if current_page != 'wallet':
        quick_row.append(InlineKeyboardButton("💰 کیف پول", callback_data='wallet_menu'))
    if current_page != 'support':
        quick_row.append(InlineKeyboardButton("💬 پشتیبانی", callback_data='support_menu'))
    
    if quick_row:
        buttons.append(quick_row)
    
    # Back button
    if show_back:
        buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data=back_to)])
    
    return InlineKeyboardMarkup(buttons)


def breadcrumb_text(path):
    """
    Generate breadcrumb navigation text
    Args:
        path: List of tuples [(title, callback_data), ...]
    Returns:
        Formatted breadcrumb string
    """
    if not path:
        return ""
    
    breadcrumbs = " ❯ ".join([item[0] for item in path])
    return f"📍 {breadcrumbs}\n\n"


def service_action_keyboard(order_id, show_all=True):
    """
    Standard keyboard for service actions
    Args:
        order_id: Order ID
        show_all: Whether to show all actions
    Returns:
        InlineKeyboardMarkup
    """
    buttons = []
    
    if show_all:
        buttons.append([
            InlineKeyboardButton("🔄 دریافت لینک مجدد", callback_data=f'refresh_link_{order_id}'),
            InlineKeyboardButton("🔑 تغییر کلید", callback_data=f'revoke_key_{order_id}')
        ])
        buttons.append([
            InlineKeyboardButton("📱 QR Code", callback_data=f'view_qr_{order_id}'),
            InlineKeyboardButton("🔄 تمدید", callback_data=f'renew_service_{order_id}')
        ])
        buttons.append([
            InlineKeyboardButton("🗑 حذف سرویس", callback_data=f'delete_service_{order_id}')
        ])
    
    # Navigation
    buttons.append([
        InlineKeyboardButton("📱 سرویس‌های من", callback_data='my_services'),
        InlineKeyboardButton("🏠 منوی اصلی", callback_data='start_main')
    ])
    
    return InlineKeyboardMarkup(buttons)


def wallet_menu_keyboard(balance):
    """
    Wallet menu keyboard with balance display
    Args:
        balance: Current wallet balance
    Returns:
        InlineKeyboardMarkup
    """
    buttons = [
        [InlineKeyboardButton(f"💵 شارژ کیف پول (موجودی: {balance:,} تومان)", callback_data='wallet_topup_main')],
        [
            InlineKeyboardButton("💳 کارت به کارت", callback_data='wallet_topup_card'),
            InlineKeyboardButton("🌐 درگاه پرداخت", callback_data='wallet_topup_gateway')
        ],
        [
            InlineKeyboardButton("₿ رمزارز", callback_data='wallet_topup_crypto'),
            InlineKeyboardButton("📊 تراکنش‌ها", callback_data='wallet_transactions')
        ],
        [InlineKeyboardButton("🔙 بازگشت", callback_data='start_main')]
    ]
    return InlineKeyboardMarkup(buttons)


def confirmation_keyboard(yes_data, no_data, yes_label="✅ بله", no_label="❌ خیر"):
    """
    Generic confirmation keyboard
    Args:
        yes_data: Callback data for yes button
        no_data: Callback data for no button
        yes_label: Label for yes button
        no_label: Label for no button
    Returns:
        InlineKeyboardMarkup
    """
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(yes_label, callback_data=yes_data),
        InlineKeyboardButton(no_label, callback_data=no_data)
    ]])


def pagination_keyboard(current_page, total_pages, callback_prefix, extra_buttons=None):
    """
    Pagination keyboard
    Args:
        current_page: Current page number (1-indexed)
        total_pages: Total number of pages
        callback_prefix: Prefix for callback data (e.g., 'page_')
        extra_buttons: List of button rows to add above pagination
    Returns:
        InlineKeyboardMarkup
    """
    buttons = []
    
    # Add extra buttons first
    if extra_buttons:
        buttons.extend(extra_buttons)
    
    # Pagination row
    if total_pages > 1:
        page_row = []
        
        # Previous button
        if current_page > 1:
            page_row.append(InlineKeyboardButton("◀️ قبلی", callback_data=f'{callback_prefix}{current_page-1}'))
        
        # Page indicator
        page_row.append(InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data='noop'))
        
        # Next button
        if current_page < total_pages:
            page_row.append(InlineKeyboardButton("بعدی ▶️", callback_data=f'{callback_prefix}{current_page+1}'))
        
        buttons.append(page_row)
    
    return InlineKeyboardMarkup(buttons)
