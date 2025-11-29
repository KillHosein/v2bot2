"""Admin actions for user services (renew/delete)"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..db import query_db, execute_db
from ..panel import VpnPanelAPI
from ..states import ADMIN_USERS_MENU
from ..helpers.tg import safe_edit_text as _safe_edit_text
from ..config import logger


async def admin_service_renew_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask admin to confirm service renewal"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    order_id = int(parts[3])
    uid = int(parts[4])
    
    # Get service details
    order = query_db(
        """SELECT o.id, o.plan_id, o.user_id, o.marzban_username, o.panel_id,
           p.name as plan_name, p.duration_days, p.traffic_gb
           FROM orders o
           LEFT JOIN plans p ON p.id = o.plan_id
           WHERE o.id = ?""",
        (order_id,),
        one=True
    )
    
    if not order:
        await _safe_edit_text(query.message, "❌ سرویس یافت نشد.")
        return ADMIN_USERS_MENU
    
    text = (
        f"🔁 <b>تمدید سرویس توسط ادمین</b>\n\n"
        f"سرویس #{order_id}\n"
        f"کاربر: {uid}\n"
        f"پلن: {order.get('plan_name')}\n"
        f"مدت: {order.get('duration_days')} روز\n"
        f"حجم: {order.get('traffic_gb')} GB\n\n"
        f"آیا مطمئن هستید؟"
    )
    
    kb = [
        [
            InlineKeyboardButton("✅ تایید", callback_data=f"admin_service_renew_yes_{order_id}_{uid}"),
            InlineKeyboardButton("❌ انصراف", callback_data=f"admin_user_services_{uid}")
        ]
    ]
    
    await _safe_edit_text(query.message, text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_USERS_MENU


async def admin_service_renew_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute service renewal by admin"""
    query = update.callback_query
    await query.answer("در حال تمدید...")
    
    parts = query.data.split('_')
    order_id = int(parts[4])
    uid = int(parts[5])
    
    try:
        # Get service and plan details
        order = query_db(
            """SELECT o.*, p.duration_days, p.traffic_gb
               FROM orders o
               LEFT JOIN plans p ON p.id = o.plan_id
               WHERE o.id = ?""",
            (order_id,),
            one=True
        )
        
        if not order:
            await _safe_edit_text(query.message, "❌ سرویس یافت نشد.")
            return ADMIN_USERS_MENU
        
        # Renew on panel
        panel_api = VpnPanelAPI(panel_id=order['panel_id'])
        success, msg = await panel_api.renew_user(
            username=order['marzban_username'],
            add_days=order.get('duration_days', 30),
            add_gb=order.get('traffic_gb', 0)
        )
        
        if success:
            # Update expiry date in database
            from datetime import datetime, timedelta
            new_expiry = datetime.now() + timedelta(days=order.get('duration_days', 30))
            execute_db(
                "UPDATE orders SET expiry_date = ? WHERE id = ?",
                (new_expiry.strftime('%Y-%m-%d'), order_id)
            )
            
            # Log admin action
            try:
                execute_db(
                    "INSERT INTO admin_audit (admin_id, action, target, created_at, meta) VALUES (?, ?, ?, datetime('now','localtime'), ?)",
                    (query.from_user.id, 'renew_service', str(order_id), f"user_id={uid}")
                )
            except Exception:
                pass
            
            text = (
                f"✅ <b>تمدید موفق</b>\n\n"
                f"سرویس #{order_id} با موفقیت تمدید شد.\n"
                f"کاربر: {uid}\n"
                f"مدت اضافه شده: {order.get('duration_days')} روز\n"
                f"حجم اضافه شده: {order.get('traffic_gb')} GB"
            )
            
            # Notify user
            try:
                user_msg = (
                    f"🎉 <b>تمدید سرویس</b>\n\n"
                    f"سرویس شما توسط مدیر تمدید شد!\n\n"
                    f"سرویس #{order_id}\n"
                    f"مدت: {order.get('duration_days')} روز\n"
                    f"حجم: {order.get('traffic_gb')} GB"
                )
                await context.bot.send_message(uid, user_msg, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(f"Failed to notify user {uid}: {e}")
        else:
            text = f"❌ <b>خطا در تمدید</b>\n\n{msg}"
        
        kb = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_user_services_{uid}")]]
        await _safe_edit_text(query.message, text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        
    except Exception as e:
        logger.error(f"Admin renew error: {e}")
        await _safe_edit_text(
            query.message,
            f"❌ خطا: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_user_services_{uid}")]])
        )
    
    return ADMIN_USERS_MENU


async def admin_service_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask admin to confirm service deletion"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    order_id = int(parts[3])
    uid = int(parts[4])
    
    text = (
        f"🗑 <b>حذف سرویس</b>\n\n"
        f"⚠️ <b>هشدار:</b> این عمل غیرقابل بازگشت است!\n\n"
        f"سرویس #{order_id} از پنل و دیتابیس حذف خواهد شد.\n\n"
        f"آیا مطمئن هستید؟"
    )
    
    kb = [
        [
            InlineKeyboardButton("✅ بله، حذف شود", callback_data=f"admin_service_delete_yes_{order_id}_{uid}"),
            InlineKeyboardButton("❌ انصراف", callback_data=f"admin_user_services_{uid}")
        ]
    ]
    
    await _safe_edit_text(query.message, text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_USERS_MENU


async def admin_service_delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute service deletion by admin"""
    query = update.callback_query
    await query.answer("در حال حذف...")
    
    parts = query.data.split('_')
    order_id = int(parts[4])
    uid = int(parts[5])
    
    try:
        # Get service details
        order = query_db("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
        
        if not order:
            await _safe_edit_text(query.message, "❌ سرویس یافت نشد.")
            return ADMIN_USERS_MENU
        
        # Delete from panel
        try:
            panel_api = VpnPanelAPI(panel_id=order['panel_id'])
            await panel_api.delete_user(username=order['marzban_username'])
        except Exception as e:
            logger.error(f"Failed to delete from panel: {e}")
        
        # Delete from database (or mark as deleted)
        execute_db("UPDATE orders SET status = 'deleted' WHERE id = ?", (order_id,))
        
        # Log admin action
        try:
            execute_db(
                "INSERT INTO admin_audit (admin_id, action, target, created_at, meta) VALUES (?, ?, ?, datetime('now','localtime'), ?)",
                (query.from_user.id, 'delete_service', str(order_id), f"user_id={uid}")
            )
        except Exception:
            pass
        
        text = f"✅ <b>حذف موفق</b>\n\nسرویس #{order_id} حذف شد."
        
        # Notify user
        try:
            user_msg = f"ℹ️ <b>اطلاعیه</b>\n\nسرویس #{order_id} شما توسط مدیر حذف شد."
            await context.bot.send_message(uid, user_msg, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to notify user {uid}: {e}")
        
        kb = [[InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_user_services_{uid}")]]
        await _safe_edit_text(query.message, text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
        
    except Exception as e:
        logger.error(f"Admin delete error: {e}")
        await _safe_edit_text(
            query.message,
            f"❌ خطا: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_user_services_{uid}")]])
        )
    
    return ADMIN_USERS_MENU
