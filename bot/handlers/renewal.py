from datetime import datetime
import json
from typing import Tuple, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from ..db import query_db, execute_db
from ..states import (
    RENEW_SELECT_PLAN,
    RENEW_AWAIT_DISCOUNT_CODE,
    RENEW_AWAIT_PAYMENT,
)
from ..panel import VpnPanelAPI
from ..helpers.flow import set_flow, clear_flow
from ..helpers.tg import notify_admins, append_footer_buttons as _footer, safe_edit_text as _safe_edit_text
from ..helpers.admin_notifications import send_renewal_log
from ..config import logger


def _get_additions_from_plan(plan: dict) -> Tuple[float, int]:
    """Safely extract GB and day deltas from a plan record."""
    add_gb = 0.0
    add_days = 0
    try:
        add_gb = float(plan.get('traffic_gb', 0))
    except Exception:
        add_gb = 0.0
    try:
        add_days = int(plan.get('duration_days', 0))
    except Exception:
        add_days = 0
    return add_gb, add_days


def _find_inbound_id(api: VpnPanelAPI, marz_username: str) -> Optional[int]:
    """Search all inbounds for a client email matching marz_username."""
    try:
        inbounds, _msg = api.list_inbounds()
    except Exception:
        return None

    for ib in inbounds or []:
        inbound_id = ib.get('id')
        inbound = None
        try:
            inbound = api._fetch_inbound_detail(inbound_id)
        except Exception:
            inbound = None
        if not inbound:
            continue
        settings_str = inbound.get('settings')
        try:
            settings_obj = json.loads(settings_str) if isinstance(settings_str, str) else {}
        except Exception:
            settings_obj = {}
        for c in (settings_obj.get('clients') or []):
            if c.get('email') == marz_username:
                return inbound_id
    return None


async def start_renewal_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    order_id = int(query.data.split('_')[-1])
    # Don't answer here - let show_payment_method_selection handle it
    
    context.user_data['renewing_order_id'] = order_id

    # Get the original order's plan and auto-select it for renewal
    order = query_db("SELECT plan_id FROM orders WHERE id = ?", (order_id,), one=True)
    if not order or not order.get('plan_id'):
        await query.answer()
        await _safe_edit_text(query.message,
            "خطا: پلن سرویس اصلی یافت نشد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001F519 بازگشت", callback_data='my_services')]]),
        )
        return ConversationHandler.END
    
    plan_id = order['plan_id']
    plan = query_db("SELECT * FROM plans WHERE id = ?", (plan_id,), one=True)
    if not plan:
        await query.answer()
        await _safe_edit_text(query.message,
            "خطا: پلن یافت نشد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001F519 بازگشت", callback_data='my_services')]]),
        )
        return ConversationHandler.END

    # Auto-select the same plan and go directly to payment
    context.user_data['selected_renewal_plan_id'] = plan_id
    context.user_data['original_price'] = plan['price']
    context.user_data['final_price'] = plan['price']
    context.user_data['discount_code'] = None

    text = (
        f"🔄 **تمدید سرویس**\n\n"
        f"**پلن:** {plan['name']}\n"
        f"**حجم:** {plan.get('traffic_gb', 0)} GB\n"
        f"**مدت:** {plan.get('duration_days', 0)} روز\n"
        f"**قیمت:** {plan['price']:,} تومان\n\n"
        f"لطفا روش پرداخت را انتخاب کنید:"
    )
    
    # Go directly to payment method selection
    from .purchase import show_payment_method_selection
    context.user_data['_renewal_message_text'] = text
    return await show_payment_method_selection(update, context)


async def show_renewal_plan_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    plan_id = int(query.data.replace('renew_select_plan_', ''))
    await query.answer()

    plan = query_db("SELECT * FROM plans WHERE id = ?", (plan_id,), one=True)
    order_id = context.user_data.get('renewing_order_id')

    if not plan or not order_id:
        await _safe_edit_text(query.message,
            "خطا: پلن یا سفارش یافت نشد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001F519 بازگشت", callback_data=f"view_service_{order_id}")]]),
        )
        return ConversationHandler.END

    context.user_data['selected_renewal_plan_id'] = plan_id
    context.user_data['original_price'] = plan['price']
    context.user_data['final_price'] = plan['price']
    context.user_data['discount_code'] = None

    text = (
        f"شما پلن زیر را برای تمدید انتخاب کرده‌اید:\n\n"
        f"**نام پلن:** {plan['name']}\n"
        f"**قیمت:** {plan['price']:,} تومان\n\n"
        f"آیا تایید می‌کنید؟"
    )
    keyboard = [
        [InlineKeyboardButton("\u2705 تایید و پرداخت", callback_data="renew_confirm_purchase")],
        [InlineKeyboardButton("\U0001F381 کد تخفیف دارم", callback_data="renew_apply_discount_start")],
    ]
    keyboard = _footer(keyboard, back_callback=f"view_service_{order_id}")
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return RENEW_SELECT_PLAN


async def renew_apply_discount_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await _safe_edit_text(query.message, "لطفا کد تخفیف خود را برای تمدید وارد کنید:")
    return RENEW_AWAIT_DISCOUNT_CODE


async def receive_renewal_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    photo_file_id = update.message.photo[-1].file_id
    plan_id = context.user_data.get('selected_renewal_plan_id')
    order_id = context.user_data.get('renewing_order_id')
    final_price = context.user_data.get('final_price')
    discount_code = context.user_data.get('discount_code')

    if not all([plan_id, order_id, final_price is not None]):
        await update.message.reply_text("خطا در فرآیند تمدید. لطفا مجددا تلاش کنید.")
        from ..handlers.common import start_command
        await start_command(update, context)
        return ConversationHandler.END

    original_order = query_db("SELECT marzban_username FROM orders WHERE id = ?", (order_id,), one=True)
    if not original_order:
        await update.message.reply_text("خطا در یافتن سفارش اصلی. لطفا با پشتیبانی تماس بگیرید.")
        return ConversationHandler.END

    plan = query_db("SELECT * FROM plans WHERE id = ?", (plan_id,), one=True)

    # Auto-process renewal immediately (no admin approval)
    try:
        ok, msg = await process_renewal_for_order(order_id, plan_id, context)
        if ok:
            if discount_code:
                execute_db("UPDATE discount_codes SET times_used = times_used + 1 WHERE code = ?", (discount_code,))
            
            # Beautiful success message
            success_message = (
                "🎉 <b>تبریک! تمدید با موفقیت انجام شد!</b>\n\n"
                f"✨ سرویس شما با موفقیت تمدید شد و آماده استفاده است.\n\n"
                f"📦 <b>پلن انتخابی:</b> {plan.get('name', 'نامشخص') if plan else 'نامشخص'}\n"
                f"⏰ <b>مدت افزوده شده:</b> {plan.get('duration_days', 0) if plan else 0} روز\n"
                f"📊 <b>حجم اضافه شده:</b> {plan.get('traffic_gb', 0) if plan else 0} GB\n"
                f"💰 <b>مبلغ پرداخت شده:</b> {final_price:,} تومان\n\n"
                "🚀 <b>سرویس شما اکنون فعال است!</b>\n"
                "می‌توانید از سرعت و کیفیت بالای اتصال لذت ببرید.\n\n"
                "💡 <b>نکته:</b> برای مشاهده لینک اتصال و جزئیات کامل، به بخش «سرویس‌های من» مراجعه کنید."
            )
            
            keyboard = [
                [InlineKeyboardButton("📱 سرویس‌های من", callback_data='my_services')],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data='start_main')]
            ]
            
            await update.message.reply_text(
                success_message,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Send additional confirmation message to user
            try:
                confirmation_text = (
                    f"✅ <b>تأیید تمدید سرویس</b>\n\n"
                    f"تمدید سرویس شما با موفقیت انجام شد.\n\n"
                    f"🔢 شماره سفارش: #{order_id}\n"
                    f"📦 پلن: {plan.get('name', 'نامشخص') if plan else 'نامشخص'}\n"
                    f"⏰ مدت: {plan.get('duration_days', 0) if plan else 0} روز\n"
                    f"📊 حجم: {plan.get('traffic_gb', 0) if plan else 0} GB\n"
                    f"💰 مبلغ: {final_price:,} تومان\n\n"
                    f"🎉 از اعتماد شما سپاسگزاریم!"
                )
                await context.bot.send_message(
                    chat_id=user.id,
                    text=confirmation_text,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Failed to send renewal confirmation: {e}")
            
            # Send renewal notification to admin
            try:
                plan_name = plan.get('name', 'نامشخص') if plan else 'نامشخص'
                await send_renewal_log(context.bot, order_id, user.id, plan_name, final_price, payment_method="رسید")
            except Exception:
                pass
        else:
            # Beautiful error message
            error_message = (
                "❌ <b>خطا در تمدید سرویس</b>\n\n"
                f"متأسفانه تمدید سرویس شما با خطا مواجه شد:\n\n"
                f"🔴 <b>دلیل خطا:</b> {msg}\n\n"
                "💡 لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
            )
            
            keyboard = [
                [InlineKeyboardButton("🔄 تلاش مجدد", callback_data=f'renew_service_{order_id}')],
                [InlineKeyboardButton("📱 سرویس‌های من", callback_data='my_services')],
                [InlineKeyboardButton("💬 پشتیبانی", callback_data='support_menu')]
            ]
            
            await update.message.reply_text(
                error_message,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            try:
                await notify_admins(context.bot, text=(f"[Renew failed] order #{order_id} plan_id={plan_id}\n{msg}"), parse_mode=ParseMode.HTML)
            except Exception:
                pass
    except Exception as e:
        # Beautiful exception message
        exception_message = (
            "⚠️ <b>خطای سیستمی</b>\n\n"
            "متأسفانه در هنگام تمدید سرویس خطای غیرمنتظره‌ای رخ داد.\n\n"
            "✅ این خطا به تیم پشتیبانی اطلاع داده شد.\n\n"
            "💡 لطفاً چند دقیقه دیگر مجدداً تلاش کنید."
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 تلاش مجدد", callback_data=f'renew_service_{order_id}')],
            [InlineKeyboardButton("💬 پشتیبانی", callback_data='support_menu')],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data='start_main')]
        ]
        
        await update.message.reply_text(
            exception_message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        try:
            await notify_admins(context.bot, text=(f"[Renew exception] order #{order_id} plan_id={plan_id}\n{e}"))
        except Exception:
            pass
    context.user_data.pop('awaiting', None)
    clear_flow(context)
    from ..handlers.common import start_command
    context.user_data['suppress_join_log'] = True
    await start_command(update, context)
    return ConversationHandler.END


async def process_renewal_for_order(order_id: int, plan_id: int, context: ContextTypes.DEFAULT_TYPE):
    order = query_db("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
    plan = query_db("SELECT * FROM plans WHERE id = ?", (plan_id,), one=True)
    if not order or not plan:
        return False, "سفارش یا پلن یافت نشد"
    if not order.get('panel_id'):
        return False, "پنل این سرویس مشخص نیست"
    api = VpnPanelAPI(panel_id=order['panel_id'])
    marz_username = order.get('marzban_username')
    if not marz_username:
        return False, "نام کاربری سرویس ثبت نشده است"
    # For 3x-UI, renew on the same inbound id used at creation
    panel_type = (query_db("SELECT panel_type FROM panels WHERE id = ?", (order['panel_id'],), one=True) or {}).get('panel_type', '').lower()
    if panel_type in ('3xui','3x-ui','3x ui'):
        inbound_id = int(order.get('xui_inbound_id') or 0)
        add_gb, add_days = _get_additions_from_plan(plan)

        if inbound_id:
            logger.info(f"Processing renewal for {marz_username}: add_gb={add_gb}, add_days={add_days}, inbound={inbound_id}")

            # Recreate-only to avoid updateClient 404s; fallback to panel-level renew
            renewed_user, message = None, None
            if hasattr(api, 'renew_by_recreate_on_inbound'):
                renewed_user, message = api.renew_by_recreate_on_inbound(inbound_id, marz_username, add_gb, add_days)
                logger.info(f"renew_by_recreate_on_inbound result: success={bool(renewed_user)} msg={message}")

            if not renewed_user:
                logger.info("Fallback to renew_user_on_inbound")
                renewed_user, message = api.renew_user_on_inbound(inbound_id, marz_username, add_gb, add_days)
                logger.info(f"renew_user_on_inbound result: success={bool(renewed_user)} msg={message}")
        else:
            inbound_id = _find_inbound_id(api, marz_username) or 0
            if inbound_id:
                execute_db("UPDATE orders SET xui_inbound_id = ? WHERE id = ?", (inbound_id, order_id))
                logger.info(f"Found inbound {inbound_id} for {marz_username} via search; persisted for future renewals")

                renewed_user, message = api.renew_by_recreate_on_inbound(inbound_id, marz_username, add_gb, add_days)
                if not renewed_user:
                    renewed_user, message = api.renew_user_on_inbound(inbound_id, marz_username, add_gb, add_days)
            else:
                logger.warning(f"No inbound found for {marz_username}; falling back to panel-level renew")
                renewed_user, message = await api.renew_user_in_panel(marz_username, plan)
    elif panel_type in ('3xui','3x-ui','3x ui','xui','x-ui','sanaei','alireza','txui','tx-ui','tx ui'):
        inbound_id = int(order.get('xui_inbound_id') or 0)
        add_gb, add_days = _get_additions_from_plan(plan)

        if inbound_id:
            logger.info(f"[ELIF] Processing renewal for {marz_username}: add_gb={add_gb}, add_days={add_days}, inbound={inbound_id}")

            # Recreate-only for X-UI/3x-UI/TX-UI to avoid 404 update endpoints
            renewed_user, message = None, None
            if hasattr(api, 'renew_by_recreate_on_inbound'):
                renewed_user, message = api.renew_by_recreate_on_inbound(inbound_id, marz_username, add_gb, add_days)
                logger.info(f"[ELIF] renew_by_recreate_on_inbound result: success={bool(renewed_user)} msg={message}")

            if not renewed_user:
                logger.info("[ELIF] Fallback to renew_user_on_inbound")
                renewed_user, message = api.renew_user_on_inbound(inbound_id, marz_username, add_gb, add_days)
                logger.info(f"[ELIF] renew_user_on_inbound result: success={bool(renewed_user)} msg={message}")
        else:
            inbound_id = _find_inbound_id(api, marz_username) or 0
            if inbound_id:
                execute_db("UPDATE orders SET xui_inbound_id = ? WHERE id = ?", (inbound_id, order_id))
                logger.info(f"[ELIF] Found inbound {inbound_id} for {marz_username} via search; persisted for future renewals")

                renewed_user, message = api.renew_by_recreate_on_inbound(inbound_id, marz_username, add_gb, add_days)
                if not renewed_user:
                    renewed_user, message = api.renew_user_on_inbound(inbound_id, marz_username, add_gb, add_days)
            else:
                logger.warning(f"[ELIF] No inbound found for {marz_username}; falling back to panel-level renew")
                renewed_user, message = await api.renew_user_in_panel(marz_username, plan)
    else:
        renewed_user, message = await api.renew_user_in_panel(marz_username, plan)
    if renewed_user:
        # Persist new client id if present (for 3x-UI/X-UI recreate paths)
        try:
            new_cid = renewed_user.get('id') or renewed_user.get('uuid')
            if new_cid:
                execute_db("UPDATE orders SET xui_client_id = ? WHERE id = ?", (new_cid, order_id))
        except Exception:
            pass
        try:
            # Only reset usage counters for Marzban-like panels; X-UI/3x-UI/TX-UI recreate already resets usage
            xui_types = ('3xui','3x-ui','3x ui','xui','x-ui','sanaei','alireza','txui','tx-ui','tx ui')
            if panel_type not in xui_types:
                _ = await api.reset_user_traffic(marz_username)
        except Exception:
            pass
        return True, "Success"
    try:
        from ..config import logger as _logger
        _logger.error(f"Renew failed for order {order_id} (panel {order['panel_id']} type {panel_type}): {message}")
    except Exception:
        pass
    return False, message
