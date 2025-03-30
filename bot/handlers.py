from telegram import Update
import telegram
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from .callbacks import handle_refresh, handle_tax_details, handle_tx_wallet_details, handle_token_summary, handle_about,handle_portfolio_menu,render_wallet_summary,handle_scoreboard
import datetime
from .messages import show_summary
from services.token_analysis import main_async
from db import save_user_interaction
from bot.utils import is_contract_address
from bot.callbacks import handle_portfolio_add_wallet,handle_view_portfolio_wallet,handle_portfolio_command,handle_market_prices,handle_call_it
import asyncio
from bot.callbacks import delete_later
from db import session,SavedWallets,UserInteraction,save_token_dynamics
from telegram import BotCommand

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username
    request_time = datetime.datetime.now()
    
    save_user_interaction(user_id,username,requested_at=request_time)

    msg=await update.message.reply_text("Please enter the token address:")
    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))

async def set_bot_commands(application):
    commands = [
        BotCommand("help", "📖 Show help"),
        BotCommand("portfolio", "📊 View your saved wallets"),
        BotCommand("add", "➕ Add wallet: /add <address> <nickname>"),
        BotCommand("del", "🗑️ Delete wallet: /del <nickname>"),
        BotCommand("rename", "✏️ Rename a wallet"),
        BotCommand("wipewallets", "🧹 Clear all wallets"),
        BotCommand("clearchat", "🧹 Delete all messages from bot"),
        BotCommand("scoreboard", "🏆 Show Scoreboard"),       
    ]
    await application.bot.set_my_commands(commands)

async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    token_address = update.message.text.strip()
    user_id = update.effective_user.id
    username = update.effective_user.username
    message_text = update.message.text.strip()

    if update.message:
        await update.message.delete()



    # 🗑️ Delete previous prompt message (if exists)
    prompt_id = context.user_data.pop("wallet_prompt_message_id", None)
    if prompt_id:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=prompt_id
            )
        except:
            pass

    if context.user_data.get("pending_wallet_slot") is not None:
        slot = context.user_data["pending_wallet_slot"]

        if context.user_data.get("pending_wallet_stage") == "awaiting_nickname":
            # Save the wallet now
            address = context.user_data.get("pending_wallet_address")
            nickname = message_text
            telegram_username = update.effective_user.username

            new_wallet = SavedWallets(user_id=user_id, slot=slot, address=address, nickname=nickname,username=telegram_username)
            session.add(new_wallet)
            session.commit()

            prompt=await update.message.reply_text(f"✅ Wallet `{nickname}` saved in slot {slot + 1}.")
            prompt=asyncio.create_task(delete_later(context.bot, update.effective_chat.id, prompt.message_id, delay=4))
            # Clean up
            context.user_data.pop("pending_wallet_slot", None)
            context.user_data.pop("pending_wallet_address", None)
            context.user_data.pop("pending_wallet_stage", None)
            return

        # Otherwise, we're expecting the wallet address first
        context.user_data["pending_wallet_address"] = message_text
        context.user_data["pending_wallet_stage"] = "awaiting_nickname"

        prompt = await update.message.reply_text("💬 Got it! Now please enter a nickname for this wallet:")      
        prompt=asyncio.create_task(delete_later(context.bot, update.effective_chat.id, prompt.message_id, delay=4))
        return


    if not is_contract_address(message_text):
        print("📦 Detected wallet address, fetching portfolio...")
        await render_wallet_summary(update, context, message_text)
        return

    request_time_utc = datetime.datetime.utcnow()  # Pass datetime object directly
    sent_message = await update.message.reply_text("Generating summary...")
    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, sent_message.message_id, delay=4))    
    bot_reply_message_id = sent_message.message_id

    save_user_interaction(
        user_id=user_id,
        username=username,
        message_id=bot_reply_message_id,
        token_address=token_address,  # explicitly verified to be non-None
        requested_at=request_time_utc)
    
 
    curent_bundle_balance_token,curent_sniper_balance_token_percent,market_cap_usd,total_sniper_worth,total_bundle_worth=await main_async(token_address)
    save_token_dynamics(
        market_cap_usd=market_cap_usd,
        token_address=token_address,
        bundle_arrow=None,
        sniper_arrow=None,
        market_cap_arrow=None,
        curent_bundle_balance_token=curent_bundle_balance_token,
        curent_sniper_balance_token_percent=curent_sniper_balance_token_percent,
        total_sniper_worth=total_sniper_worth,
        total_bundle_worth=total_bundle_worth
    )

  
    await show_summary(sent_message.message_id, update, context)

async def handle_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except:
        pass  # if it's already gone or undeletable, ignore
    if len(args) < 2:
        msg=await update.message.reply_text("⚠️ Usage: /add <wallet_address> <nickname>")
        asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=15))
        return

    address, nickname = args[0], " ".join(args[1]).strip()

    # Check if already exists
    existing = session.query(SavedWallets).filter_by(user_id=user_id, address=address).first()
    if existing:
        msg=await update.message.reply_text("❌ This wallet is already saved.")
        asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))
        return

    # Find first available slot
    existing_wallets = session.query(SavedWallets).filter_by(user_id=user_id).all()
    used_slots = {w.slot for w in existing_wallets}
    available_slot = next((i for i in range(4) if i not in used_slots), None)

    if available_slot is None:
        msg=await update.message.reply_text("❌ You already have 4 wallets saved. Delete one to add a new.")
        asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))
        return
    username = update.effective_user.username or "unknown"  # fallback in case username is not set
    new_wallet = SavedWallets(
        user_id=user_id,
        username=username,
        address=address,
        nickname=nickname,
        slot=available_slot
    )
    session.add(new_wallet)
    session.commit()

    msg=await update.message.reply_text(f"✅ Added wallet `{nickname}` to slot {available_slot}", parse_mode="Markdown")
    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))

async def handle_delete_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except:
        pass  # if it's already gone or undeletable, ignore
    if not args:
        msg=await update.message.reply_text("⚠️ Usage: /del <nickname>")
        asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=15))
        return

    nickname = " ".join(args).strip().lower()

    wallet = session.query(SavedWallets).filter(
        SavedWallets.user_id == user_id,
        SavedWallets.nickname.ilike(nickname)
    ).first()

    if not wallet:
        msg=await update.message.reply_text(f"❌ No wallet found with nickname `{nickname}`.", parse_mode="Markdown")
        asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))
        return

    session.delete(wallet)
    session.commit()

    msg=await update.message.reply_text(f"✅ Deleted wallet `{wallet.nickname}` from slot {wallet.slot}", parse_mode="Markdown")
    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    HELP_TEXT = (
        "*📖 0xSniff Help Menu*\n\n"

        "*🧰 Commands:*\n"
        "/portfolio — Open your portfolio with all saved wallets\n"
        "/add <wallet> <nickname> — Save a wallet to your slots\n"
        "/del <nickname> — Delete a wallet by its nickname\n"
        "/rename <old> <new> — Rename a saved wallet\n"
        "/wipewallets — Remove all saved wallets\n"
        "/clearchat — Delete all messages sent by the bot\n"
        "/scoreboard — Show top token calls in the past 24h\n"
        "/help — Show this help menu\n\n"

        "*💬 Quick Actions:*\n"
        "Paste a *token address* to get a token summary\n"
        "Paste a *wallet address* to see wallet portfolio\n\n"

        "*💡 Tips:*\n"
        "• Always double-check data using provided links\n"
        "• Use the refresh button and watch for snipers or team sells\n"
        "• Only tokens with liquidity, value, and security score are shown\n"
        "• ETH balance is included in your portfolio value\n"
        "• Use Dexscreener / Dextools for deep token research\n\n"

        "*🧠 Reminder:*\n"
        "0xSniff doesn’t make financial decisions. You do.\n"
        "*Track smart. Trade smarter.*"
    )



    if update.message:
        await update.message.delete()
    msg=await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")
    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=60))

async def handle_rename_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if update.message:
        await update.message.delete()
    if len(args) < 2:
        msg = await update.message.reply_text("⚠️ Usage: /rename <old_nickname> <new_nickname>")
        asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=10))
        return

    old_nick, new_nick = args[0], " ".join(args[1:]).strip()

    wallet = session.query(SavedWallets).filter_by(user_id=user_id, nickname=old_nick).first()

    if not wallet:
        msg = await update.message.reply_text(f"❌ No wallet found with nickname `{old_nick}`.", parse_mode="Markdown")
        asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))
        return

    wallet.nickname = new_nick
    session.commit()

    msg = await update.message.reply_text(f"✅ Renamed `{old_nick}` to `{new_nick}`.", parse_mode="Markdown")
    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))

async def handle_clear_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message:
        await update.message.delete()
    # Delete all wallets for this user
    deleted = session.query(SavedWallets).filter_by(user_id=user_id).delete()
    session.commit()

    if deleted:
        msg = await update.message.reply_text("🗑️ All saved wallets have been cleared.")
    else:
        msg = await update.message.reply_text("⚠️ You have no saved wallets to clear.")

    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))

async def handle_clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Get all saved messages from DB for this user
    messages = session.query(UserInteraction).filter_by(user_id=user_id).all()

    deleted = 0
    for m in messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=m.message_id)
            deleted += 1
        except telegram.error.BadRequest:
            pass  # message not found or too old to delete
        except Exception as e:
            print(f"Error deleting message: {e}")

    # Optionally, delete user’s own recent messages (if in private chat)
    if update.message:
        chat = await context.bot.get_chat(chat_id)
        async for msg in chat.iter_history(limit=100):

            if msg.from_user.id == user_id:
                try:
                    await context.bot.delete_message(chat_id, msg.message_id)
                except:
                    pass

    # Don't delete from DB unless you want a full wipe
    await update.message.reply_text(f"🧹 Cleared {deleted} bot messages (and some user messages where possible).")

def register_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", handle_add_wallet))  
    application.add_handler(CommandHandler("del", handle_delete_wallet))  
    application.add_handler(CommandHandler("portfolio", handle_portfolio_command))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("rename", handle_rename_wallet))
    application.add_handler(CommandHandler("wipewallets", handle_clear_wallets))
    application.add_handler(CommandHandler("clearchat", handle_clear_chat))
    application.add_handler(CommandHandler("scoreboard", handle_scoreboard))


    application.add_handler(CallbackQueryHandler(handle_call_it, pattern="^call\\|"))
    application.add_handler(CallbackQueryHandler(handle_scoreboard, pattern="^scoreboard"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address))
    application.add_handler(CallbackQueryHandler(handle_tax_details, pattern="show_tax"))
    application.add_handler(CallbackQueryHandler(handle_token_summary, pattern="show_summary"))
    application.add_handler(CallbackQueryHandler(handle_refresh, pattern="refresh"))
    application.add_handler(CallbackQueryHandler(handle_tx_wallet_details, pattern="^show_tx_details\\|"))
    application.add_handler(CallbackQueryHandler(handle_about, pattern=r"^about_bot\|"))
    application.add_handler(CallbackQueryHandler(handle_portfolio_menu, pattern=r"^handle_portfolio_menu\|"))
    application.add_handler(CallbackQueryHandler(handle_portfolio_add_wallet, pattern=r"^portfolio_add_wallet\|"))
    application.add_handler(CallbackQueryHandler(handle_view_portfolio_wallet, pattern=r"^portfolio_view_wallet\|"))
    application.add_handler(CallbackQueryHandler(handle_market_prices, pattern="^market_prices$"))


    



    