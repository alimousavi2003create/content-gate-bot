with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block = '''        if can_group:
            media_list = []
            for i, it in enumerate(items):
                cap = caption if i == 0 else None
                if it["item_type"] == "photo":
                    media_list.append(InputMediaPhoto(media=it["file_id"], caption=cap))
                else:
                    media_list.append(InputMediaVideo(media=it["file_id"], caption=cap))
            try:
                sent_messages = await bot.send_media_group(chat_id=chat_id, media=media_list)
            except Exception as e:
                logger.error(f"album delivery (media_group) failed: {e}")
                return'''

new_block = '''        if can_group:
            chunk_size = 10
            chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
            for chunk_index, chunk in enumerate(chunks):
                media_list = []
                for i, it in enumerate(chunk):
                    cap = caption if (chunk_index == 0 and i == 0) else None
                    if it["item_type"] == "photo":
                        media_list.append(InputMediaPhoto(media=it["file_id"], caption=cap))
                    else:
                        media_list.append(InputMediaVideo(media=it["file_id"], caption=cap))
                if len(media_list) == 1:
                    single = media_list[0]
                    try:
                        msg = await _send_single_item(
                            bot, chat_id,
                            "photo" if isinstance(single, InputMediaPhoto) else "video",
                            single.media, single.caption
                        )
                        if msg is not None:
                            sent_messages.append(msg)
                    except Exception as e:
                        logger.error(f"single leftover item delivery failed: {e}")
                    continue
                try:
                    chunk_sent = await bot.send_media_group(chat_id=chat_id, media=media_list)
                    sent_messages.extend(chunk_sent)
                except Exception as e:
                    logger.error(f"album delivery (media_group) failed on chunk {chunk_index}: {e}")
                await asyncio.sleep(0.3)'''

assert old_block in content, "album send block anchor not found"
content = content.replace(old_block, new_block, 1)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("main.py: album delivery now splits into batches of 10 (Telegram's limit)")
