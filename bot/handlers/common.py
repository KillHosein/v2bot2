from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ApplicationHandlerStop

from ..config import ADMIN_ID, CHANNEL_ID, CHANNEL_USERNAME, logger
from ..db import query_db
from ..utils import register_new_user
from ..helpers.flow import get_flow
from ..helpers.keyboards import build_start_menu_keyboard
from ..helpers.tg import safe_edit_message, answer_safely


async def force_join_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	if not user:
		return
	# Bypass channel join for any admin (primary or additional)
	if user.id == ADMIN_ID:
		logger.debug(f"force_join_checker: admin {user.id} bypassed")
		return
	# Gate: if bot is OFF, block non-admins globally with a maintenance message
	try:
		active_row = query_db("SELECT value FROM settings WHERE key='bot_active'", one=True)
		bot_on = (active_row and str(active_row.get('value') or '1') == '1')
	except Exception:
		bot_on = True
	if not bot_on:
		# Allow extra admins
		try:
			extra_admin = query_db("SELECT 1 FROM admins WHERE user_id = ?", (user.id,), one=True)
			if extra_admin:
				logger.debug(f"force_join_checker: extra admin {user.id} bypassed (bot off)")
				return
		except Exception:
			pass
		# For normal users, show maintenance and stop
		try:
			mm = query_db("SELECT value FROM settings WHERE key='maintenance_message'", one=True)
			text = (mm.get('value') if mm else None) or (
                "🔧 <b>ربات در حال نگهداری است</b>\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚠️ ربات به‌طور موقت برای نگهداری و بهبود خاموش شده است.\n\n"
                "⏰ لطفاً چند لحظه دیگر مراجعه کنید.\n\n"
                "💡 از صبر و شکیبایی شما متشکریم.\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━"
            )
			if update.callback_query:
				await update.callback_query.answer("ربات موقتا خاموش است", show_alert=True)
				await update.callback_query.message.edit_text(text)
			elif update.message:
				await update.message.reply_text(text)
		except Exception:
			pass
		raise ApplicationHandlerStop
	try:
		extra_admin = query_db("SELECT 1 FROM admins WHERE user_id = ?", (user.id,), one=True)
		if extra_admin:
			logger.debug(f"force_join_checker: extra admin {user.id} bypassed")
			return
	except Exception:
		pass
	# Capture referral payload from /start before blocking join
	try:
		if update.message and update.message.text:
			parts = update.message.text.strip().split()
			if len(parts) == 2 and parts[0].lower() == '/start':
				ref_id = int(parts[1])
				if ref_id != user.id:
					context.user_data['referrer_id'] = ref_id
	except Exception:
		pass
	# Skip join check during active flows to not block message inputs
	ud = context.user_data or {}
	if ud.get('awaiting') or ud.get('awaiting_admin') or ud.get('awaiting_ticket') or get_flow(context):
		logger.debug(f"force_join_checker: skip join check for user {user.id} due to active flow flags: {list(k for k,v in ud.items() if v)}")
		return
	from ..config import CHANNEL_CHAT as _CHAT
	chat_id = _CHAT if _CHAT is not None else (CHANNEL_ID or CHANNEL_USERNAME)
	try:
		member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user.id)
		if member.status in ['member', 'administrator', 'creator']:
			return
	except TelegramError as e:
		# If we cannot verify, keep user blocked and show join info instead of allowing silently
		logger.warning(f"Could not check channel membership for {user.id}: {e}")

	# Build a visible channel hint and a reliable join link if possible
	join_url = None
	channel_hint = ""
	try:
		chat_obj = await context.bot.get_chat(chat_id=chat_id)
		uname = getattr(chat_obj, 'username', None)
		inv = getattr(chat_obj, 'invite_link', None)
		if uname:
			handle = f"@{str(uname).replace('@','')}"
			join_url = f"https://t.me/{str(uname).replace('@','')}"
			channel_hint = f"\n\nکانال: {handle}"
		elif inv:
			join_url = inv
			channel_hint = "\n\nلینک دعوت کانال در دکمه زیر موجود است."
	except Exception:
		if (CHANNEL_USERNAME or '').strip():
			handle = (CHANNEL_USERNAME or '').strip()
			if not handle.startswith('@'):
				handle = f"@{handle}"
			join_url = f"https://t.me/{handle.replace('@','')}"
			channel_hint = f"\n\nکانال: {handle}"
		elif CHANNEL_ID:
			channel_hint = f"\n\nشناسه کانال: `{CHANNEL_ID}`"

	keyboard = []
	if join_url:
		keyboard.append([InlineKeyboardButton("\U0001F195 عضویت در کانال", url=join_url)])
	keyboard.append([InlineKeyboardButton("\u2705 عضو شدم", callback_data="check_join")])
	text = (
        f"🔐 **الزام عضویت در کانال**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 سلام! برای استفاده از ربات:\n\n"
        f"1️⃣ ابتدا در کانال ما عضو شوید\n"
        f"2️⃣ سپس دکمه «✅ عضو شدم» را بزنید\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━" + channel_hint
    )
	logger.info(f"force_join_checker: blocking user {user.id} with join gate")
	if update.callback_query:
		await update.callback_query.message.edit_text(
			text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN
		)
		await update.callback_query.answer("❌ شما هنوز در کانال عضو نیستید! لطفاً ابتدا عضو شوید.", show_alert=True)
	elif update.message:
		await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
	raise ApplicationHandlerStop


async def send_dynamic_message(update: Update, context: ContextTypes.DEFAULT_TYPE, message_name: str, back_to: str = 'start_main'):
	query = update.callback_query

	message_data = query_db("SELECT text, file_id, file_type FROM messages WHERE message_name = ?", (message_name,), one=True)
	if not message_data:
		await answer_safely(query, f"محتوای '{message_name}' یافت نشد!", show_alert=True)
		return
	
	# Answer callback query immediately to prevent timeout
	await answer_safely(query)

	text = message_data.get('text')
	file_id = message_data.get('file_id')
	file_type = message_data.get('file_type')

	buttons_data = query_db(
		"SELECT text, target, is_url, row, col FROM buttons WHERE menu_name = ? ORDER BY row, col",
		(message_name,),
	)

	if message_name == 'start_main':
		trial_status = query_db("SELECT value FROM settings WHERE key = 'free_trial_status'", one=True)
		if not trial_status or trial_status.get('value') != '1':
			buttons_data = [b for b in buttons_data if b.get('target') != 'get_free_config']

	keyboard = []
	if buttons_data:
		max_row = max((b['row'] for b in buttons_data), default=0) if buttons_data else 0
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

	if message_name == 'start_main':
		# For start_main, the dynamic keyboard builder handles everything
		reply_markup = build_start_menu_keyboard()
	else:
		keyboard.append([InlineKeyboardButton("\U0001F519 بازگشت", callback_data=back_to)])
		reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None


	try:
		if file_id or (query.message and (query.message.photo or query.message.video or query.message.document)):
			try:
				await query.message.delete()
			except Exception:
				pass  # Ignore if message already deleted
			if file_id:
				sender = getattr(context.bot, f"send_{file_type}", None)
				if sender:
					payload = {file_type: file_id}
					await sender(
						chat_id=query.message.chat_id,
						**payload,
						caption=text,
						reply_markup=reply_markup,
						parse_mode=ParseMode.MARKDOWN,
					)
				else:
					await context.bot.send_message(
						chat_id=query.message.chat_id,
						text=text or '',
						reply_markup=reply_markup,
						parse_mode=ParseMode.MARKDOWN,
					)
			else:
				await context.bot.send_message(
					chat_id=query.message.chat_id,
					text=text,
					reply_markup=reply_markup,
					parse_mode=ParseMode.MARKDOWN,
				)
		else:
			# Use safe edit with callback already answered
			await safe_edit_message(query, text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN, answer_callback=False)
	except TelegramError as e:
		# Fallback: if original message cannot be edited (e.g., deleted), send a new message instead
		msg = str(e)
		if 'Message is not modified' in msg:
			# benign, ignore
			return
		if 'Message to edit not found' in msg or 'message to edit not found' in msg:
			try:
				await context.bot.send_message(
					chat_id=query.message.chat_id,
					text=text or '',
					reply_markup=reply_markup,
					parse_mode=ParseMode.MARKDOWN,
				)
				return
			except Exception:
				pass
		# Log other errors
		logger.error(f"Error handling dynamic message: {e}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"start_command by user {update.effective_user.id}")
    
    # Check if user is banned
    user_check = query_db("SELECT COALESCE(banned,0) AS banned FROM users WHERE user_id = ?", (update.effective_user.id,), one=True)
    if user_check and int(user_check.get('banned', 0)) == 1:
        banned_message = (
            "🚫 <b>دسترسی مسدود شده است</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "❌ متأسفانه دسترسی شما به این ربات مسدود شده است.\n\n"
            "📞 برای اطلاعات بیشتر لطفاً با پشتیبانی تماس بگیرید.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        if update.message:
            await update.message.reply_text(banned_message, parse_mode=ParseMode.HTML)
        return
    
    # Check if user already exists (to send join log only once)
    user_existed = query_db("SELECT 1 FROM users WHERE user_id = ?", (update.effective_user.id,), one=True)
    await register_new_user(update.effective_user, update, referrer_hint=context.user_data.get('referrer_id'))
    # Optional: send join/start logs to admin-defined chat (skip if suppressed by flow OR user already existed)
    try:
        if not context.user_data.pop('suppress_join_log', False) and not user_existed:
            st = query_db("SELECT key, value FROM settings WHERE key IN ('join_logs_enabled','join_logs_chat_id')") or []
            kv = {r['key']: r['value'] for r in st}
            if (kv.get('join_logs_enabled') or '0') == '1':
                raw = (kv.get('join_logs_chat_id') or '').strip()
                chat_ident = raw if raw.startswith('@') else (int(raw) if (raw and raw.lstrip('-').isdigit()) else 0)
                if chat_ident:
                    u = update.effective_user
                    uname = f"@{u.username}" if getattr(u, 'username', None) else f"{u.first_name or ''} {u.last_name or ''}".strip()
                    from datetime import datetime
                    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    text = f"👤 ورود کاربر به ربات\nID: `{u.id}`\nنام: {uname or '-'}\nزمان: `{ts}`"
                    try:
                        await context.bot.send_message(chat_id=chat_ident, text=text, parse_mode=ParseMode.MARKDOWN)
                    except Exception as e:
                        try:
                            logger.warning(f"join log send failed to '{raw}' ({chat_ident}): {e}")
                        except Exception:
                            pass
                        # Fallback to primary admin DM
                        try:
                            await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode=ParseMode.MARKDOWN)
                        except Exception:
                            pass
                else:
                    # No valid chat configured -> send to primary admin
                    u = update.effective_user
                    uname = f"@{u.username}" if getattr(u, 'username', None) else f"{u.first_name or ''} {u.last_name or ''}".strip()
                    from datetime import datetime
                    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    text = f"👤 ورود کاربر به ربات\nID: `{u.id}`\nنام: {uname or '-'}\nزمان: `{ts}`"
                    try:
                        await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        pass
    except Exception:
        pass
    context.user_data.clear()

    sender = None
    if update.callback_query:
        sender = None
    elif update.message:
        sender = update.message.reply_text

    if not sender:
        pass

    message_data = query_db("SELECT text FROM messages WHERE message_name = 'start_main'", one=True)
    text = message_data.get('text') if message_data else "خوش آمدید!"

    reply_markup = build_start_menu_keyboard()

    if update.callback_query:
        await safe_edit_message(update.callback_query, text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN, answer_callback=True)
    else:
        await sender(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        # Provide a persistent /start reply keyboard as a static bot button
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=" ",
                reply_markup=ReplyKeyboardMarkup([[KeyboardButton("/start")]], resize_keyboard=True, one_time_keyboard=False)
            )
        except Exception:
            pass


async def dynamic_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	query = update.callback_query
	message_name = query.data

	# Skip callbacks that are handled by stateful flows (e.g., purchase flow) or special screens
	# Otherwise, this handler would re-edit the same message and override their UI
	if message_name in ('buy_config_main', 'admin_stats'):
		return

	# First, check if the callback data corresponds to a dynamic message.
	# This is safer than a blacklist of prefixes.
	if query_db("SELECT 1 FROM messages WHERE message_name = ?", (message_name,), one=True):
		await send_dynamic_message(update, context, message_name=message_name, back_to='start_main')
		# Stop further handlers from processing this update
		raise ApplicationHandlerStop

	# If it's not a dynamic message, just return and let other handlers (with more specific patterns) process it.
	return


async def unhandled_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        data = (query.data or '') if query else ''
        from ..config import logger
        try:
            logger.warning(f"Unhandled callback: '{data}' from user {query.from_user.id if query and query.from_user else 'unknown'}")
        except Exception:
            pass
        # Show a friendly fallback with a Main Menu button
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data='start_main')]])
        if query and query.message:
            try:
                await query.answer()
            except Exception:
                pass
            try:
                await query.message.reply_text(
                    "⚠️ <b>دکمه نامعتبر</b>\n\n"
                    "این دکمه در دسترس نیست یا منقضی شده است.\n\n"
                    "🏠 لطفاً از منوی اصلی استفاده کنید.",
                    reply_markup=kb,
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                try:
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text="⚠️ <b>دکمه نامعتبر</b>\n\nاین دکمه در دسترس نیست یا منقضی شده است.\n\n🏠 لطفاً از منوی اصلی استفاده کنید.",
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass
    except Exception:
        pass