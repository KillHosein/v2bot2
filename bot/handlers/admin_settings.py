from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from ..db import query_db, execute_db
from ..states import SETTINGS_MENU, SETTINGS_AWAIT_TRIAL_DAYS, SETTINGS_AWAIT_PAYMENT_TEXT, SETTINGS_AWAIT_USD_RATE, SETTINGS_AWAIT_GATEWAY_API, SETTINGS_AWAIT_SIGNUP_BONUS, SETTINGS_AWAIT_TRAFFIC_ALERT_VALUE
from ..helpers.tg import notify_admins, append_footer_buttons as _footer, answer_safely as _ans, safe_edit_text as _safe_edit_text
from ..config import ADMIN_ID, logger


def _md_escape(text: str) -> str:
    if not text:
        return ''
    return (
        text.replace('\\', r'\\')
            .replace('_', r'\_')
            .replace('*', r'\*')
            .replace('`', r'\`')
            .replace('[', r'\[')
            .replace(']', r'\]')
            .replace('(', r'\(')
            .replace(')', r'\)')
    )


async def admin_settings_manage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass  # Ignore expired callback queries
    settings = {s['key']: s['value'] for s in query_db("SELECT key, value FROM settings")}
    trial_status = settings.get('free_trial_status', '0')
    trial_button_text = "\u274C غیرفعال کردن تست" if trial_status == '1' else "\u2705 فعال کردن تست"
    trial_button_callback = "set_trial_status_0" if trial_status == '1' else "set_trial_status_1"

    usd_manual = settings.get('usd_irt_manual') or 'تنظیم نشده'
    usd_cached = settings.get('usd_irt_cached') or '-'
    usd_mode = (settings.get('usd_irt_mode') or 'manual').lower()
    mode_title = 'API' if usd_mode == 'api' else 'دستی'
    next_mode = 'manual' if usd_mode == 'api' else 'api'

    pay_card = settings.get('pay_card_enabled', '1') == '1'
    pay_crypto = settings.get('pay_crypto_enabled', '1') == '1'
    pay_gateway = settings.get('pay_gateway_enabled', '0') == '1'
    gateway_type = (settings.get('gateway_type') or 'zarinpal').lower()
    sb_enabled = settings.get('signup_bonus_enabled', '0') == '1'
    sb_amount = int((settings.get('signup_bonus_amount') or '0') or 0)
    trial_panel_id = (settings.get('free_trial_panel_id') or '').strip()
    panels = query_db("SELECT id, name FROM panels ORDER BY id") or []
    trial_panel_name = next((p['name'] for p in panels if str(p['id']) == trial_panel_id), 'پیش‌فرض')
    ref_percent = int((settings.get('referral_commission_percent') or '10') or 10)

    # New: traffic alert (GB-only) and time alerts
    user_show_quota = (settings.get('user_show_quota_enabled') or '1') == '1'
    ta_enabled = (settings.get('traffic_alert_enabled') or '0') == '1'
    ta_value_gb = settings.get('traffic_alert_value_gb') or '5'
    time_alert_on = (settings.get('time_alert_enabled') or '1') == '1'
    time_alert_days = settings.get('time_alert_days') or '3'
    # Auto-backup
    auto_backup_on = (settings.get('auto_backup_enabled') or '0') == '1'
    auto_backup_hours = settings.get('auto_backup_hours') or '12'

    # Join/purchase logs settings
    join_logs_on = (settings.get('join_logs_enabled') or '0') == '1'
    join_logs_chat = settings.get('join_logs_chat_id') or '-'
    purch_logs_on = (settings.get('purchase_logs_enabled') or '0') == '1'
    purch_logs_chat = settings.get('purchase_logs_chat_id') or '-'

    text = (
        f"⚙️ **تنظیمات کلی ربات**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 **سرویس تست رایگان**\n"
        f"   • وضعیت: {'✅ فعال' if trial_status == '1' else '❌ غیرفعال'}\n"
        f"   • مدت: `{settings.get('free_trial_days', '1')}` روز | حجم: `{settings.get('free_trial_gb', '0.2')} GB`\n"
        f"   • پنل ساخت: `{trial_panel_name}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 **تنظیمات مالی**\n"
        f"   • کمیسیون معرفی: `{ref_percent}%`\n"
        f"   • نرخ دلار: `{usd_manual}` تومان\n"
        f"   • آخرین کش: `{usd_cached}`\n"
        f"   • حالت: `{mode_title}`\n"
        f"   • هدیه ثبت‌نام: {'✅ فعال' if sb_enabled else '❌ غیرفعال'} | `{sb_amount:,}` تومان\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 **روش‌های پرداخت**\n"
        f"   • کارت به کارت: {'✅ فعال' if pay_card else '❌ غیرفعال'}\n"
        f"   • رمزارز (کریپتو): {'✅ فعال' if pay_crypto else '❌ غیرفعال'}\n"
        f"   • درگاه آنلاین: {'✅ فعال' if pay_gateway else '❌ غیرفعال'} ({'زرین‌پال' if gateway_type=='zarinpal' else 'آقای پرداخت'})\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 **سیستم هشدارها (هر 12 ساعت)**\n"
        f"   • نمایش حجم به کاربر: {'✅ فعال' if user_show_quota else '❌ غیرفعال'}\n"
        f"   • هشدار حجم: {'✅ فعال' if ta_enabled else '❌ غیرفعال'} | آستانه: `{ta_value_gb} GB`\n"
        f"   • هشدار زمان: {'✅ فعال' if time_alert_on else '❌ غیرفعال'} | آستانه: `{time_alert_days} روز`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💾 **بکاپ خودکار**\n"
        f"   • وضعیت: {'✅ فعال' if auto_backup_on else '❌ غیرفعال'}\n"
        f"   • بازه زمانی: هر `{auto_backup_hours}` ساعت\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **لاگ‌های سیستم**\n"
        f"   • لاگ ورود کاربر: {'✅ فعال' if join_logs_on else '❌ غیرفعال'} | چت: `{join_logs_chat}`\n"
        f"   • لاگ خرید/تمدید: {'✅ فعال' if purch_logs_on else '❌ غیرفعال'} | چت: `{purch_logs_chat}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 **متن زیر کانفیگ:**\n{_md_escape((settings.get('config_footer_text') or '').strip()) or '-'}\n\n"
        f"💡 برای تغییر: `/setms` و سپس متن جدید\n"
    )
    keyboard = [
        # Group 1: Trials & Payments
        [InlineKeyboardButton(trial_button_text, callback_data=trial_button_callback)],
        [InlineKeyboardButton("روز/حجم تست", callback_data="set_trial_days"), InlineKeyboardButton("ویرایش متن پرداخت", callback_data="set_payment_text")],
        [InlineKeyboardButton("انتخاب پنل ساخت تست", callback_data="set_trial_panel_start")],
        # Group 2: Business & Wallet
        [InlineKeyboardButton("تنظیمات نمایندگی", callback_data="admin_reseller_menu"), InlineKeyboardButton("تنظیم درصد کمیسیون معرفی", callback_data="set_ref_percent_start")],
        [InlineKeyboardButton("\U0001F4B3 کارت‌ها", callback_data="admin_cards_menu"), InlineKeyboardButton("\U0001F4B0 ولت‌ها", callback_data="admin_wallets_menu")],
        [InlineKeyboardButton("\U0001F4B8 درخواست‌های کیف پول", callback_data="admin_wallet_tx_menu")],
        # Group 3: Pricing & Payments
        [InlineKeyboardButton("\U0001F4B1 تنظیم نرخ دلار", callback_data="set_usd_rate_start"), InlineKeyboardButton("\U0001F504 تغییر حالت نرخ: " + ("به دستی" if next_mode=='manual' else "به API"), callback_data=f"toggle_usd_mode_{next_mode}")],
        [InlineKeyboardButton(("کارت: غیرفعال" if pay_card else "کارت: فعال"), callback_data=f"toggle_pay_card_{0 if pay_card else 1}"), InlineKeyboardButton(("رمزارز: غیرفعال" if pay_crypto else "رمزارز: فعال"), callback_data=f"toggle_pay_crypto_{0 if pay_crypto else 1}")],
        [InlineKeyboardButton(("درگاه: غیرفعال" if pay_gateway else "درگاه: فعال"), callback_data=f"toggle_pay_gateway_{0 if pay_gateway else 1}"), InlineKeyboardButton(("زرین‌پال" if gateway_type!='zarinpal' else "آقای پرداخت"), callback_data=f"toggle_gateway_type_{'zarinpal' if gateway_type!='zarinpal' else 'aghapay'}")],
        [InlineKeyboardButton(("هدیه ثبت‌نام: غیرفعال" if sb_enabled else "هدیه ثبت‌نام: فعال"), callback_data=f"toggle_signup_bonus_{0 if sb_enabled else 1}"), InlineKeyboardButton("مبلغ هدیه", callback_data="set_signup_bonus_amount")],
        # Group 4: Alerts
        [InlineKeyboardButton(("👁 نمایش حجم: مخفی" if user_show_quota else "👁 نمایش حجم: نمایش"), callback_data=f"toggle_user_quota_{0 if user_show_quota else 1}")],
        [InlineKeyboardButton(("📊 هشدار حجم: غیرفعال" if ta_enabled else "📊 هشدار حجم: فعال"), callback_data=f"toggle_talert_{0 if ta_enabled else 1}"), InlineKeyboardButton("📏 تنظیم آستانه حجم (GB)", callback_data="set_talert_gb_start")],
        [InlineKeyboardButton(("⏰ هشدار زمان: غیرفعال" if time_alert_on else "⏰ هشدار زمان: فعال"), callback_data=f"toggle_time_alert_{0 if time_alert_on else 1}"), InlineKeyboardButton("📅 تنظیم آستانه زمان (روز)", callback_data="set_time_alert_days_start")],
        # Group 5: Auto-backup
        [InlineKeyboardButton(("بکاپ خودکار: غیرفعال" if auto_backup_on else "بکاپ خودکار: فعال"), callback_data=f"toggle_auto_backup_{0 if auto_backup_on else 1}"), InlineKeyboardButton("بازه بکاپ (ساعت)", callback_data="set_auto_backup_hours_start")],
        # Group 6: Admin wallet manual adjust
        [InlineKeyboardButton("افزایش/کاهش کیف پول (ادمین)", callback_data="admin_wallet_adjust_menu")],
        # Group 7: Config footer text
        [InlineKeyboardButton("ویرایش متن زیر کانفیگ", callback_data="set_config_footer_start")],
        # Group 8: Logs settings
        [InlineKeyboardButton(("لاگ ورود: غیرفعال" if join_logs_on else "لاگ ورود: فعال"), callback_data=f"toggle_join_logs_{0 if join_logs_on else 1}"), InlineKeyboardButton("گروه/چت لاگ ورود", callback_data="set_join_logs_chat")],
        [InlineKeyboardButton(("لاگ خرید: غیرفعال" if purch_logs_on else "لاگ خرید: فعال"), callback_data=f"toggle_purchase_logs_{0 if purch_logs_on else 1}"), InlineKeyboardButton("گروه/چت لاگ خرید", callback_data="set_purchase_logs_chat")],
        [InlineKeyboardButton("ارسال تست لاگ ورود", callback_data="test_join_log"), InlineKeyboardButton("ارسال تست لاگ خرید", callback_data="test_purchase_log")],
        # Back
        [InlineKeyboardButton("\U0001F519 بازگشت", callback_data="admin_main")],
    ]
    try:
        await _safe_edit_text(query.message, text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        # If edit fails (message too old, deleted, etc), send new message and delete old one
        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            # Last resort: send to chat directly
            try:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception:
                pass
    return SETTINGS_MENU


async def admin_toggle_trial_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    new_status = query.data.split('_')[-1]
    execute_db("UPDATE settings SET value = ? WHERE key = 'free_trial_status'", (new_status,))
    await query.answer(f"وضعیت تست رایگان {'فعال' if new_status == '1' else 'غیرفعال'} شد.", show_alert=True)
    return await admin_settings_manage(update, context)


async def _resolve_chat_ident(raw: str):
    raw = (raw or '').strip()
    if not raw:
        return None
    if raw.startswith('@'):
        return raw
    if raw.lstrip('-').isdigit():
        try:
            return int(raw)
        except Exception:
            return None
    return None
async def admin_toggle_join_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    target = query.data.split('_')[-1]
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('join_logs_enabled', ?)", (target,))
    return await admin_settings_manage(update, context)


async def admin_toggle_purchase_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    target = query.data.split('_')[-1]
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('purchase_logs_enabled', ?)", (target,))
    return await admin_settings_manage(update, context)


async def admin_set_join_logs_chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_admin'] = 'set_join_logs_chat'
    await _safe_edit_text(query.message, "شناسه چت (ID) گروه/چنل برای لاگ ورود را ارسال کنید. (مثال: -1001234567890)")
    return SETTINGS_AWAIT_USD_RATE


async def admin_set_purchase_logs_chat_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_admin'] = 'set_purchase_logs_chat'
    await _safe_edit_text(query.message, "شناسه چت (ID) گروه/چنل برای لاگ خرید را ارسال کنید. (مثال: -1001234567890)")
    return SETTINGS_AWAIT_USD_RATE


async def admin_settings_save_log_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    mode = context.user_data.get('awaiting_admin')
    if mode not in ('set_join_logs_chat', 'set_purchase_logs_chat'):
        return ConversationHandler.END
    txt = (update.message.text or '').strip()
    if not txt:
        await update.message.reply_text("ورودی نامعتبر است.")
        return ConversationHandler.END
    key = 'join_logs_chat_id' if mode == 'set_join_logs_chat' else 'purchase_logs_chat_id'
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, txt))
    context.user_data.pop('awaiting_admin', None)
    await update.message.reply_text("ذخیره شد.")
    fake_query = type('obj', (object,), {
        'data': 'admin_settings_manage', 'message': update.message, 'answer': (lambda *args, **kwargs: None), 'from_user': update.effective_user,
    })
    fake_update = type('obj', (object,), {'callback_query': fake_query, 'effective_user': update.effective_user})
    return await admin_settings_manage(fake_update, context)


async def admin_settings_send_test_join_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    st = {r['key']: r['value'] for r in query_db("SELECT key,value FROM settings WHERE key IN ('join_logs_enabled','join_logs_chat_id')")}
    if (st.get('join_logs_enabled') or '0') != '1':
        await _ans(query, "لاگ ورود غیرفعال است.", show_alert=True)
        return await admin_settings_manage(update, context)
    ident = await _resolve_chat_ident(st.get('join_logs_chat_id') or '')
    if not ident:
        await _ans(query, "شناسه چت لاگ ورود صحیح نیست.", show_alert=True)
        return await admin_settings_manage(update, context)
    try:
        await context.bot.send_message(chat_id=ident, text="[TEST] لاگ ورود")
        await _ans(query, "تست با موفقیت ارسال شد.", show_alert=True)
    except Exception as e:
        try:
            await _ans(query, f"خطا در ارسال تست: {e}", show_alert=True)
        except Exception:
            pass
    return await admin_settings_manage(update, context)


async def admin_settings_send_test_purchase_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    st = {r['key']: r['value'] for r in query_db("SELECT key,value FROM settings WHERE key IN ('purchase_logs_enabled','purchase_logs_chat_id')")}
    if (st.get('purchase_logs_enabled') or '0') != '1':
        await _ans(query, "لاگ خرید غیرفعال است.", show_alert=True)
        return await admin_settings_manage(update, context)
    ident = await _resolve_chat_ident(st.get('purchase_logs_chat_id') or '')
    if not ident:
        await _ans(query, "شناسه چت لاگ خرید صحیح نیست.", show_alert=True)
        return await admin_settings_manage(update, context)
    try:
        await context.bot.send_message(chat_id=ident, text="[TEST] لاگ خرید")
        await _ans(query, "تست با موفقیت ارسال شد.", show_alert=True)
    except Exception as e:
        try:
            await _ans(query, f"خطا در ارسال تست: {e}", show_alert=True)
        except Exception:
            pass
    return await admin_settings_manage(update, context)


async def admin_wallet_adjust_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("➕ افزایش موجودی", callback_data="wallet_adjust_start_credit"), InlineKeyboardButton("➖ کاهش موجودی", callback_data="wallet_adjust_start_debit")],
        [InlineKeyboardButton("\U0001F519 بازگشت", callback_data="admin_settings_manage")],
    ]
    try:
        await _safe_edit_text(query.message, "عملیات دستی کیف پول کاربر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))
    except Exception:
        try:
            await query.message.reply_text("عملیات دستی کیف پول کاربر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))
        except Exception:
            pass
    return SETTINGS_MENU


async def admin_toggle_usd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    target = query.data.split('_')[-1]
    execute_db("UPDATE settings SET value = ? WHERE key = 'usd_irt_mode'", (target,))
    return await admin_settings_manage(update, context)


async def admin_settings_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    action = query.data
    prompts = {
        'set_trial_days': "تعداد روزهای تست را وارد کنید:",
        'set_payment_text': "متن پرداخت را ارسال کنید:",
    }
    states = {
        'set_trial_days': SETTINGS_AWAIT_TRIAL_DAYS,
        'set_payment_text': SETTINGS_AWAIT_PAYMENT_TEXT,
    }
    await _safe_edit_text(query.message, prompts[action])
    return states[action]


async def admin_settings_save_trial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        days, gb = update.message.text.split('-')
        execute_db("UPDATE settings SET value = ? WHERE key = 'free_trial_days'", (days.strip(),))
        execute_db("UPDATE settings SET value = ? WHERE key = 'free_trial_gb'", (gb.strip(),))
        await update.message.reply_text("\u2705 تنظیمات تست رایگان با موفقیت ذخیره شد.")
    except Exception:
        await update.message.reply_text("فرمت نامعتبر است. لطفا با فرمت `روز-حجم` وارد کنید.")
        return SETTINGS_AWAIT_TRIAL_DAYS
    return await admin_settings_manage(update, context)


async def admin_settings_save_payment_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    awaiting = context.user_data.get('awaiting_admin')
    if awaiting and awaiting != 'set_payment_text':
        return ConversationHandler.END
    new_text = (update.message.text or '').strip()
    if not new_text:
        await update.message.reply_text("ورودی نامعتبر است. متن خالی ارسال نکنید.")
        return ConversationHandler.END
    execute_db("UPDATE messages SET text = ? WHERE message_name = ?", (new_text, 'payment_info_text'))
    context.user_data.pop('awaiting_admin', None)
    await update.message.reply_text("\u2705 متن پرداخت با موفقیت ذخیره شد.")
    fake_query = type('obj', (object,), {
        'data': 'admin_settings_manage',
        'message': update.message,
        'answer': (lambda *args, **kwargs: None),
        'from_user': update.effective_user,
    })
    fake_update = type('obj', (object,), {'callback_query': fake_query, 'effective_user': update.effective_user})
    return await admin_settings_manage(fake_update, context)


async def admin_run_alerts_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await _ans(query, "در حال اجرای هشدارها...", show_alert=True)
    try:
        from ..jobs import check_expirations
        await check_expirations(context)
        await _ans(query, "انجام شد: اجرای هشدارها تکمیل شد.", show_alert=True)
    except Exception as e:
        try:
            await _ans(query, f"خطا در اجرای هشدارها: {e}", show_alert=True)
        except Exception:
            try:
                await context.bot.send_message(chat_id=query.from_user.id, text=f"خطا در اجرای هشدارها: {e}")
            except Exception:
                pass
    return await admin_settings_manage(update, context)


async def admin_toggle_user_quota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    target = query.data.split('_')[-1]
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('user_show_quota_enabled', ?)", (target,))
    return await admin_settings_manage(update, context)


async def admin_toggle_talert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    target = query.data.split('_')[-1]
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('traffic_alert_enabled', ?)", (target,))
    return await admin_settings_manage(update, context)


async def admin_set_talert_gb_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_admin'] = 'set_talert_gb'
    await _safe_edit_text(
        query.message,
        "📏 **تنظیم آستانه هشدار حجم**\n\n"
        "لطفاً مقدار حجم باقی‌مانده (به گیگابایت) را وارد کنید.\n"
        "وقتی حجم باقی‌مانده کاربر کمتر از این مقدار شود، هشدار ارسال می‌شود.\n\n"
        "💡 **مثال:** `5` (برای 5 گیگابایت)\n\n"
        "🔢 عدد را وارد کنید:"
    )
    return SETTINGS_AWAIT_TRAFFIC_ALERT_VALUE


async def admin_set_time_alert_days_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_admin'] = 'set_time_alert_days'
    await _safe_edit_text(
        query.message,
        "📅 **تنظیم آستانه هشدار زمان**\n\n"
        "لطفاً تعداد روزهای باقی‌مانده را وارد کنید.\n"
        "وقتی روزهای باقی‌مانده تا پایان سرویس کمتر از این مقدار شود، هشدار ارسال می‌شود.\n\n"
        "💡 **مثال:** `3` (برای 3 روز مانده)\n\n"
        "🔢 عدد را وارد کنید:"
    )
    return SETTINGS_AWAIT_TRAFFIC_ALERT_VALUE


async def admin_set_talert_value_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = (update.message.text or '').strip().replace('%','')
    mode = context.user_data.get('awaiting_admin')
    
    if mode == 'set_talert_gb':
        try:
            val = float(txt)
        except Exception:
            await update.message.reply_text("❌ عدد نامعتبر است. لطفاً دوباره تلاش کنید:")
            return SETTINGS_AWAIT_TRAFFIC_ALERT_VALUE
        execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('traffic_alert_value_gb', ?)", (str(val),))
        await update.message.reply_text(f"✅ مقدار هشدار حجم به {val} GB تنظیم شد.\n\n🔄 بازگشت به منوی تنظیمات...")
    elif mode == 'set_time_alert_days':
        try:
            ival = int(txt)
        except Exception:
            await update.message.reply_text("❌ عدد صحیح نامعتبر است. لطفاً دوباره تلاش کنید:")
            return SETTINGS_AWAIT_TRAFFIC_ALERT_VALUE
        execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('time_alert_days', ?)", (str(ival),))
        await update.message.reply_text(f"✅ روزهای هشدار زمان به {ival} روز تنظیم شد.\n\n🔄 بازگشت به منوی تنظیمات...")
    elif mode == 'set_auto_backup_hours':
        try:
            hours = int(txt)
            if hours <= 0:
                raise ValueError("Hours must be positive")
        except Exception:
            await update.message.reply_text("❌ عدد صحیح نامعتبر است. لطفاً دوباره تلاش کنید:")
            return SETTINGS_AWAIT_TRAFFIC_ALERT_VALUE
        execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('auto_backup_hours', ?)", (str(hours),))
        # Reschedule the backup job with new interval
        try:
            jq = context.application.job_queue
            # Cancel existing backup job
            for j in jq.get_jobs_by_name("auto_backup_send"):
                j.schedule_removal()
            # Check if auto-backup is enabled
            ab_enabled = (query_db("SELECT value FROM settings WHERE key='auto_backup_enabled'", one=True) or {}).get('value') == '1'
            if ab_enabled:
                from ..jobs import backup_and_send_to_admins
                from ..config import logger
                interval_seconds = hours * 3600
                jq.run_repeating(backup_and_send_to_admins, interval=interval_seconds, first=60, name="auto_backup_send")
                logger.info(f"Auto-backup rescheduled: every {hours} hours ({interval_seconds} seconds)")
        except Exception as e:
            from ..config import logger
            logger.error(f"Failed to reschedule auto-backup: {e}")
        await update.message.reply_text(f"✅ بازه بکاپ خودکار به هر {hours} ساعت تنظیم شد و job مجدداً برنامه‌ریزی شد.\n\n🔄 بازگشت به منوی تنظیمات...")
    else:
        await update.message.reply_text("❌ خطا: حالت ناشناخته")
        context.user_data.pop('awaiting_admin', None)
        return ConversationHandler.END
    
    context.user_data.pop('awaiting_admin', None)
    
    # Send settings menu using bot.send_message
    import asyncio
    await asyncio.sleep(1)
    
    # Call admin_settings_manage with a proper fake update
    from telegram import CallbackQuery
    
    # Create a proper async callable for answer
    async def noop_answer(*args, **kwargs):
        return
    
    # Create fake callback query
    fake_query = type('CallbackQuery', (), {
        'answer': noop_answer,
        'data': 'admin_settings_manage',
        'from_user': update.effective_user,
        'message': update.message,
    })()
    
    fake_update = type('Update', (), {
        'callback_query': fake_query,
        'effective_user': update.effective_user,
        'message': update.message,
    })()
    
    return await admin_settings_manage(fake_update, context)


async def admin_toggle_time_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    target = query.data.split('_')[-1]
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('time_alert_enabled', ?)", (target,))
    return await admin_settings_manage(update, context)


async def admin_toggle_auto_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    target = query.data.split('_')[-1]
    execute_db("INSERT OR REPLACE INTO settings (key, value) VALUES ('auto_backup_enabled', ?)", (target,))
    # Reschedule job immediately
    try:
        # Cancel existing
        jq = context.application.job_queue
        for j in jq.get_jobs_by_name("auto_backup_send"):
            j.schedule_removal()
        # If enabling, schedule with current hours
        if target == '1':
            from ..db import query_db as _q
            try:
                hours = int((_q("SELECT value FROM settings WHERE key='auto_backup_hours'", one=True) or {}).get('value') or '12')
            except Exception:
                hours = 12
            if hours > 0:
                from ..jobs import backup_and_send_to_admins
                jq.run_repeating(backup_and_send_to_admins, interval=hours*3600, first=60, name="auto_backup_send")
    except Exception:
        pass
    return await admin_settings_manage(update, context)


async def admin_set_auto_backup_hours_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_admin'] = 'set_auto_backup_hours'
    await _safe_edit_text(query.message, "بازه ارسال بکاپ خودکار (ساعت) را وارد کنید. مثلا 12")
    return SETTINGS_AWAIT_TRAFFIC_ALERT_VALUE