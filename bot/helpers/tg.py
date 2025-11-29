from telegram.error import BadRequest, TelegramError
from ..db import query_db
from ..config import ADMIN_ID, logger


async def safe_edit_message(query, text, reply_markup=None, parse_mode=None, answer_callback=True):
    """Safely edit message from callback query with automatic callback answering"""
    # Answer callback query first to prevent timeout
    if answer_callback and hasattr(query, 'answer'):
        await answer_safely(query)
    
    try:
        message = query.message if hasattr(query, 'message') else query
        return await safe_edit_text(message, text, reply_markup, parse_mode)
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")
        # Try to send a new message as fallback
        try:
            if hasattr(query, 'message') and hasattr(query.message, 'chat'):
                bot = query.message.get_bot()
                return await bot.send_message(
                    chat_id=query.message.chat.id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
        except Exception:
            pass
        return None


async def safe_edit_text(message, text, reply_markup=None, parse_mode=None):
    # Log outgoing request details for troubleshooting
    try:
        import traceback
        kb_summary = None
        try:
            if reply_markup and hasattr(reply_markup, 'inline_keyboard'):
                rows = reply_markup.inline_keyboard or []
                kb_summary = f"rows={len(rows)} cols={[len(r) for r in rows]}"
            elif reply_markup and hasattr(reply_markup, 'to_dict'):
                d = reply_markup.to_dict()
                rows = (d.get('inline_keyboard') or []) if isinstance(d, dict) else []
                kb_summary = f"rows={len(rows)}"
        except Exception:
            kb_summary = "unknown"
        
        # Get caller info for debugging
        stack = traceback.extract_stack()
        caller_info = ""
        if len(stack) >= 2:
            caller = stack[-2]
            caller_info = f" [CALLER: {caller.filename.split('/')[-1]}:{caller.lineno} in {caller.name}]"
        
        logger.info(
            f"TG API -> editMessageText chat_id={getattr(message, 'chat_id', None)} message_id={getattr(message, 'message_id', None)} parse_mode={parse_mode} text_len={len(text or '')} {kb_summary or ''}{caller_info}"
        )
    except Exception:
        pass
    try:
        # Check if message has media (photo, video, etc) - if so, delete and send new text message
        has_media = hasattr(message, 'photo') and message.photo
        has_media = has_media or (hasattr(message, 'video') and message.video)
        has_media = has_media or (hasattr(message, 'document') and message.document)
        has_media = has_media or (hasattr(message, 'animation') and message.animation)
        
        if has_media:
            # Message has media, can't edit text - delete and send new
            try:
                await message.delete()
            except Exception:
                pass
            bot = message.get_bot()
            return await bot.send_message(chat_id=getattr(message, 'chat_id', None), text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        
        resp = await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        try:
            logger.info(
                f"TG API <- editMessageText OK chat_id={getattr(message, 'chat_id', None)} message_id={getattr(message, 'message_id', None)}"
            )
        except Exception:
            pass
        return resp
    except BadRequest as e:
        # Fallback: if cannot edit (e.g., too old / not editable), try sending a new message
        msg = str(e)
        if 'Message is not modified' in msg:
            try:
                logger.info(
                    f"TG API <- editMessageText 400 BadRequest (not modified): text unchanged; skipping edit")
            except Exception:
                pass
            return None
        try:
            logger.warning(
                f"TG API <- editMessageText 400 BadRequest: {msg} | text_preview={(text or '')[:200]!r}")
        except Exception:
            pass
        if ("Message can't be edited" in msg) or ("message to edit not found" in msg) or ("message to edit not found" in msg.lower()) or ("There is no text in the message to edit" in msg) or ("no text in the message to edit" in msg.lower()):
            try:
                bot = message.get_bot()
                return await bot.send_message(chat_id=getattr(message, 'chat_id', None), text=text, reply_markup=reply_markup, parse_mode=parse_mode)
            except Exception:
                pass
        raise
    except TelegramError:
        # Best-effort: ignore other transient editing errors
        try:
            logger.error("TG API <- editMessageText TelegramError (non-400)")
        except Exception:
            pass
        return None


async def safe_edit_caption(message, caption, reply_markup=None, parse_mode=None):
    try:
        try:
            kb_summary = None
            if reply_markup and hasattr(reply_markup, 'inline_keyboard'):
                rows = reply_markup.inline_keyboard or []
                kb_summary = f"rows={len(rows)} cols={[len(r) for r in rows]}"
            logger.info(
                f"TG API -> editMessageCaption chat_id={getattr(message, 'chat_id', None)} message_id={getattr(message, 'message_id', None)} parse_mode={parse_mode} caption_len={len(caption or '')} {kb_summary or ''}"
            )
        except Exception:
            pass
        resp = await message.edit_caption(caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        try:
            logger.info(
                f"TG API <- editMessageCaption OK chat_id={getattr(message, 'chat_id', None)} message_id={getattr(message, 'message_id', None)}"
            )
        except Exception:
            pass
        return resp
    except BadRequest as e:
        try:
            logger.error(
                f"TG API <- editMessageCaption 400 BadRequest: {str(e)} | caption_preview={(caption or '')[:200]!r}")
        except Exception:
            pass
        if 'Message is not modified' in str(e):
            return None
        raise
    except TelegramError:
        try:
            logger.error("TG API <- editMessageCaption TelegramError (non-400)")
        except Exception:
            pass
        return None


def ltr_code(text: str) -> str:
    t = (text or '').replace(' ', '').replace('-', '')
    return f"<code>\u2066{t}\u2069</code>"


async def answer_safely(query, text: str | None = None, show_alert: bool = False):
    """Answer callback query safely with timeout handling"""
    try:
        await query.answer(text or '', show_alert=show_alert)
    except Exception as e:
        # Ignore timeout errors (query already answered)
        if 'query is too old' not in str(e).lower():
            try:
                logger.warning(f"Failed to answer callback query: {e}")
            except Exception:
                pass


def get_all_admin_ids() -> list[int]:
    try:
        rows = query_db("SELECT user_id FROM admins") or []
    except Exception:
        rows = []
    admin_ids: list[int] = []
    try:
        primary_id = int(ADMIN_ID)
        if primary_id > 0:
            admin_ids.append(primary_id)
    except Exception:
        pass
    for r in rows:
        try:
            uid = int(r.get('user_id'))
            if uid not in admin_ids:
                admin_ids.append(uid)
        except Exception:
            continue
    return admin_ids


async def notify_admins(bot, *, text: str | None = None, parse_mode=None, reply_markup=None, photo: str | None = None, document: str | None = None, caption: str | None = None):
    for admin_id in get_all_admin_ids():
        try:
            if photo:
                await bot.send_photo(chat_id=admin_id, photo=photo, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
            elif document:
                await bot.send_document(chat_id=admin_id, document=document, caption=caption, parse_mode=parse_mode, reply_markup=reply_markup)
            elif text:
                await bot.send_message(chat_id=admin_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception:
            continue


def build_styled_qr(data: str):
    """Return a BytesIO PNG with a modern styled QR and soft background.
    Falls back to simple QR if styling deps unavailable.
    """
    import io
    try:
        import qrcode
        from qrcode.image.styledpil import StyledPilImage
        from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
        from qrcode.image.styles.colormasks import RadialGradiantColorMask
        from PIL import Image, ImageFilter, ImageDraw
    except Exception:
        try:
            import qrcode
            buf = io.BytesIO()
            qrcode.make(data).save(buf, format='PNG')
            buf.seek(0)
            return buf
        except Exception:
            return None

    # Base QR
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(image_factory=StyledPilImage, module_drawer=RoundedModuleDrawer(), color_mask=RadialGradiantColorMask())

    # Create soft gradient background
    size = (qr_img.size[0] + 220, qr_img.size[1] + 220)
    bg = Image.new('RGB', size, (20, 24, 28))
    # radial vignette
    overlay = Image.new('L', size, 0)
    d = ImageDraw.Draw(overlay)
    d.ellipse((40, 40, size[0]-40, size[1]-40), fill=230)
    overlay = overlay.filter(ImageFilter.GaussianBlur(50))
    grad = Image.new('RGB', size, (58, 97, 180))
    bg = Image.composite(grad, bg, overlay)

    # Paste QR centered on background with a white rounded rect backdrop
    try:
        pad = 24
        card_w = qr_img.size[0] + pad*2
        card_h = qr_img.size[1] + pad*2
        card = Image.new('RGBA', (card_w, card_h), (255, 255, 255, 255))
        # rounded corners mask
        corner = Image.new('L', (40, 40), 0)
        dc = ImageDraw.Draw(corner)
        dc.pieslice((0, 0, 40, 40), 180, 270, fill=255)
        mask = Image.new('L', (card_w, card_h), 255)
        mask.paste(corner, (0, 0))
        mask.paste(corner.rotate(90), (0, card_h-40))
        mask.paste(corner.rotate(180), (card_w-40, card_h-40))
        mask.paste(corner.rotate(270), (card_w-40, 0))
        card.putalpha(mask)

        card.paste(qr_img.convert('RGBA'), (pad, pad), qr_img.convert('RGBA'))
        x = (bg.size[0] - card_w)//2
        y = (bg.size[1] - card_h)//2
        bg.paste(card, (x, y), card)
    except Exception:
        # fallback: just center QR
        x = (bg.size[0] - qr_img.size[0])//2
        y = (bg.size[1] - qr_img.size[1])//2
        bg.paste(qr_img, (x, y))

    out = io.BytesIO()
    bg.save(out, format='PNG', optimize=True)
    out.seek(0)
    return out


def append_footer_buttons(keyboard_rows, back_callback: str | None = None):
    """Append a persistent footer row with Back and Main buttons to inline keyboards.
    keyboard_rows: list[list[InlineKeyboardButton]]
    back_callback: if provided, uses that for Back; otherwise uses 'start_main'.
    """
    try:
        from telegram import InlineKeyboardButton
        back_cb = back_callback or 'start_main'
        footer = [InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb), InlineKeyboardButton("🏠 منوی اصلی", callback_data='start_main')]
        keyboard_rows.append(footer)
    except Exception:
        pass
    return keyboard_rows