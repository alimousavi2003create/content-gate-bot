with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = '''async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("سلام! برای دریافت محتوا از یک لینک معتبر استفاده کن.")
        return'''

assert old_block in content, "start() anchor not found"

new_block = '''ADMIN_PANEL_URL = os.environ.get("ADMIN_PANEL_URL", "https://content-gate-bot-production.up.railway.app/admin")
DEFAULT_GROUP_LINK = os.environ.get("DEFAULT_GROUP_LINK", "https://t.me/botgrups")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        if str(user_id) in ADMIN_IDS:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001F6E0 باز کردن پنل ادمین", url=ADMIN_PANEL_URL)]])
            await update.message.reply_text("سلام ادمین.", reply_markup=kb)
        else:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001F517 عضویت", url=DEFAULT_GROUP_LINK)]])
            await update.message.reply_text("سلام! برای دریافت محتوا از یک لینک معتبر استفاده کن.", reply_markup=kb)
        return'''

content = content.replace(old_block, new_block, 1)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("main.py: admin/user start routing added")
