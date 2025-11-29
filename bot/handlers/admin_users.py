from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import io
import csv

from ..db import query_db, execute_db
from ..states import ADMIN_USERS_MENU, ADMIN_USERS_AWAIT_SEARCH
from ..helpers.tg import safe_edit_text as _safe_edit_text

PAGE_SIZE = 10

def _build_users_query(search: str | None):
    base = "SELECT user_id, first_name, COALESCE(banned,0) AS banned, join_date FROM users"
    args = []
    if search:
        base += " WHERE CAST(user_id AS TEXT) LIKE ? OR (first_name IS NOT NULL AND first_name LIKE ?)"
        like = f"%{search}%"
        args = [like, like]
    base += " ORDER BY join_date DESC"
    return base, tuple(args)

async def admin_users_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.setdefault('users_search', '')
    context.user_data.setdefault('users_page', 1)
    return await admin_users_page(update, context)

async def admin_users_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    page = 1
    if query and query.data.startswith('admin_users_page_'):
        try:
            page = int(query.data.split('_')[-1])
        except Exception:
            page = 1
        context.user_data['users_page'] = page
    else:
        page = context.user_data.get('users_page', 1)

    search = context.user_data.get('users_search', '')
    sql, args = _build_users_query(search)
    rows = query_db(sql, args) or []
    total = len(rows)
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    slice_rows = rows[start:end]

    text = "👥 مدیریت کاربران\n\n"
    if search:
        text += f"جستجو: `{search}`\n\n"
    if not slice_rows:
        text += "کاربری یافت نشد."
    else:
        for r in slice_rows:
            status = 'مسدود' if int(r.get('banned') or 0) == 1 else 'عادی'
            text += f"- `{r['user_id']}` | {r.get('first_name') or '-'} | {status}\n"
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    kb = []
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin_users_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"admin_users_page_{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("🔎 جستجو", callback_data="admin_users_search"), InlineKeyboardButton("📤 خروجی CSV", callback_data="admin_users_export")])
    kb.append([InlineKeyboardButton("👁️‍🗨️ مشاهده کاربر (با آیدی)", callback_data=f"admin_user_view_prompt"), InlineKeyboardButton("🔁 تغییر وضعیت بن کاربر (با آیدی)", callback_data=f"admin_user_toggle_0")])
    kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_main")])
    await _safe_edit_text(query.message, text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_USERS_MENU

async def admin_users_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await _safe_edit_text(query.message, "عبارت جستجو را ارسال کنید (نام یا آیدی):")
    return ADMIN_USERS_AWAIT_SEARCH

async def admin_users_search_apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    term = (update.message.text or '').strip()
    context.user_data['users_search'] = term
    context.user_data['users_page'] = 1
    fake_query = type('obj', (object,), {'data': 'admin_users_menu', 'message': update.message, 'answer': (lambda *a, **k: None)})
    fake_update = type('obj', (object,), {'callback_query': fake_query})
    return await admin_users_menu(fake_update, context)

async def admin_users_toggle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    # Ask admin to reply with a user id to toggle
    await _safe_edit_text(query.message, "آیدی عددی کاربری که می‌خواهید بن/آنبن کنید را ارسال کنید:")
    context.user_data['awaiting_admin'] = 'toggle_ban_user'
    return ADMIN_USERS_MENU

async def admin_users_export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    search = context.user_data.get('users_search', '')
    sql, args = _build_users_query(search)
    rows = query_db(sql, args) or []
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['user_id', 'first_name', 'banned', 'join_date'])
    for r in rows:
        writer.writerow([r.get('user_id'), r.get('first_name') or '', int(r.get('banned') or 0), r.get('join_date') or ''])
    data = buf.getvalue().encode('utf-8')
    bio = io.BytesIO(data)
    bio.name = 'users.csv'
    await query.message.reply_document(document=InputFile(bio, filename='users.csv'), caption='CSV کاربران')
    return ADMIN_USERS_MENU


async def admin_users_view_by_id_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['awaiting_admin'] = 'view_user'
    await _safe_edit_text(query.message, "آیدی عددی کاربر را ارسال کنید:")
    return ADMIN_USERS_MENU


async def admin_users_view_by_id_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin_user_view_{uid} callback"""
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split('_')[-1])
    # Create fake update for compatibility
    fake_update = type('obj', (object,), {'message': query.message, 'effective_user': query.from_user})
    return await admin_users_view_by_id_show(fake_update, context, uid)

async def admin_users_view_by_id_show(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: int) -> int:
    u = query_db("SELECT user_id, first_name, COALESCE(banned,0) AS banned, join_date FROM users WHERE user_id = ?", (uid,), one=True)
    if not u:
        await update.message.reply_text("کاربر یافت نشد.")
        return ADMIN_USERS_MENU
    banned = int(u.get('banned') or 0) == 1
    # Aggregates
    orders_total = (query_db("SELECT COUNT(*) AS c FROM orders WHERE user_id = ?", (uid,), one=True) or {}).get('c', 0)
    orders_active = (query_db("SELECT COUNT(*) AS c FROM orders WHERE user_id = ? AND status='approved'", (uid,), one=True) or {}).get('c', 0)
    last_order = (query_db("SELECT MAX(timestamp) AS ts FROM orders WHERE user_id = ?", (uid,), one=True) or {}).get('ts', '-')
    wallet = (query_db("SELECT balance FROM user_wallets WHERE user_id = ?", (uid,), one=True) or {}).get('balance', 0)
    tickets_open = (query_db("SELECT COUNT(*) AS c FROM tickets WHERE user_id = ? AND status='pending'", (uid,), one=True) or {}).get('c', 0)
    refs = (query_db("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?", (uid,), one=True) or {}).get('c', 0)

    text = (
        f"👤 کاربر: `{u['user_id']}` | {u.get('first_name') or '-'}\n"
        f"وضعیت: {'مسدود' if banned else 'عادی'}\n"
        f"تاریخ عضویت: {u.get('join_date') or '-'}\n\n"
        f"سفارش‌ها: {int(orders_total)} | فعال: {int(orders_active)}\n"
        f"آخرین سفارش: {last_order or '-'}\n"
        f"کیف پول: {int(wallet):,} تومان\n"
        f"تیکت‌های باز: {int(tickets_open)}\n"
        f"زیرمجموعه‌ها: {int(refs)}\n"
    )
    kb = [
        [InlineKeyboardButton("📦 سرویس‌ها", callback_data=f"admin_user_services_{uid}"), InlineKeyboardButton("🎫 تیکت‌ها", callback_data=f"admin_user_tickets_{uid}")],
        [InlineKeyboardButton("💳 کیف پول", callback_data=f"admin_user_wallet_{uid}"), InlineKeyboardButton("👥 ارجاع‌ها", callback_data=f"admin_user_refs_{uid}")],
        [InlineKeyboardButton(("آنبن" if banned else "بن"), callback_data=f"admin_user_ban_{uid}")],
        [InlineKeyboardButton("بازگشت", callback_data="admin_users_menu")],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)
    return ADMIN_USERS_MENU


async def admin_users_toggle_ban_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split('_')
    # admin_user_ban_<uid> or admin_user_ban_yes_<uid> or admin_user_ban_no_<uid>
    if parts[-2] in ('yes', 'no'):
        decision = parts[-2]
        uid = int(parts[-1])
        if decision == 'no':
            # Re-render detail
            fake_update = type('obj', (object,), {'message': query.message, 'effective_user': query.from_user})
            return await admin_users_view_by_id_show(fake_update, context, uid)
    else:
        uid = int(parts[-1])
        # Ask for confirmation
        await _safe_edit_text(query.message, f"تغییر وضعیت بن برای کاربر `{uid}`؟", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("تایید", callback_data=f"admin_user_ban_yes_{uid}"), InlineKeyboardButton("انصراف", callback_data=f"admin_user_ban_no_{uid}")]
        ]))
        return ADMIN_USERS_MENU
    row = query_db("SELECT COALESCE(banned,0) AS banned FROM users WHERE user_id=?", (uid,), one=True)
    if not row:
        await _safe_edit_text(query.message, "کاربر یافت نشد.")
        return ADMIN_USERS_MENU
    newv = 0 if int(row.get('banned') or 0) == 1 else 1
    execute_db("UPDATE users SET banned = ? WHERE user_id = ?", (newv, uid))
    try:
        execute_db(
            "INSERT INTO admin_audit (admin_id, action, target, created_at, meta) VALUES (?, ?, ?, datetime('now','localtime'), ?)",
            (update.effective_user.id, 'toggle_ban', str(uid), None)
        )
    except Exception:
        pass
    # Re-render detail view
    fake_update = type('obj', (object,), {'message': query.message, 'effective_user': query.from_user})
    await _safe_edit_text(query.message, "در حال بروزرسانی...")
    return await admin_users_view_by_id_show(fake_update, context, uid)


def _paginate(items, page: int, size: int):
    total = len(items)
    start = max(0, (page - 1) * size)
    end = start + size
    return items[start:end], total


async def admin_users_show_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    uid = int(parts[-1]) if parts[-2] != 'page' else int(parts[-3])
    page = int(parts[-1]) if parts[-2] == 'page' else 1
    
    # Debug logging
    from ..config import logger
    logger.info(f"[admin_users_show_services] callback_data={query.data}, parsed uid={uid}, page={page}")
    
    rows = query_db(
        """SELECT o.id, o.plan_id, o.status, o.marzban_username, o.panel_type, o.timestamp,
           p.name as plan_name, p.price, p.duration_days, p.traffic_gb
           FROM orders o
           LEFT JOIN plans p ON p.id = o.plan_id
           WHERE o.user_id = ?
           ORDER BY o.id DESC""",
        (uid,)
    ) or []
    
    logger.info(f"[admin_users_show_services] Found {len(rows)} orders for user {uid}")
    if not rows:
        # Store user_id for re-displaying user details on back
        context.user_data['viewing_user_id'] = uid
        kb = [
            [InlineKeyboardButton("🔄 تلاش مجدد", callback_data=f"admin_user_services_{uid}")],
            [InlineKeyboardButton("🔙 بازگشت به کاربر", callback_data=f"admin_user_view_{uid}")],
            [InlineKeyboardButton("🏠 منوی ادمین", callback_data="admin_main")]
        ]
        await _safe_edit_text(
            query.message,
            f"📦 <b>سرویس‌های کاربر {uid}</b>\n\n"
            f"❌ هیچ سرویسی برای این کاربر یافت نشد.\n\n"
            f"💡 ممکن است کاربر هنوز سفارشی نداشته باشد.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return ADMIN_USERS_MENU
    
    page_rows, total = _paginate(rows, page, 5)
    text = f"📦 <b>سرویس‌های کاربر {uid}</b>\n\n"
    
    kb = []
    for r in page_rows:
        pname = r.get('plan_name') or 'نامشخص'
        status_icon = "✅" if r.get('status') == 'approved' else "⏳" if r.get('status') == 'pending' else "❌"
        price = r.get('price') or 0
        created = r.get('timestamp') or '-'
        duration = r.get('duration_days') or '-'
        traffic = r.get('traffic_gb') or '-'
        
        # Calculate expiry date from timestamp and duration
        expiry = '-'
        if created != '-' and duration != '-':
            try:
                from datetime import datetime, timedelta
                created_dt = datetime.strptime(created.split('.')[0], '%Y-%m-%d %H:%M:%S')
                expiry_dt = created_dt + timedelta(days=int(duration))
                expiry = expiry_dt.strftime('%Y-%m-%d')
            except Exception:
                expiry = f"{duration} روز از ایجاد"
        
        text += (
            f"{status_icon} <b>سرویس #{r['id']}</b>\n"
            f"• پلن: {pname}\n"
            f"• قیمت: {int(price):,} تومان\n"
            f"• مدت: {duration} روز\n"
            f"• حجم: {traffic} GB\n"
            f"• وضعیت: {r.get('status')}\n"
            f"• یوزرنیم: <code>{r.get('marzban_username') or '-'}</code>\n"
            f"• پنل: {r.get('panel_type') or '-'}\n"
            f"• تاریخ ایجاد: {created}\n"
            f"• تاریخ انقضا: {expiry}\n\n"
        )
        
        # Add buttons for each service
        service_row = [
            InlineKeyboardButton("🔁 تمدید", callback_data=f"admin_service_renew_{r['id']}_{uid}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"admin_service_delete_{r['id']}_{uid}")
        ]
        kb.append(service_row)
    
    # Pagination
    nav = []
    total_pages = max(1, (total + 5 - 1) // 5)
    if total_pages > 1:
        if page > 1:
            nav.append(InlineKeyboardButton("◀️ قبلی", callback_data=f"admin_user_services_{uid}_page_{page-1}"))
        nav.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data='noop'))
        if page < total_pages:
            nav.append(InlineKeyboardButton("▶️ بعدی", callback_data=f"admin_user_services_{uid}_page_{page+1}"))
        kb.append(nav)
    
    kb.append([InlineKeyboardButton("🔙 بازگشت به کاربر", callback_data=f"admin_user_view_{uid}")])
    await _safe_edit_text(query.message, text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_USERS_MENU


async def admin_users_show_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    uid = int(parts[-1]) if parts[-2] != 'page' else int(parts[-3])
    page = int(parts[-1]) if parts[-2] == 'page' else 1
    rows = query_db("SELECT id, status, created_at FROM tickets WHERE user_id = ? ORDER BY id DESC", (uid,)) or []
    text = "🎫 تیکت‌ها:\n\n"
    if not rows:
        text += "موردی نیست."
    else:
        page_rows, total = _paginate(rows, page, 10)
        for t in page_rows:
            text += f"- #{t['id']} | {t.get('status')} | {t.get('created_at') or ''}\n"
    nav = []
    total_pages = max(1, (len(rows) + 10 - 1) // 10)
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin_user_tickets_{uid}_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"admin_user_tickets_{uid}_page_{page+1}"))
    kb = []
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("🔙 بازگشت به کاربر", callback_data=f"admin_user_view_{uid}")])
    await _safe_edit_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_USERS_MENU


async def admin_users_show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    uid = int(parts[-1]) if parts[-2] != 'page' else int(parts[-3])
    page = int(parts[-1]) if parts[-2] == 'page' else 1
    bal = (query_db("SELECT balance FROM user_wallets WHERE user_id = ?", (uid,), one=True) or {}).get('balance', 0)
    txs = query_db("SELECT id, amount, direction, status, created_at FROM wallet_transactions WHERE user_id = ? ORDER BY id DESC", (uid,)) or []
    text = f"💳 کیف پول\n\nموجودی: {int(bal):,} تومان\n\nتراکنش‌ها:\n"
    if not txs:
        text += "موردی نیست."
    else:
        page_rows, total = _paginate(txs, page, 10)
        for t in page_rows:
            sign = '+' if (t.get('direction')=='credit') else '-'
            text += f"- #{t['id']} | {sign}{int(t.get('amount') or 0):,} | {t.get('status')} | {t.get('created_at') or ''}\n"
    nav = []
    total_pages = max(1, (len(txs) + 10 - 1) // 10)
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin_user_wallet_{uid}_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"admin_user_wallet_{uid}_page_{page+1}"))
    kb = []
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("🔙 بازگشت به کاربر", callback_data=f"admin_user_view_{uid}")])
    await _safe_edit_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_USERS_MENU


async def admin_users_show_refs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    uid = int(parts[-1]) if parts[-2] != 'page' else int(parts[-3])
    page = int(parts[-1]) if parts[-2] == 'page' else 1
    cnt = (query_db("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?", (uid,), one=True) or {}).get('c', 0)
    recent_all = query_db("SELECT referee_id, created_at FROM referrals WHERE referrer_id = ? ORDER BY created_at DESC", (uid,)) or []
    recent, total = _paginate(recent_all, page, 10)
    text = f"👥 زیرمجموعه‌ها: {int(cnt)}\n\nآخرین موارد:\n"
    if not recent:
        text += "موردی نیست."
    else:
        for r in recent:
            text += f"- {r.get('referee_id')} | {r.get('created_at') or ''}\n"
    nav = []
    total_pages = max(1, (len(recent_all) + 10 - 1) // 10)
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin_user_refs_{uid}_page_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"admin_user_refs_{uid}_page_{page+1}"))
    kb = []
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("🔙 بازگشت به کاربر", callback_data=f"admin_user_view_{uid}")])
    await _safe_edit_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_USERS_MENU
