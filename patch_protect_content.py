with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = '''async def deliver_content(bot, chat_id, content):
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
        logger.error(f"delivery failed: {e}")'''

assert old_block in content, "deliver_content anchor not found"

new_block = '''async def deliver_content(bot, chat_id, content):
    ctype = content["content_type"]
    caption = content["text_content"] or ""
    try:
        if ctype == "text":
            await bot.send_message(chat_id=chat_id, text=content["text_content"] or "", protect_content=True)
        elif ctype == "photo":
            await bot.send_photo(chat_id=chat_id, photo=content["file_id"], caption=caption, protect_content=True)
        elif ctype == "video":
            await bot.send_video(chat_id=chat_id, video=content["file_id"], caption=caption, protect_content=True)
        elif ctype == "animation":
            await bot.send_animation(chat_id=chat_id, animation=content["file_id"], caption=caption, protect_content=True)
        elif ctype == "audio":
            await bot.send_audio(chat_id=chat_id, audio=content["file_id"], caption=caption, protect_content=True)
        elif ctype == "sticker":
            await bot.send_sticker(chat_id=chat_id, sticker=content["file_id"], protect_content=True)
        elif ctype == "document":
            await bot.send_document(chat_id=chat_id, document=content["file_id"], caption=caption, protect_content=True)
    except Exception as e:
        logger.error(f"delivery failed: {e}")'''

content = content.replace(old_block, new_block, 1)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("main.py: protect_content=True added to all deliveries")
