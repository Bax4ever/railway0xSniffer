from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from bot.utils import get_change_arrow,format_mc
from bot.messages import generate_tax_details, generate_tx_wallet_details, generate_summary_response,format_wallet_summary,format_market_overview
import re
import asyncio
from services.token_analysis import main_async
from db import get_dynamic_token_data, save_token_dynamics, get_token_address_by_message_id,save_user_interaction, get_user_wallets,save_token_call,get_static_token_data
from db import session, SavedWallets,TokenCall
from portfolioTracker import portfolio_Tracker_function
from datetime import datetime,timedelta
from bot.utils import fetch_market_prices
from services.moralis_api import get_erc20_token_price_stats
from db import get_recent_token_calls
from services.moralis_api import get_multiple_token_prices_moralis_scoreboard  
import time

  # Store this globally or in-memory module-wide

async def handle_tx_wallet_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the transaction and wallet details view with pagination support."""
    query = update.callback_query
    await query.answer()

    # Extract message ID and page number from the callback data
    try:
        data_parts = query.data.split('|')
        if len(data_parts) < 2:
            raise ValueError("Invalid format")

        _, message_id_str = data_parts[0:2]
        current_page = int(data_parts[2]) if len(data_parts) == 3 else 1
        message_id = int(message_id_str.strip())
        token_address= get_token_address_by_message_id(message_id)


    except (ValueError, IndexError):
        await query.edit_message_text("Invalid request format. Please try again.")
        return

    # Generate transaction and wallet details for all pages
    page_data = generate_tx_wallet_details(token_address)
    if not page_data:
        await query.edit_message_text("No token data found for this message.")
        return    

    # Get the current page text and metadata
    if current_page < 1 or current_page > page_data["total_pages"]:
        await query.edit_message_text("Invalid page number. Please try again.")
        return

    page_text = page_data["pages"][current_page - 1]
     # Escape Markdown to avoid formatting errors

    # Create navigation buttons
    navigation_buttons = []
    if current_page > 1:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Previous Page", callback_data=f"show_tx_details|{message_id}|{current_page - 1}"))
    if current_page < page_data["total_pages"]:
        navigation_buttons.append(InlineKeyboardButton("➡️ Next Page", callback_data=f"show_tx_details|{message_id}|{current_page + 1}"))

    # Add buttons to switch back to summary or refresh
    keyboard = [
        [
            InlineKeyboardButton("📊 Token Summary", callback_data=f"show_summary|{message_id}"),
            InlineKeyboardButton("🔍 Tax Details", callback_data=f"show_tax|{message_id}"),
        ],
        navigation_buttons  # Add navigation buttons as a separate row
    ]
    reply_markup = InlineKeyboardMarkup([row for row in keyboard if row])

    # Edit the message to show the selected page of transaction and wallet details
    await query.edit_message_text(
        text=page_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def handle_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    # Extract message ID from the callback data
    try:
        _, message_id_str = query.data.split('|')
        message_id = message_id_str
    except ValueError:
        await query.edit_message_text("Invalid request format.")
        return

    token_address = get_token_address_by_message_id(message_id)
    if not token_address:
        await query.edit_message_text("❌ Could not extract token address.")
        return

    # Retrieve current refresh count from the message content
    current_text = query.message.text
    match = re.search(r"🔄Refreshed Count : (\d+)", current_text)
    refresh_count = int(match.group(1)) + 1 if match else 1

    save_user_interaction(refresh_count=refresh_count, message_id=message_id)

    # Load old data from DB
    old_data = get_dynamic_token_data(token_address)
    if not old_data:
        await query.edit_message_text("⚠️ No token data found for this message.")
        return

    old_bundle_percentage = old_data.curent_bundle_balance_token
    old_sniper_percentage = old_data.curent_sniper_balance_token_percent
    old_market_cap = old_data.market_cap_usd
    # Run fresh analysis (saves to DB, no return)
    curent_bundle_balance_token,curent_sniper_balance_token_percent,market_cap_usd,total_sniper_worth,total_bundle_worth=await main_async(token_address)
    bundle_arrow = get_change_arrow(old_bundle_percentage, curent_bundle_balance_token)
    sniper_arrow = get_change_arrow(old_sniper_percentage, curent_sniper_balance_token_percent)
    market_cap_arrow = get_change_arrow(old_market_cap, market_cap_usd)

    save_token_dynamics(
        market_cap_usd=market_cap_usd,
        token_address=token_address,
        bundle_arrow=bundle_arrow,
        sniper_arrow=sniper_arrow,
        market_cap_arrow=market_cap_arrow,
        curent_bundle_balance_token=curent_bundle_balance_token,
        curent_sniper_balance_token_percent=curent_sniper_balance_token_percent,
        total_sniper_worth=total_sniper_worth,
        total_bundle_worth=total_bundle_worth
    )


    # Generate the updated summary
    summary_text = generate_summary_response(token_address)

    # Inline button menu
    keyboard = [
        [  # Row 1
            InlineKeyboardButton("📈 Tax", callback_data=f"show_tax|{message_id}"),
            InlineKeyboardButton("📦 TX Details", callback_data=f"show_tx_details|{message_id}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh|{message_id}")
        ],
        [  # Row 2
            InlineKeyboardButton("📣 Call It", callback_data=f"call|{token_address}"),
            InlineKeyboardButton("🏆 Scoreboard", callback_data=f"scoreboard|{message_id}")
        ],
        [  # Row 3
            InlineKeyboardButton("🏷️ Prices", callback_data="market_prices"),
            InlineKeyboardButton("ℹ️ About", callback_data=f"about_bot|{message_id}"),
            InlineKeyboardButton("📂 Portfolio", callback_data=f"handle_portfolio_menu|{message_id}")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Update message
    await query.edit_message_text(
        text=f"🔄Refreshed Count : {refresh_count}\n" + summary_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

    # Show short-lived confirmation message
    temporary_message = await query.message.reply_text(f"✅ Refreshed Count: {refresh_count}")
    await asyncio.sleep(2)
    await temporary_message.delete()

async def handle_tax_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the tax details view with a button to switch to the token summary."""
    query = update.callback_query
    await query.answer()
    # Extract message ID from the callback data
    _, message_id_str = query.data.split('|')
    message_id = int(message_id_str)
    token_address=get_token_address_by_message_id(message_id)
    # Generate tax details text
    tax_text = generate_tax_details(token_address)
    if not tax_text:
        await query.edit_message_text("No token data found for this message.")
        return

    # Create buttons to switch back to summary or refresh
    keyboard = [
        [  # Row 1
            InlineKeyboardButton("📊 Token Summary", callback_data=f"show_summary|{message_id}"),
            InlineKeyboardButton("📦 TX Details", callback_data=f"show_tx_details|{message_id}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh|{message_id}")
        ],
        [  # Row 2
            InlineKeyboardButton("📣 Call It", callback_data=f"call|{token_address}"),
            InlineKeyboardButton("🏆 Scoreboard", callback_data=f"scoreboard|{message_id}")
        ],
        [  # Row 3
            InlineKeyboardButton("🏷️ Prices", callback_data="market_prices"),
            InlineKeyboardButton("ℹ️ About", callback_data=f"about_bot|{message_id}"),
            InlineKeyboardButton("📂 Portfolio", callback_data=f"handle_portfolio_menu|{message_id}")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Enable MarkdownV2 for safe Markdown usage
    await query.edit_message_text(
        text=tax_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )

async def handle_token_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switches back to the token summary view."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    # Extract the message ID from the callback data
    _, message_id_str = query.data.split('|')
    message_id = int(message_id_str)

    token_address=get_token_address_by_message_id(message_id)
    # Generate the summary view again
    summary_text = generate_summary_response(token_address)

    # Create keyboard with message ID
    keyboard = [
        [  # Row 1
            InlineKeyboardButton("📈 Tax", callback_data=f"show_tax|{message_id}"),
            InlineKeyboardButton("📦 TX Details", callback_data=f"show_tx_details|{message_id}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh|{message_id}")
        ],
        [  # Row 2
            InlineKeyboardButton("📣 Call It", callback_data=f"call|{token_address}"),
            InlineKeyboardButton("🏆 Scoreboard", callback_data=f"scoreboard|{message_id}")
        ],
        [  # Row 3
            InlineKeyboardButton("🏷️ Prices", callback_data="market_prices"),
            InlineKeyboardButton("ℹ️ About", callback_data=f"about_bot|{message_id}"),
            InlineKeyboardButton("📂 Portfolio", callback_data=f"handle_portfolio_menu|{message_id}")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=summary_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def handle_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    try:
        _, message_id_str = query.data.split('|')
        message_id = int(message_id_str)
    except (ValueError, IndexError):
        await query.edit_message_text("⚠️ Invalid request format.")
        return
    token_address=get_token_address_by_message_id(message_id)
    ABOUT_TEXT = (
        "🤖 *0xSniff Bot*\n\n"

        "0xSniff scans Ethereum tokens and wallet portfolios to show:\n"
        "• Bundle/sniper wallet behavior\n"
        "• Token tax structure\n"
        "• Liquidity & market cap\n"
        "• Volume & transactional stats\n\n"

        "📊 *Token Summary Guide:*\n"
        "🔹 *Clog* – Tokens in smart contract (tax sink)\n"
        "🔹 *Bundle Wallets* – Team/private wallets — First buyers\n"
        "🔹 *Sniper Wallets* – Bots/wallets that snipe launch — Second buyers\n"
        "🔹 *Initial* – Amount of tokens first acquired\n"
        "🔹 *Total* – Current token holdings\n"
        "🔹 *Unsold Worth* – ETH value of current holdings\n"
        "🔹 *Total ETH (B/S)* – ETH extracted by bundles or snipers\n"
        "🔹 *Arrows (🔼/🔽)* – Shows change since last check\n\n"

        "🏆 *Scoreboard:*\n"
        "Use */scoreboard* to see the top token calls made by users in the last 24h.\n"
        "Ranks are based on % gain since each call.\n"
        "Displays:\n"
        "• Token symbol and gain %\n"
        "• Market cap and liquidity\n"
        "• Etherscan + DEX links\n"
        "• Top 10 overall + your top 3\n\n"

        "💡 *Tip:* Use links to DYOR. Always verify liquidity, holders, and TX patterns.\n\n"

        "🛠 *Built by:* [Baxiks](https://t.me/Baxiks)\n"
        "📂 *GitHub:* [0xSniff on GitHub](https://github.com/Bax4ever/botv2)\n"
        "📬 *Contact:* @Baxiks"
    )


    keyboard = [
        [  # Row 1
            InlineKeyboardButton("📈 Tax", callback_data=f"show_tax|{message_id}"),
            InlineKeyboardButton("📦 TX Details", callback_data=f"show_tx_details|{message_id}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh|{message_id}")
        ],
        [  # Row 2
            InlineKeyboardButton("📣 Call It", callback_data=f"call|{token_address}"),
            InlineKeyboardButton("🏆 Scoreboard", callback_data=f"scoreboard|{message_id}")
        ],
        [  # Row 3
            InlineKeyboardButton("🏷️ Prices", callback_data="market_prices"),
            InlineKeyboardButton("📊 Token Summary", callback_data=f"show_summary|{message_id}"),
            InlineKeyboardButton("📂 Portfolio", callback_data=f"handle_portfolio_menu|{message_id}")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=ABOUT_TEXT,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=False
    )

async def handle_portfolio_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # prevent Telegram from showing the loading spinner forever

    user_id = query.from_user.id
    _, message_id_str = query.data.split('|')
    message_id = int(message_id_str)  # Optional: extract message ID if needed
    wallets=get_user_wallets(user_id)
    # Load wallets from DB or stub
    #wallets = get_saved_wallets(user_id)  # <- this should return a list of saved wallets for this user
    keyboard = build_portfolio_keyboard(wallets,message_id)

    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text="📊 Portfolio Overview:\nSelect a wallet to track or manage:",
        reply_markup=keyboard
    )

async def handle_portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        wallets = get_user_wallets(user_id)
        if update.message:
            await update.message.delete()

        keyboard = build_portfolio_keyboard(wallets, message_id=None)
        text = "💼 *Portfolio Menu*\nSelect a wallet slot to view or manage."

        await update.message.reply_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    except Exception as e:
        print(f"⚠️ Error in /portfolio: {e}")
        await update.message.reply_text("⚠️ Something went wrong opening your portfolio.")

def build_portfolio_keyboard(wallets, message_id=None, max_slots=4):
    keyboard = []

    for slot in range(max_slots):
        wallet = wallets[slot] if slot < len(wallets) else None

        if wallet:
            label = f"💼 {wallet.get('nickname')}"
            callback_data = f"portfolio_view_wallet|{slot}"
        else:
            label = "➕ Empty Slot"
            callback_data = f"portfolio_add_wallet|{slot}"

        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])

    # Refresh button to update the portfolio menu
    keyboard.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"handle_portfolio_menu|{message_id or 0}")
    ])

    if message_id:
        keyboard.append([
            InlineKeyboardButton("⬅️ Back to Summary", callback_data=f"show_summary|{message_id}")
        ])

    return InlineKeyboardMarkup(keyboard)

async def handle_portfolio_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Extract slot from callback_data
    _, slot_str = query.data.split("|")
    slot = int(slot_str)

    # Save the slot in user_data to know what to fill next
    context.user_data["pending_wallet_slot"] = slot
    msg=await update.effective_message.reply_text(" Please enter wallet address:")
    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=4))
    
async def delete_later(bot, chat_id, message_id, delay=4):
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except BadRequest as e:
        if "message to delete not found" not in str(e).lower():
            raise

async def handle_view_portfolio_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        _, slot_str = query.data.split("|")
        slot = int(slot_str)
    except ValueError:
        await query.message.reply_text("⚠️ Invalid wallet slot.")
        return

    user_id = update.effective_user.id
    wallet = session.query(SavedWallets).filter_by(user_id=user_id, slot=slot).first()

    if not wallet:
        await query.message.reply_text("❌ No wallet found in this slot.")
        return
    nickname = wallet.nickname or "Wallet"
    loading_msg = await query.message.reply_text(
        f"🔍 Fetching data for `{nickname}`...", parse_mode="Markdown"
    )
    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, loading_msg.message_id,delay=4))
    # Fetch DexScreener data using the wallet address
    token_data,eth_balance =await portfolio_Tracker_function([wallet.address])
    
    if not token_data:
        await query.message.reply_text("❌ Could not fetch token info for this wallet.")
        prompt=asyncio.create_task(delete_later(context.bot, update.effective_chat.id, prompt.message_id, delay=4))
        return
    
    msg=format_wallet_summary(token_data,eth_balance,nickname,wallet)

    load_message=await query.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
    prompt=asyncio.create_task(delete_later(context.bot, update.effective_chat.id, load_message.message_id, delay=30))

async def render_wallet_summary(update, context, wallet_address: str):
    user_id = update.effective_user.id

    # Try to fetch saved nickname from DB
    wallet = session.query(SavedWallets).filter_by(user_id=user_id, address=wallet_address).first()
    if wallet:
        nickname = wallet.nickname
        wallet_obj = wallet
    else:
        nickname = wallet_address[:6] + "..." + wallet_address[-4:]
        # Mock a fake wallet object for formatting
        FakeWallet = type("FakeWallet", (object,), {"address": wallet_address})
        wallet_obj = FakeWallet()

    # Fetch token and ETH data
    tokens, eth_balance = await portfolio_Tracker_function([wallet_address])

    if not tokens:
        await update.message.reply_text("❌ Could not fetch token info for this address.")
        return

    msg = format_wallet_summary(tokens, eth_balance, nickname, wallet_obj)
    msgR=await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msgR.message_id, delay=30))

async def handle_market_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = await fetch_market_prices()
        time = datetime.utcnow()
        text = format_market_overview(data,time)
        message_id = update.callback_query.message.message_id
        token_address=get_token_address_by_message_id(message_id)
        # Use your full token keyboard layout
        keyboard = [
            [  # Row 1
                InlineKeyboardButton("📈 Tax", callback_data=f"show_tax|{message_id}"),
                InlineKeyboardButton("📦 TX Details", callback_data=f"show_tx_details|{message_id}"),
                InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh|{message_id}")
            ],
            [  # Row 2
                InlineKeyboardButton("📣 Call It", callback_data=f"call|{token_address}"),
                InlineKeyboardButton("🏆 Scoreboard", callback_data=f"scoreboard|{message_id}")
            ],
            [  # Row 3
                InlineKeyboardButton("📊 Token Summary", callback_data=f"show_summary|{message_id}"),
                InlineKeyboardButton("ℹ️ About", callback_data=f"about_bot|{message_id}"),
                InlineKeyboardButton("📂 Portfolio", callback_data=f"handle_portfolio_menu|{message_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
        await update.callback_query.answer()

    except Exception as e:
        print(f"❌ Market fetch error: {e}")
        await update.callback_query.answer("Failed to load prices.", show_alert=True)

async def handle_call_it(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    username = user.username
    first_name = user.first_name

    try:
        data_parts = query.data.split("|")
        token_address = data_parts[1] if len(data_parts) > 1 else None
        message_id = int(data_parts[2]) if len(data_parts) > 2 else query.message.message_id
        user_id = str(query.from_user.id)

        if token_address is None:
            token_address = get_token_address_by_message_id(message_id)

        # Always fetch live price
        price_data = get_erc20_token_price_stats(token_address)
        price = price_data.get("usdPrice", 0)


        # Try to fetch metadata
        token_data = get_static_token_data(token_address)
        if token_data:
            symbol = token_data.get("token_symbol", "???")
            name = token_data.get("token_name", "Unknown")
        else:
            symbol = price_data.get("symbol", "???")
            name = price_data.get("name", "Unknown")

        success = save_token_call(user_id, token_address, symbol, price, name, username, first_name)

        if success:
            msg=await context.bot.send_message(chat_id=user_id, text="📣 Call saved!")
            asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))

        else:
           msg=await context.bot.send_message(chat_id=user_id, text="📣 Already called this token in the last 24h!") 
           asyncio.create_task(delete_later(context.bot, update.effective_chat.id, msg.message_id, delay=6))          


        old_keyboard = query.message.reply_markup.inline_keyboard
        new_keyboard = []
        for row in old_keyboard:
            new_row = []
            for btn in row:
                if btn.callback_data and btn.callback_data.startswith("call|"):
                    new_row.append(InlineKeyboardButton("✅ Called", callback_data="noop"))
                else:
                    new_row.append(btn)
            new_keyboard.append(new_row)

     
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(new_keyboard))

        # Respond based on call status


    except Exception as e:
        print(f"❌ Error in handle_call_it: {e}")
        await query.answer("Something went wrong.", show_alert=True)

def build_token_action_keyboard(user_id, token_address, price, message_id):
    called_recently = check_if_user_called(user_id, token_address)

    call_button = (
        InlineKeyboardButton("✅ Called", callback_data="noop")
        if called_recently else
        InlineKeyboardButton("📣 Call It", callback_data=f"call|{token_address}|{message_id}")
    )

    keyboard = [
        [
            InlineKeyboardButton("📈 Tax", callback_data=f"show_tax|{message_id}"),
            InlineKeyboardButton("📦 TX Details", callback_data=f"show_tx_details|{message_id}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh|{message_id}")
        ],
        [
            call_button,
            InlineKeyboardButton("🏆 Scoreboard", callback_data=f"scoreboard|{message_id}")
        ],
        [
            InlineKeyboardButton("🏷️ Prices", callback_data="market_prices"),
            InlineKeyboardButton("ℹ️ About", callback_data=f"about_bot|{message_id}"),
            InlineKeyboardButton("📂 Portfolio", callback_data=f"handle_portfolio_menu|{message_id}")
        ]
    ]

    return InlineKeyboardMarkup(keyboard)

def check_if_user_called(user_id , token_address: str) -> bool:
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        call = session.query(TokenCall).filter(
            TokenCall.user_id == user_id,
            TokenCall.token_address == token_address.lower(),
            TokenCall.timestamp > cutoff
        ).first()
        return call is not None
    finally:
        session.close()

async def handle_scoreboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        reply = query.message.reply_text
    elif update.message:
        query = update.message
        reply = query.reply_text
    else:
        return  # fallback safety
    price_cache = {}
    user_id = query.from_user.id
    recent_calls = get_recent_token_calls(hours=24)
   #print(recent_calls)
   #print(f"[DEBUG] Found {len(recent_calls)} recent calls.")
    if not recent_calls:
        await update.message.reply_text("No calls made in the last 24h.")
        return

    token_addresses = list(set(call.token_address for call in recent_calls))
    now = time.time()

    tokens_to_fetch = [addr for addr in token_addresses if addr not in price_cache or now - price_cache[addr]["timestamp"] > 300]
  # print(tokens_to_fetch)
    if tokens_to_fetch:
        updated_prices = get_multiple_token_prices_moralis_scoreboard(tokens_to_fetch)
       #print(updated_prices)
        for token in updated_prices:
            addr = token.get("token_address", "").lower()
            price_cache[addr] = {
                "price": token.get("price"),
                "liquidity": token.get("liquidity", 0),
                "scam": token.get("scam", False),
                "timestamp": now
            }
           #print(updated_prices)

    scores = []
    for call in recent_calls:
        token_info = price_cache.get(call.token_address)
        if not token_info or call.price == 0:
            continue
        price_now = token_info["price"]
        change = ((price_now - call.price) / call.price) * 100
        scores.append({
            "user_id": call.user_id,
            "symbol": call.symbol,
            "price_at_call": call.price,
            "price_now": price_now,
            "change": change,
            "username": call.username,
            "first_name": call.first_name,
            "token_address": call.token_address
        })


    top_calls = sorted(scores, key=lambda x: x["change"], reverse=True)[:10]
    your_best = sorted((c for c in scores if c["user_id"] == user_id), key=lambda x: x["change"], reverse=True)[:3]
   #print(top_calls,your_best)

    lines = ["<b>🏆 Top Calls (24h)</b>"]
    for i, entry in enumerate(top_calls, 1):
        token_address = entry["token_address"]
        token_info = price_cache.get(token_address, {})
        token_data = get_static_token_data(token_address)

        user_tag = (
            "👉 You" if entry["user_id"] == user_id
            else f"@{entry['username']}" if entry.get("username")
            else entry.get("first_name", f"user_{entry['user_id'][-4:]}")
        )

        liq = token_info.get("liquidity", 0)
        price = token_info.get("price", 0)
        supply = float(token_data.get("total_supply", 0))
        mc = price * supply if price and supply else 0
        scam = token_info.get("scam", False)

        short_addr = f'<a href="https://etherscan.io/address/{token_address}"><code>{token_address[:6]}...{token_address[-4:]}</code></a>'
        liq_str = format_mc(liq)
        mc_str = format_mc(mc)
        scam_str = " ⚠️Scam" if scam else ""
        change_str = f"{entry['change']:+.1f}%"

        tokensniffer_url = f"https://tokensniffer.com/token/eth/{token_address}"
        dextools_url = f"https://www.dextools.io/app/en/ether/pair-explorer/{token_address}"
        dexscreener_url = f"https://dexscreener.com/ethereum/{token_address}"

        # Line 1: rank. username — symbol +X.X%
        lines.append(f"<b>{i}. {user_tag}</b> — {entry['symbol']} {change_str}")

        # Line 2: MC | LIQ | 0xABC...1234 + scam
        lines.append(f"💵{mc_str} | 💧{liq_str} | {short_addr}{scam_str}")

        # Line 3: Link row
        lines.append(
            f'<a href="{tokensniffer_url}">Sniffer</a> | '
            f'<a href="{dextools_url}">Dextools</a> | '
            f'<a href="{dexscreener_url}">DexScreener</a>'
        )
        lines.append("")  # 👈 this creates the space between top entries
    
    if your_best:
        lines.append("\n<b>🔥 Your Best Calls</b>\n")
    for i, entry in enumerate(your_best, 1):
        token_address = entry["token_address"]
        token_info = price_cache.get(token_address, {})
        token_data = get_static_token_data(token_address)

        liq = token_info.get("liquidity", 0)
        price = token_info.get("price", 0)
        supply = float(token_data.get("total_supply", 0))
        mc = price * supply if price and supply else 0
        scam = token_info.get("scam", False)

        short_addr = f'<a href="https://etherscan.io/address/{token_address}"><code>{token_address[:6]}...{token_address[-4:]}</code></a>'

        liq_str = format_mc(liq)
        mc_str = format_mc(mc)
        scam_str = " ⚠️Scam" if scam else ""
        change_str = f"{entry['change']:+.1f}%"

        tokensniffer_url = f"https://tokensniffer.com/token/eth/{token_address}"
        dextools_url = f"https://www.dextools.io/app/en/ether/pair-explorer/{token_address}"
        dexscreener_url = f"https://dexscreener.com/ethereum/{token_address}"

        # Line 1: Your best X. SYMBOL +X.X%
        lines.append(f"<b>{i}. {entry['symbol']}</b> {change_str}")

        # Line 2: MC | LIQ | 0xABC...1234
        lines.append(f"💵{mc_str} | 💧{liq_str} | {short_addr}{scam_str}")

        # Line 3: Link row
        lines.append(
            f'<a href="{tokensniffer_url}">Sniffer</a> | '
            f'<a href="{dextools_url}">Dextools</a> | '
            f'<a href="{dexscreener_url}">DexScreener</a>'
        )

   
    text = "\n".join(lines)
    sent = await reply(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


    asyncio.create_task(delete_later(context.bot, update.effective_chat.id, sent.message_id, delay=30))
