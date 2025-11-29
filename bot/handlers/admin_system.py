"""System monitoring and maintenance commands for admin"""

import psutil
import platform
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..db import query_db, execute_db
from ..panel import VpnPanelAPI
from ..states import ADMIN_MAIN_MENU
from ..helpers.tg import safe_edit_text as _safe_edit_text

async def admin_system_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show system health and status"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # Get system info
    try:
        # Basic system info
        sys_info = {
            'os': f"{platform.system()} {platform.release()}",
            'python': platform.python_version(),
            'uptime': _format_seconds(psutil.boot_time()),
            'load_avg': ", ".join([f"{x:.2f}" for x in os.getloadavg()])
        }
        
        # Memory usage
        mem = psutil.virtual_memory()
        mem_info = {
            'total': _format_bytes(mem.total),
            'used': _format_bytes(mem.used),
            'free': _format_bytes(mem.available),
            'percent': mem.percent
        }
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_info = {
            'total': _format_bytes(disk.total),
            'used': _format_bytes(disk.used),
            'free': _format_bytes(disk.free),
            'percent': disk.percent
        }
        
        # Database info
        db_info = {
            'users': query_db("SELECT COUNT(*) as c FROM users", one=True)['c'],
            'active_services': query_db("SELECT COUNT(*) as c FROM orders WHERE status='active'", one=True)['c'],
            'pending_orders': query_db("SELECT COUNT(*) as c FROM orders WHERE status='pending'", one=True)['c']
        }
        
        # Panel status
        panels = query_db("SELECT id, name, url, panel_type, enabled FROM panels")
        panel_status = []
        for p in panels:
            try:
                api = VpnPanelAPI(panel_id=p['id'])
                online = await api.check_connection()
                status = "🟢 آنلاین" if online else "🔴 آفلاین"
            except Exception as e:
                status = f"🔴 خطا: {str(e)[:30]}"
            
            panel_status.append({
                'name': p['name'],
                'type': p['panel_type'],
                'status': status,
                'enabled': p.get('enabled', 1) == 1
            })
        
        # Build status message
        text = """
🛠️ *وضعیت سیستم*

*سیستم عامل:* {os}
*پایتون:* {python}
*آپتایم:* {uptime}
*لود سیستم:* {load_avg}

*حافظه رم:*
- کل: {mem_total}
- استفاده شده: {mem_used} ({mem_percent}%)
- آزاد: {mem_free}

*فضای دیسک:*
- کل: {disk_total}
- استفاده شده: {disk_used} ({disk_percent}%)
- آزاد: {disk_free}

*پایگاه داده:*
- کاربران: {users:,}
- سرویس‌های فعال: {active_services:,}
- سفارشات در انتظار: {pending_orders:,}

*وضعیت پنل‌ها:*
{panel_status}
""".format(
            **sys_info,
            mem_total=mem_info['total'],
            mem_used=mem_info['used'],
            mem_free=mem_info['free'],
            mem_percent=mem_info['percent'],
            disk_total=disk_info['total'],
            disk_used=disk_info['used'],
            disk_free=disk_info['free'],
            disk_percent=disk_info['percent'],
            **db_info,
            panel_status='\n'.join([
                f"- {p['name']} ({p['type']}): {'✅ ' if p['enabled'] else '❌ '}{p['status']}"
                for p in panel_status
            ]) if panel_status else "هیچ پنلی یافت نشد"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 بروزرسانی", callback_data="admin_system_health")],
            [InlineKeyboardButton("🔔 پاک‌سازی اعلان‌های هشدار", callback_data="admin_clear_notifications")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_main")]
        ]
        
        if query:
            await _safe_edit_text(
                query.message,
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
    except Exception as e:
        error_msg = f"❌ خطا در دریافت وضعیت سیستم: {str(e)}"
        if query:
            await _safe_edit_text(query.message, error_msg)
        else:
            await update.message.reply_text(error_msg)
    
    return ADMIN_MAIN_MENU

def _format_bytes(bytes_num):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} PB"

def _format_seconds(seconds):
    """Format seconds to human readable format"""
    seconds = int(datetime.now().timestamp() - seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days} روز")
    if hours > 0:
        parts.append(f"{hours} ساعت")
    if minutes > 0 and len(parts) < 2:
        parts.append(f"{minutes} دقیقه")
    if seconds > 0 and len(parts) < 2:
        parts.append(f"{seconds} ثانیه")
    
    return " و ".join(parts) if parts else "چند لحظه"


async def admin_clear_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Clear all notification flags so alerts can be resent"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Reset all notification flags
        execute_db("""
            UPDATE orders 
            SET notified_traffic_80 = 0,
                notified_traffic_95 = 0,
                notified_expiry_3d = 0,
                notified_expiry_1d = 0
            WHERE status = 'approved'
        """)
        
        # Count affected orders
        affected = query_db("SELECT COUNT(*) as c FROM orders WHERE status = 'approved'", one=True)['c']
        
        await query.answer(
            f"✅ اعلان‌های هشدار برای {affected} سرویس پاک‌سازی شد",
            show_alert=True
        )
        
        # Return to system health menu
        return await admin_system_health(update, context)
        
    except Exception as e:
        await query.answer(f"❌ خطا: {str(e)}", show_alert=True)
        return await admin_system_health(update, context)
