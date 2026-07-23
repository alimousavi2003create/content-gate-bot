import os
import io
import uuid
import asyncio
import logging
import threading
import functools

from flask import Flask, request, jsonify, session, redirect, url_for, render_template

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    MessageReactionHandler, filters, ContextTypes,
)

from database import init_db, get_db_cursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = [x for x in os.environ.get("ADMIN_IDS", "8030373785").split(",") if x]
ADMIN_PANEL_PASSWORD = os.environ.get("ADMIN_PANEL_PASSWORD", "")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24).hex()
GROUP_GATE_CHAT_ID = os.environ.get("GROUP_GATE_CHAT_ID", "")
GROUP_GATE_REQUIRED_CHATS = os.environ.get("GROUP_GATE_REQUIRED_CHATS", "")

flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET_KEY
flask_app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

bot_app = None
bot_loop = None
bot_ready_event = threading.Event()
BOT_USERNAME = None


def run_bot_coro(coro, timeout=30):
    if bot_loop is None:
        raise RuntimeError("bot loop not ready")
    future = asyncio.run_coroutine_threadsafe(coro, bot_loop)
    return future.result(timeout=timeout)


# ---------- Telegram bot logic ----------

async def check_membership(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.error(f"membership check failed for chat {chat_id}: {e}")
        return False


def build_join_keyboard(missing, code):
    buttons = []
    for title, link in missing:
        buttons.append([InlineKeyboardButton(f"\U0001F4E2 Join {title}", url=link)])
    buttons.append([InlineKeyboardButton("\u2705 I joined - check again", callback_data=f"recheck:{code}")])
    return InlineKeyboardMarkup(buttons)


async def resolve_missing(bot, required_chats, user_id):
    missing = []
    config_errors = []
    for chat_id in required_chats:
        ok = await check_membership(bot, chat_id, user_id)
        if not ok:
            try:
                chat = await bot.get_chat(chat_id)
                title = chat.title or chat_id
                link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
                if not link:
                    link = await bot.export_chat_invite_link(chat_id)
                missing.append((title, link))
            except Exception as e:
                logger.error(f"could not resolve chat {chat_id}: {e}")
                config_errors.append(chat_id)
    return missing, config_errors


async def deliver_content(bot, chat_id, content):
    ctype = content["content_type"]
    caption = content["text_content"] or ""
    try:
        if ctype == "text":
            await bot.send_message(chat_id=chat_id, text=content["text_content"] or "")
        elif ctype == "photo":
            await bot.send_photo(chat_id=chat_id, photo=content["file_id"], caption=caption)
        elif ctype == "video":
            await bot.send_video(chat_id=chat_id, video=content["file_id"], caption=caption)
        elif ctype == "animation":
            await bot.send_animation(chat_id=chat_id, animation=content["file_id"], caption=caption)
        elif ctype == "audio":
            await bot.send_audio(chat_id=chat_id, audio=content["file_id"], caption=caption)
        elif ctype == "sticker":
            await bot.send_sticker(chat_id=chat_id, sticker=content["file_id"])
        elif ctype == "document":
            await bot.send_document(chat_id=chat_id, document=content["file_id"], caption=caption)
    except Exception as e:
        logger.error(f"delivery failed: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("سلام! برای دریافت محتوا از یک لینک معتبر استفاده کن.")
        return

    code = context.args[0].strip()
    with get_db_cursor() as c:
        c.execute("SELECT * FROM contents WHERE code = %s", (code,))
        content = c.fetchone()

    if not content:
        await update.message.reply_text("این لینک نامعتبر یا منقضی شده.")
        return

    required_chats = [x for x in content["required_chats"].split(",") if x]
    missing, config_errors = await resolve_missing(context.bot, required_chats, user_id)

    if config_errors:
        await update.message.reply_text("این لینک تنظیمات نادرست دارد. به ادمین اطلاع بده.")
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=f"محتوای '{code}' کانال نامعتبر دارد: {config_errors}")
            except Exception:
                pass
        return

    if missing:
        await update.message.reply_text("اول باید عضو این کانال‌ها بشی:", reply_markup=build_join_keyboard(missing, code))
        return

    await deliver_content(context.bot, update.effective_chat.id, content)


async def recheck_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    user_id = query.from_user.id

    with get_db_cursor() as c:
        c.execute("SELECT * FROM contents WHERE code = %s", (code,))
        content = c.fetchone()
    if not content:
        await query.edit_message_text("این لینک نامعتبر یا منقضی شده.")
        return

    required_chats = [x for x in content["required_chats"].split(",") if x]
    missing, config_errors = await resolve_missing(context.bot, required_chats, user_id)

    if config_errors:
        await query.edit_message_text("این لینک تنظیمات نادرست دارد. به ادمین اطلاع بده.")
        return

    if missing:
        await query.edit_message_text("هنوز عضو این‌ها نیستی:", reply_markup=build_join_keyboard(missing, code))
        return

    await query.edit_message_text("همه چی اوکیه! در حال ارسال محتوا...")
    await deliver_content(context.bot, query.message.chat_id, content)


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
                await context.bot.send_message(chat_id=user_id, text=f"اول باید عضو {chat.title} بشی:\n{link}")
            except Exception:
                pass
            return


# ---------- bridge coroutines called from Flask ----------

async def _resolve_channel(identifier):
    ident = identifier
    if ident.lstrip("-").isdigit():
        ident = int(ident)
    chat = await bot_app.bot.get_chat(ident)
    try:
        invite_link = chat.invite_link or await bot_app.bot.export_chat_invite_link(chat.id)
    except Exception:
        invite_link = f"https://t.me/{chat.username}" if chat.username else ""
    return {
        "chat_id": str(chat.id),
        "title": chat.title or str(chat.id),
        "username": chat.username or "",
        "invite_link": invite_link or "",
    }


async def _upload_and_get_file_id(content_type, file_bytes, filename, caption):
    storage_chat_id = int(ADMIN_IDS[0])
    bot = bot_app.bot
    bio = io.BytesIO(file_bytes)
    bio.name = filename
    if content_type == "photo":
        msg = await bot.send_photo(chat_id=storage_chat_id, photo=bio, caption=caption or None)
        return msg.photo[-1].file_id
    elif content_type == "video":
        msg = await bot.send_video(chat_id=storage_chat_id, video=bio, caption=caption or None)
        return msg.video.file_id
    elif content_type == "animation":
        msg = await bot.send_animation(chat_id=storage_chat_id, animation=bio, caption=caption or None)
        return msg.animation.file_id
    elif content_type == "audio":
        msg = await bot.send_audio(chat_id=storage_chat_id, audio=bio, caption=caption or None)
        return msg.audio.file_id
    elif content_type == "sticker":
        msg = await bot.send_sticker(chat_id=storage_chat_id, sticker=bio)
        return msg.sticker.file_id
    else:
        msg = await bot.send_document(chat_id=storage_chat_id, document=bio, caption=caption or None)
        return msg.document.file_id


def detect_content_type(filename, mimetype):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mimetype = mimetype or ""
    if ext == "gif":
        return "animation"
    if ext in ("jpg", "jpeg", "png", "webp"):
        return "photo"
    if ext in ("mp4", "mov", "mkv", "webm"):
        return "video"
    if ext in ("mp3", "wav", "ogg", "m4a", "flac"):
        return "audio"
    if ext == "tgs":
        return "sticker"
    if mimetype.startswith("image/"):
        return "photo"
    if mimetype.startswith("video/"):
        return "video"
    if mimetype.startswith("audio/"):
        return "audio"
    return "document"


# ---------- Flask admin panel ----------

def require_admin(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


@flask_app.route("/")
def health():
    return "OK"


@flask_app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if ADMIN_PANEL_PASSWORD and password == ADMIN_PANEL_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        return render_template("admin_login.html", error="رمز اشتباهه")
    return render_template("admin_login.html", error=None)


@flask_app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))


@flask_app.route("/admin")
@require_admin
def admin_dashboard():
    return render_template("admin_dashboard.html")


@flask_app.route("/admin/api/channels", methods=["GET", "POST"])
@require_admin
def api_channels():
    if request.method == "POST":
        data = request.json or {}
        identifier = (data.get("identifier") or "").strip()
        if not identifier:
            return jsonify({"success": False, "error": "شناسه کانال خالیه"}), 400
        try:
            info = run_bot_coro(_resolve_channel(identifier))
        except Exception as e:
            return jsonify({"success": False, "error": f"کانال پیدا نشد یا بات توش عضو نیست: {e}"}), 400
        with get_db_cursor() as c:
            c.execute("""
                INSERT INTO channel_pool (chat_id, title, username, invite_link)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chat_id) DO UPDATE SET title=%s, username=%s, invite_link=%s
            """, (info["chat_id"], info["title"], info["username"], info["invite_link"],
                  info["title"], info["username"], info["invite_link"]))
        return jsonify({"success": True, "channel": info})

    with get_db_cursor() as c:
        c.execute("SELECT * FROM channel_pool ORDER BY added_at DESC")
        rows = [dict(r) for r in c.fetchall()]
    return jsonify({"success": True, "channels": rows})


@flask_app.route("/admin/api/channels/<chat_id>", methods=["DELETE"])
@require_admin
def api_channel_delete(chat_id):
    with get_db_cursor() as c:
        c.execute("DELETE FROM channel_pool WHERE chat_id = %s", (chat_id,))
    return jsonify({"success": True})


@flask_app.route("/admin/api/contents", methods=["GET", "POST"])
@require_admin
def api_contents():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        caption = request.form.get("caption") or ""
        text_body = request.form.get("text_body") or ""
        type_override = request.form.get("type_override") or ""
        channel_ids = request.form.getlist("channel_ids")
        code = (request.form.get("code") or "").strip() or uuid.uuid4().hex[:8]

        if not channel_ids:
            return jsonify({"success": False, "error": "حداقل یک کانال انتخاب کن"}), 400

        uploaded = request.files.get("file")

        if uploaded and uploaded.filename:
            file_bytes = uploaded.read()
            valid_types = ("photo", "video", "animation", "audio", "sticker", "document")
            content_type = type_override if type_override in valid_types else detect_content_type(uploaded.filename, uploaded.mimetype)
            try:
                file_id = run_bot_coro(_upload_and_get_file_id(content_type, file_bytes, uploaded.filename, caption), timeout=60)
            except Exception as e:
                return jsonify({"success": False, "error": f"آپلود فایل به تلگرام شکست خورد: {e}"}), 500
            text_content = caption
        else:
            if not text_body.strip():
                return jsonify({"success": False, "error": "یا فایل بفرست یا متن بنویس"}), 400
            content_type = "text"
            file_id = None
            text_content = text_body

        with get_db_cursor() as c:
            c.execute("""
                INSERT INTO contents (code, title, content_type, text_content, file_id, required_chats)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET title=%s, content_type=%s, text_content=%s, file_id=%s, required_chats=%s
            """, (code, title, content_type, text_content, file_id, ",".join(channel_ids),
                  title, content_type, text_content, file_id, ",".join(channel_ids)))

        link = f"https://t.me/{BOT_USERNAME}?start={code}"
        return jsonify({"success": True, "code": code, "link": link})

    with get_db_cursor() as c:
        c.execute("SELECT * FROM contents ORDER BY created_at DESC")
        rows = [dict(r) for r in c.fetchall()]
    for r in rows:
        r["link"] = f"https://t.me/{BOT_USERNAME}?start={r['code']}"
    return jsonify({"success": True, "contents": rows})


@flask_app.route("/admin/api/contents/<code>", methods=["DELETE"])
@require_admin
def api_content_delete(code):
    with get_db_cursor() as c:
        c.execute("DELETE FROM contents WHERE code = %s", (code,))
    return jsonify({"success": True})


# ---------- bot thread bootstrap ----------

async def _run_bot_async():
    global bot_app, bot_loop, BOT_USERNAME
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(recheck_callback, pattern="^recheck:"))
    application.add_handler(MessageReactionHandler(track_reaction))
    application.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, group_gate))
    bot_app = application

    await application.initialize()
    me = await application.bot.get_me()
    BOT_USERNAME = me.username
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query", "message_reaction"])

    bot_loop = asyncio.get_running_loop()
    bot_ready_event.set()

    stop_event = asyncio.Event()
    await stop_event.wait()


def _bot_thread_target():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run_bot_async())


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN environment variable is not set")
    if not ADMIN_PANEL_PASSWORD:
        logger.warning("ADMIN_PANEL_PASSWORD not set - admin panel login will always fail")
    init_db()

    t = threading.Thread(target=_bot_thread_target, daemon=True)
    t.start()
    bot_ready_event.wait(timeout=30)

    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
