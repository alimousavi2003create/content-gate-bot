with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

anchor = 'def main():'
assert anchor in content, "main() anchor not found"

new_handler = '''async def report_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return
    title = chat.title or chat.id
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"Chat ID discovered:\\n{title}\\n{chat.id}"
            )
        except Exception:
            pass


'''
content = content.replace(anchor, new_handler + anchor, 1)

old_reg = '''    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, group_gate))'''
new_reg = '''    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, group_gate))
    app.add_handler(MessageHandler(filters.ALL, report_chat_id))'''
assert old_reg in content, "group_gate handler registration anchor not found"
content = content.replace(old_reg, new_reg, 1)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("main.py: chat_id discovery handler added")
