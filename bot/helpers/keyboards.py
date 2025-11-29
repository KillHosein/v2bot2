from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from ..db import query_db


def build_start_menu_keyboard() -> InlineKeyboardMarkup:
    buttons_data = query_db(
        "SELECT text, target, is_url, row, col FROM buttons WHERE menu_name = 'start_main' ORDER BY row, col"
    )

    trial_status = query_db("SELECT value FROM settings WHERE key = 'free_trial_status'", one=True)
    if not trial_status or trial_status.get('value') != '1':
        buttons_data = [b for b in buttons_data if b.get('target') != 'get_free_config']

    keyboard = []
    if buttons_data:
        max_row = max((b['row'] for b in buttons_data), default=0)
        keyboard_rows = [[] for _ in range(max_row + 1)]
        for b in buttons_data:
            btn = (
                InlineKeyboardButton(b['text'], url=b['target'])
                if b['is_url']
                else InlineKeyboardButton(b['text'], callback_data=b['target'])
            )
            if 0 < b['row'] <= len(keyboard_rows):
                keyboard_rows[b['row'] - 1].append(btn)
        keyboard = [row for row in keyboard_rows if row]

    # --- Fallback Logic ---
    # Ensures core buttons are present if not defined in the database
    missing = lambda target: not any((b.get('target') == target) for b in (buttons_data or []))
    
    # Preferred grouped layout: Buy + My Services (top), Wallet + Support, Tutorials + Referrals, Reseller + Get Free
    existing_targets = {b.get('target') for b in (buttons_data or [])}

    def add_pair(row_targets):
        row = []
        for target, text in row_targets:
            if target == 'get_free_config':
                if not (trial_status and trial_status.get('value') == '1'):
                    continue
            if target not in existing_targets and not any(
                (isinstance(btn, InlineKeyboardButton) and getattr(btn, 'callback_data', None) == target)
                for line in keyboard for btn in line
            ):
                row.append(InlineKeyboardButton(text, callback_data=target))
        if row:
            keyboard.append(row)

    # Top row
    add_pair([
        ('buy_config_main', "\U0001F4E1 خرید کانفیگ"),
        ('my_services', "\U0001F4DD سرویس‌های من"),
    ])
    # Next rows
    add_pair([
        ('wallet_menu', "\U0001F4B3 کیف پول من"),
        ('support_menu', "\U0001F4AC پشتیبانی"),
    ])
    add_pair([
        ('tutorials_menu', "\U0001F4D6 آموزش‌ها"),
        ('referral_menu', "\U0001F517 معرفی به دوستان"),
    ])
    add_pair([
        ('reseller_menu', "\U0001F4B5 دریافت نمایندگی"),
        ('get_free_config', "\U0001F381 دریافت تست"),
    ])

    return InlineKeyboardMarkup(keyboard) if keyboard else None
