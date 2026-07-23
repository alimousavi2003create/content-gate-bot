import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    MessageReactionHandler, filters, ContextTypes
)
from database import init_db, get_db_cursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = set(os.environ.get("ADMIN_IDS", "8030373785").split(","))
GROUP_GATE_CHAT_ID = os.environ.get("GROUP_GATE_CHAT_ID", "")
GROUP_GATE_REQUIRED_CHATS = os.environ.get("GROUP_GATE_REQUIRED_CHATS", "")


def is_admin(user_id):
    return str(user_id) in ADMIN_IDS


async def check_membership(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.error(f"membership check failed for chat {chat_id}: {e}")
        return False


async def check_reaction(chat_id, message_id, user_id):
    with get_db_cursor() as c:
        c.execute(
            "SELECT 1 FROM reactions WHERE chat_id=%s AND message_id=%s AND user_id=%s",
            (str(chat_id), message_id, str(user_id))
        )
        return c.fetchone() is not None


def build_join_keyboard(missing_chat_titles, code):
    buttons = []
    for title, link in missing_chat_titles:
        buttons.append([InlineKeyboardButton(f"\U0001F4E2 Join {title}", url=link)])
    buttons.append([InlineKeyboardButton("\u2705 I joined - check again", callback_data=f"recheck:{code}")])
    return InlineKeyboardMarkup(buttons)


async def deliver_content(update_or_query, context, content, edit=False):
    bot = context.bot
    chat_id = update_or_query.effective_chat.id if hasattr(update_or_query, "effective_chat") else update_or_query.message.chat_id
    ctype = content["content_type"]
    try:
        if ctype == "text":
            await bot.send_message(chat_id=chat_id, text=content["text_content"])
        elif ctype == "photo":
            await bot.send_photo(chat_id=chat_id, photo=content["file_id"], caption=content["text_content"] or "")
        elif ctype == "video":
            await bot.send_video(chat_id=chat_id, video=content["file_id"], caption=content["text_content"] or "")
        elif ctype == "audio":
            await bot.send_audio(chat_id=chat_id, audio=content["file_id"], caption=content["text_content"] or "")
        elif ctype == "document":
            await bot.send_document(chat_id=chat_id, document=content["file_id"], caption=content["text_content"] or "")
    except Exception as e:
        logger.error(f"delivery failed: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Welcome! Use a content link to get started.")
        return

    code = context.args[0].strip()
    with get_db_cursor() as c:
        c.execute("SELECT * FROM contents WHERE code = %s", (code,))
        content = c.fetchone()

    if not content:
        await update.message.reply_text("This link is invalid or expired.")
        return

    required_chats = [x for x in content["required_chats"].split(",") if x]
    missing = []
    config_errors = []
    for chat_id in required_chats:
        ok = await check_membership(context.bot, chat_id, user_id)
        if not ok:
            try:
                chat = await context.bot.get_chat(chat_id)
                title = chat.title or chat_id
                link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
                if not link:
                    link = await context.bot.export_chat_invite_link(chat_id)
                missing.append((title, link))
            except Exception as e:
                logger.error(f"could not resolve chat {chat_id}: {e}")
                config_errors.append(chat_id)

    if content["reaction_chat_id"] and content["reaction_message_id"]:
        reacted = await check_reaction(content["reaction_chat_id"], content["reaction_message_id"], user_id)
        if not reacted:
            try:
                chat = await context.bot.get_chat(content["reaction_chat_id"])
                title = f"{chat.title} (react to the latest post)"
                link = chat.invite_link or await context.bot.export_chat_invite_link(content["reaction_chat_id"])
                missing.append((title, link))
            except Exception as e:
                logger.error(f"could not resolve reaction chat: {e}")
                config_errors.append(content["reaction_chat_id"])

    if config_errors:
        await update.message.reply_text(
            "This link is misconfigured (invalid channel/group ID). Please tell the admin."
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"Content '{code}' has invalid chat IDs: {config_errors}"
                )
            except Exception:
                pass
        return

    if missing:
        await update.message.reply_text(
            "You need to join these first:",
            reply_markup=build_join_keyboard(missing, code)
        )
        return

    await deliver_content(update, context, content)


async def recheck_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    user_id = query.from_user.id

    with get_db_cursor() as c:
        c.execute("SELECT * FROM contents WHERE code = %s", (code,))
        content = c.fetchone()
    if not content:
        await query.edit_message_text("This link is invalid or expired.")
        return

    required_chats = [x for x in content["required_chats"].split(",") if x]
    missing = []
    config_errors = []
    for chat_id in required_chats:
        ok = await check_membership(context.bot, chat_id, user_id)
        if not ok:
            try:
                chat = await context.bot.get_chat(chat_id)
                title = chat.title or chat_id
                link = chat.invite_link or await context.bot.export_chat_invite_link(chat_id)
                missing.append((title, link))
            except Exception as e:
                logger.error(f"could not resolve chat {chat_id}: {e}")
                config_errors.append(chat_id)

    if content["reaction_chat_id"] and content["reaction_message_id"]:
        reacted = await check_reaction(content["reaction_chat_id"], content["reaction_message_id"], user_id)
        if not reacted:
            try:
                chat = await context.bot.get_chat(content["reaction_chat_id"])
                title = f"{chat.title} (react to the latest post)"
                link = chat.invite_link or await context.bot.export_chat_invite_link(content["reaction_chat_id"])
                missing.append((title, link))
            except Exception as e:
                logger.error(f"could not resolve reaction chat: {e}")
                config_errors.append(content["reaction_chat_id"])

    if config_errors:
        await query.edit_message_text("This link is misconfigured (invalid channel/group ID). Please tell the admin.")
        return

    if missing:
        await query.edit_message_text(
            "Still missing:",
            reply_markup=build_join_keyboard(missing, code)
        )
        return

    await query.edit_message_text("All set! Sending your content now...")
    await deliver_content(query, context, content)


async def addcontent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage:\n/addcontent <code> <required_chat_id1,required_chat_id2,...> [reaction_chat_id:message_id]\n\n"
            "Then send the actual content (text/photo/video/audio/document) as your next message."
        )
        return

    code = context.args[0]
    required_chats = context.args[1]
    reaction_chat_id, reaction_message_id = None, None
    if len(context.args) >= 3 and ":" in context.args[2]:
        reaction_chat_id, msg_id_str = context.args[2].split(":", 1)
        reaction_message_id = int(msg_id_str)

    with get_db_cursor() as c:
        c.execute("""
            INSERT INTO pending_uploads (admin_id, code, required_chats, reaction_chat_id, reaction_message_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (admin_id) DO UPDATE SET code=%s, required_chats=%s, reaction_chat_id=%s, reaction_message_id=%s
        """, (str(update.effective_user.id), code, required_chats, reaction_chat_id, reaction_message_id,
              code, required_chats, reaction_chat_id, reaction_message_id))

    await update.message.reply_text(f"Got it. Now send the content for code '{code}' (text, photo, video, audio, or document).")


async def capture_pending_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = str(update.effective_user.id)
    if not is_admin(admin_id):
        return
    with get_db_cursor() as c:
        c.execute("SELECT * FROM pending_uploads WHERE admin_id = %s", (admin_id,))
        pending = c.fetchone()
    if not pending:
        return

    msg = update.message
    content_type, file_id, text_content = None, None, None
    if msg.photo:
        content_type, file_id = "photo", msg.photo[-1].file_id
        text_content = msg.caption
    elif msg.video:
        content_type, file_id = "video", msg.video.file_id
        text_content = msg.caption
    elif msg.audio:
        content_type, file_id = "audio", msg.audio.file_id
        text_content = msg.caption
    elif msg.document:
        content_type, file_id = "document", msg.document.file_id
        text_content = msg.caption
    elif msg.text:
        content_type = "text"
        text_content = msg.text
    else:
        return

    with get_db_cursor() as c:
        c.execute("""
            INSERT INTO contents (code, content_type, text_content, file_id, required_chats, reaction_chat_id, reaction_message_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET content_type=%s, text_content=%s, file_id=%s, required_chats=%s, reaction_chat_id=%s, reaction_message_id=%s
        """, (pending["code"], content_type, text_content, file_id, pending["required_chats"],
              pending["reaction_chat_id"], pending["reaction_message_id"],
              content_type, text_content, file_id, pending["required_chats"],
              pending["reaction_chat_id"], pending["reaction_message_id"]))
        c.execute("DELETE FROM pending_uploads WHERE admin_id = %s", (admin_id,))

    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={pending['code']}"
    await update.message.reply_text(f"Content saved!\n\nShare this link:\n{link}")


async def track_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reaction = update.message_reaction
    if not reaction or not reaction.new_reaction:
        return
    with get_db_cursor() as c:
        c.execute("""
            INSERT INTO reactions (chat_id, message_id, user_id)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (str(reaction.chat.id), reaction.message_id, str(reaction.user.id) if reaction.user else "0"))


async def group_gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not GROUP_GATE_CHAT_ID or not GROUP_GATE_REQUIRED_CHATS:
        return
    if str(update.effective_chat.id) != str(GROUP_GATE_CHAT_ID):
        return
    user_id = update.effective_user.id
    required = [x for x in GROUP_GATE_REQUIRED_CHATS.split(",") if x]
    for chat_id in required:
        ok = await check_membership(context.bot, chat_id, user_id)
        if not ok:
            try:
                await update.message.delete()
            except Exception:
                pass
            try:
                chat = await context.bot.get_chat(chat_id)
                link = chat.invite_link or await context.bot.export_chat_invite_link(chat_id)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"Please join {chat.title} before posting in the group:\n{link}"
                )
            except Exception:
                pass
            return


async def report_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return
    title = chat.title or chat.id
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"Chat ID discovered:\n{title}\n{chat.id}"
            )
        except Exception:
            pass


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN environment variable is not set")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcontent", addcontent))
    app.add_handler(CallbackQueryHandler(recheck_callback, pattern="^recheck:"))
    app.add_handler(MessageReactionHandler(track_reaction))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL) & ~filters.COMMAND,
        capture_pending_content
    ))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, group_gate))
    app.add_handler(MessageHandler(filters.ALL, report_chat_id))

    logger.info("Content gate bot started!")
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query", "message_reaction"])


if __name__ == "__main__":
    main()
