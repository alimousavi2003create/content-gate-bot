with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

old_block_1 = '''    required_chats = [x for x in content["required_chats"].split(",") if x]
    missing = []
    for chat_id in required_chats:
        ok = await check_membership(context.bot, chat_id, user_id)
        if not ok:
            try:
                chat = await context.bot.get_chat(chat_id)
                title = chat.title or chat_id
                link = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else None
                if not link:
                    link = await context.bot.export_chat_invite_link(chat_id)
            except Exception:
                title, link = chat_id, None
            if link:
                missing.append((title, link))

    if content["reaction_chat_id"] and content["reaction_message_id"]:
        reacted = await check_reaction(content["reaction_chat_id"], content["reaction_message_id"], user_id)
        if not reacted:
            try:
                chat = await context.bot.get_chat(content["reaction_chat_id"])
                title = f"{chat.title} (react to the latest post)"
                link = chat.invite_link or await context.bot.export_chat_invite_link(content["reaction_chat_id"])
                missing.append((title, link))
            except Exception:
                pass

    if missing:
        await update.message.reply_text(
            "You need to join these first:",
            reply_markup=build_join_keyboard(missing, code)
        )
        return

    await deliver_content(update, context, content)'''

new_block_1 = '''    required_chats = [x for x in content["required_chats"].split(",") if x]
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

    await deliver_content(update, context, content)'''

assert old_block_1 in content, "start() gate block anchor not found"
content = content.replace(old_block_1, new_block_1, 1)

old_block_2 = '''    required_chats = [x for x in content["required_chats"].split(",") if x]
    missing = []
    for chat_id in required_chats:
        ok = await check_membership(context.bot, chat_id, user_id)
        if not ok:
            try:
                chat = await context.bot.get_chat(chat_id)
                title = chat.title or chat_id
                link = chat.invite_link or await context.bot.export_chat_invite_link(chat_id)
            except Exception:
                title, link = chat_id, None
            if link:
                missing.append((title, link))

    if content["reaction_chat_id"] and content["reaction_message_id"]:
        reacted = await check_reaction(content["reaction_chat_id"], content["reaction_message_id"], user_id)
        if not reacted:
            try:
                chat = await context.bot.get_chat(content["reaction_chat_id"])
                title = f"{chat.title} (react to the latest post)"
                link = chat.invite_link or await context.bot.export_chat_invite_link(content["reaction_chat_id"])
                missing.append((title, link))
            except Exception:
                pass

    if missing:
        await query.edit_message_text(
            "Still missing:",
            reply_markup=build_join_keyboard(missing, code)
        )
        return

    await query.edit_message_text("All set! Sending your content now...")
    await deliver_content(query, context, content)'''

new_block_2 = '''    required_chats = [x for x in content["required_chats"].split(",") if x]
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
    await deliver_content(query, context, content)'''

assert old_block_2 in content, "recheck_callback gate block anchor not found"
content = content.replace(old_block_2, new_block_2, 1)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("main.py: fail-safe gate logic applied (invalid chat config now blocks instead of bypassing)")
