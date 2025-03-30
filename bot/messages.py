from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.utils import format_number_with_spaces,parse_tags
import json
from db import SessionLocal,Token
from db import get_static_token_data, get_dynamic_token_data, get_transaction_snapshots,save_user_interaction,get_token_address_by_message_id,save_token_dynamics
from datetime import datetime
from services.etherscan_api import get_latest_eth_price

def generate_summary_response(token_address) -> str:
    # Use token address from original context
    
    snaps=get_transaction_snapshots(token_address)
    if not snaps:
        return "❌ Error: snaps data not found in DB."
    # ✅ Static data
    static_data = get_static_token_data(token_address)
    # Find first block tagged as zero_block (first trade)
    first_trade_block = min(
        (s.block_number for s in snaps if s.block_number and "zero_block" in parse_tags(s.tags or [])),
        default=None
)
    pre_trading_transfers = [
    s for s in snaps
    if "transfer" in parse_tags(s.tags or []) and (s.block_number or 99999999) < first_trade_block]
    total_transfer_tokens = sum(s.transfer_amount or 0 for s in pre_trading_transfers)
    
    pre_trade_percent = total_transfer_tokens / int(static_data["total_supply"]) * 100 if static_data.get("total_supply") else 0
    alert_line=""
    if pre_trade_percent>1:
        alert_line = f"🚨 *Pre-Trading Transfers Detected:* {pre_trade_percent:.2f}% of supply moved before trading!\n"

    if not static_data:
        return "❌ Error: Static token data not found in DB."

    # ✅ Dynamic data
    analytics_data = get_dynamic_token_data(token_address)
    if not analytics_data:
        return "❌ Error: Dynamic analytics data not found in DB."
    
    # Supply and volume
    supply = int(static_data["total_supply"])
    totVol = 0 if analytics_data.totalVolumen1 == "N/A" else int(analytics_data.totalVolumen1)

    # 🔗 Parse links
    links_raw = static_data.get("links", "{}")
    try:
        links = json.loads(links_raw) if isinstance(links_raw, str) else links_raw
    except json.JSONDecodeError:
        #print("⚠️ Could not decode links from DB:", links_raw)
        links = {}
    if not isinstance(links, dict):
        #print("⚠️ Expected dict for links, got:", type(links))
        links = {}

    links_text = (
        " | ".join(
            f"[TG]({value})" if "tg" in key.lower()
            else f"[X]({value})" if "x" in key.lower()
            else f"[Web]({value})" if "web" in key.lower()
            else f"[{key.capitalize()}]({value})"
            for key, value in links.items()
        ) if links else "None"
    )

    if static_data.get("pairA"):
        links_text += " | " + " | ".join([
            f"[DEXT](https://www.dextools.io/app/en/ether/pair-explorer/{static_data['pairA']})",
            f"[DEXS](https://dexscreener.com/ethereum/{static_data['pairA']})"
        ])

    maestro_bot_username = "MaestroSniperBot"
    snaps = get_transaction_snapshots(token_address)
    if snaps:
        sniper_total = sum(
            s.token_balance or 0.0
            for s in snaps 
            if any("sniper" in tag.lower() for tag in parse_tags(s.tags)) 
            and not any("bundle" in tag.lower() for tag in parse_tags(s.tags))
        )

        bundle_total = sum(
            s.token_balance or 0.0
            for s in snaps 
            if any("bundle" in tag.lower() for tag in parse_tags(s.tags))
        )
        rounded_bundle_balance = round(bundle_total, 2)  # Optional
        rounded_sniper_balance = round(sniper_total, 2)
        save_token_dynamics(
        **{
        "token_address": token_address,
        "curent_bundle_balance_token": rounded_bundle_balance,
        "curent_sniper_balance_token_percent": rounded_sniper_balance,
        })
    else:
        print(f"⚠️ TokenDynamic entry not found for: {token_address}")
    return (
        f"🪙 Token Details:\n"
        f"|[{static_data['token_symbol']}](https://etherscan.io/token/{token_address})|{links_text}|`{token_address}`🔗\n"
        f"Name: {static_data['token_name']} | Symbol: {static_data['token_symbol']}\n"
        f"💵 Market Cap: ${format_number_with_spaces(analytics_data.market_cap_usd)}{analytics_data.market_cap_arrow or ''}\n"
        f"📦Total Supply: {format_number_with_spaces(supply)}\n"
        f"💧Liq:${format_number_with_spaces(analytics_data.reserveUSD)}|🔁TotalTx: {analytics_data.tx_count}|💱(24h)Vol:${format_number_with_spaces(analytics_data.totalVolumen)}|🟢B: {int(analytics_data.buys_24h)}|🔴S :{int(analytics_data.sells_24h)}\n"
        f"|🤖[Trade with Maestro Bot](https://t.me/{maestro_bot_username}?start={token_address})|\n "
        f"\n{alert_line}\n "
        f"\n📊 Summary:\n"
        f"📈 Clog: {format_number_with_spaces(analytics_data.clog)} | {analytics_data.clog_percent:.1f}%\n"
        f"👛 Bundle Wallets: {static_data['b_count']} | 🤖 Sniper Wallets: {static_data['s_count']}\n"
        f"🧊 Initial Bundle Tokens:  {format_number_with_spaces(static_data['total_recivedB'])} ({(static_data['recivedB_percent'] or 0):.1f}%)\n"
        f"🧊 Initial Sniper Tokens: {format_number_with_spaces(static_data['total_recivedS'])} ({(static_data['recivedS_percent']or 0):.1f}%)\n"
        f"🔹 Total Bundle Tokens: {format_number_with_spaces(bundle_total)} "
        f"({bundle_total / supply * 100:.1f}%" +
        (f"{analytics_data.bundle_arrow}" if analytics_data.bundle_arrow else "") + ")\n"
        f"💎 Unsold Bundle Worth: {analytics_data.total_bundle_worth:,.2f} ETH\n"
        f"🔹 Total Sniper Tokens: {format_number_with_spaces(sniper_total)} "
        f"({sniper_total / supply * 100:.1f}%" +
        (f"{analytics_data.sniper_arrow}" if analytics_data.sniper_arrow else "") + ")\n"
        f"💎 Unsold Sniper Worth: {analytics_data.total_sniper_worth:,.2f} ETH\n"


        f"💰 Total Bundle ETH: {analytics_data.total_ethb:.2f} ETH\n"
        f"💰 Total Sniper ETH: {analytics_data.total_eths:.2f} ETH\n"
        f"[TokenSniffer](https://tokensniffer.com/token/1/{token_address})|[goPlus](https://gopluslabs.io/token-security/1/{token_address})\n"
    )

def generate_tax_details(token_address) -> str:

    session = SessionLocal()
    try:
        static_data = session.query(Token).filter(
            Token.token_address.ilike(token_address.strip())
        ).first()

        if not static_data or not static_data.tax:
            return "⚠️ No tax details found for this token."

        # explicitly parse JSON from the 'tax' column
        tax_data = json.loads(static_data.tax) if isinstance(static_data.tax, str) else static_data.tax

        tax_details_text = (
            f"📌 **Tax Details** 📌\n"
            f"Initial Buy Tax: {tax_data.get('_initialBuyTax', 'N/A') or 'N/A'}%\n"
            f"Initial Sell Tax: {tax_data.get('_initialSellTax', 'N/A') or 'N/A'}%\n"
            f"Final Buy Tax: {tax_data.get('_finalBuyTax', 'N/A') or 'N/A'}%\n"
            f"Final Sell Tax: {tax_data.get('_finalSellTax', 'N/A') or 'N/A'}%\n"
            f"Reduce Buy Tax At: {tax_data.get('_reduceBuyTaxAt', 'N/A') or 'N/A'}\n"
            f"Reduce Sell Tax At: {tax_data.get('_reduceSellTaxAt', 'N/A') or 'N/A'}\n"
            f"Prevent Swap Before: {tax_data.get('_preventSwapBefore', 'N/A') or 'N/A'}\n"
            f"Transfer Tax: {tax_data.get('_transferTax', 'N/A') or 'N/A'}%\n"
            f"Buy Count: {tax_data.get('_buyCount', 'N/A') or 'N/A'}\n"
        )

        # Telegram markdown escape
        tax_details_text = tax_details_text.replace('.', '\\.')

        return tax_details_text

    except Exception as e:
        #print(f"❌ DB Error explicitly retrieving tax details: {e}")
        return "⚠️ An error occurred while retrieving tax details."
    finally:
        session.close()

def generate_tx_wallet_details(token_address, page_size=11) -> dict:
    transactions = get_transaction_snapshots(token_address)
    MAX_TELEGRAM_MESSAGE_LENGTH = 2220

    bundle_txs = [tx for tx in transactions if any('bundle' in (tag or '').lower() for tag in parse_tags(tx.tags))]
    sniper_txs = [tx for tx in transactions if any('sniper' in (tag or '').lower() for tag in parse_tags(tx.tags)) and tx not in bundle_txs]
    filtered_transactions = bundle_txs + sniper_txs


    if not filtered_transactions:
        return {
            "pages": ["🔗 **Recent Transactions**\n\nNo sniper or bundle transactions found for this token."],
            "total_pages": 1
        }

    pages = []
    current_page = []
    total_length = 0
    transaction_count = 0

    for tx in filtered_transactions:
        transaction_count += 1
        
        tx_hash = tx.tx_hash
        value_in_ether = tx.value_in_ether or 0.0
        token_value = tx.token_value or 0.0
        received_percentage = tx.received_percent or 0.0
        token_balance = tx.token_balance or 0.0
        balance_percentage = tx.balance_percent or 0.0
        eth_balance = tx.eth_balance or 0.0
        from_address_short = tx.from_address[:6] if tx.from_address else 'Unknown'

        tags = tx.tags or []
        filtered_tags = [tag for tag in tags if 'bundle' in tag.lower() or 'sniper' in tag.lower()]
        tags_text = ', '.join(filtered_tags)

        tx_link = f"[{from_address_short}](https://etherscan.io/tx/{tx_hash})"

        transaction_text = (
            f"\n{transaction_count}.{tx_link}"
            f"\n💰 {value_in_ether:.2f} ETH ➡️ {token_value:.1f} tokens ({received_percentage:.1f}%) |"
            f"\n📊 Balance: {token_balance:.1f} TOK ({balance_percentage:.0f}%) | {eth_balance:.2f} ETH | "
            f"{tags_text}\n"
        )

        if total_length + len(transaction_text) > MAX_TELEGRAM_MESSAGE_LENGTH:
            pages.append(current_page)
            current_page = []
            total_length = 0

        current_page.append(transaction_text)
        total_length += len(transaction_text)

    if current_page:
        pages.append(current_page)

    formatted_pages = []
    for page_number, page_content in enumerate(pages, start=1):
        page_text = "🔗 **Recent Transactions**\n"
        page_text += "".join(page_content)
        page_text += f"\nPage {page_number} of {len(pages)}\n"
        formatted_pages.append(page_text)

    return {
        "pages": formatted_pages,
        "total_pages": len(formatted_pages)
    }

async def show_summary(message_id, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the token summary view with buttons for tax and transaction details."""
    
    user_id = update.effective_user.id
    username = update.effective_user.username
    request_time = datetime.utcnow()


    token_address = get_token_address_by_message_id(message_id)
    if not token_address:
        if update.message:
            await update.message.reply_text("⚠️ No token data found. Please enter a valid address.")
        elif update.callback_query and update.callback_query.message:
            await update.callback_query.message.edit_text("⚠️ No token data found. Please enter a valid address.")
        return
 
    summary_text = generate_summary_response(token_address)

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

    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text(
            text=summary_text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    elif hasattr(update, "message") and update.message:
        sent_message = await update.message.reply_text(
            text=summary_text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

        # ✅ Only save interaction if this is a new message
        save_user_interaction(
            user_id=user_id,
            username=username,
            message_id=sent_message.message_id,
            token_address=token_address,
            requested_at=request_time
        )

def format_wallet_summary(tokens, eth_balance, nickname, wallet):
    if not tokens:
        return "⚠️ No tokens found in this wallet."

    lines = []

    # ETH & total value
    eth_price_usd = get_latest_eth_price()
    total_usd_value = sum(token.get("usd_value", 0) for token in tokens)
    eth_usd_value = eth_balance * eth_price_usd if eth_price_usd else 0
    total_usd = total_usd_value + eth_usd_value

    # Wallet link
    etherscan_url = f"https://etherscan.io/address/{wallet.address}"

    # Header
    lines.append(f"💼 *{nickname}  Summary*")
    lines.append(f"🔎 [{wallet.address}]({etherscan_url})\n")
    lines.append(f"💰 Total Value: *${total_usd:,.2f}*")
    lines.append(f"Ξ ETH Balance: {eth_balance:,.4f} (${eth_usd_value:,.2f})\n")

    # Tokens section
    lines.append("🪙 *Tokens:*")

    for idx, token in enumerate(tokens, start=1):
        symbol = token.get("symbol", "N/A")
        balance = token.get("balance", 0)
        usd_value = token.get("usd_value", 0)
        price_usd = token.get("price_usd", 0)
        liquidity = token.get("liquidity_usd", 0)
        pair_url = token.get("pair_url", "")
        pair_address = token.get("pair_address", "")
        price_change = token.get("price_change_24h", "")
        listed_at = token.get("listed_at")
        security_score = token.get("security_score", "N/A")

        # Format date
        listed_date = "N/A"
        if listed_at:
            try:
                ts = int(listed_at)
                listed_date = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            except:
                pass

        # Format values
        balance_str = f"{balance:,.4f}"
        usd_str = f"${usd_value:,.2f}"
        price_str = f"${price_usd:,.6f}" if price_usd else "$0.000000"
        liq_str = f"${liquidity:,.0f}" if liquidity else "$0"
        try:
            change_str = f"{round(float(price_change))}%" if price_change not in [None, '', 'null'] else "N/A"
        except:
            change_str = "N/A"


        # Links
        dex_link = f"[DexS]({pair_url})" if pair_url else "DexS"
        dextools_link = f"[DexT](https://www.dextools.io/app/en/ether/pair-explorer/{pair_address})" if pair_address else "DexT"

        # Token display
        lines.append(
            f"{idx}.*{symbol}*:{balance_str}({usd_str})|🛡️ Score:{security_score}\n"
            f"💲{price_str}|📈24h:{change_str}|💧{liq_str}\n"
            #f"   🕒 Listed: {listed_date} | {dex_link} | {dextools_link}"
        )

    return "\n\n".join(lines)

def format_market_overview(data: dict,time) -> str:
    coin_symbols = {
        "bitcoin": "₿ BTC",
        "ethereum": "Ξ ETH",
        "binancecoin": "🟡 BNB",
        "solana": "◎ SOL",
        "toncoin": "🔵 TON",
        "sui": "🌀 SUI",
        "pulsechain": "🧬 PLS",
        "polygon": "🔷 MATIC",
        "cardano": "🧠 ADA",
    }

    lines = ["📈 Market Overview\n"]
    for coin_id, symbol in coin_symbols.items():
        if coin_id in data:
            price = data[coin_id].get("usd", 0)
            change = data[coin_id].get("usd_24h_change", 0)
            emoji = "🔺" if change > 0 else "🔻"
            lines.append(f"{symbol:<7} ${price:,.2f}  {emoji} {change:+.2f}%")
    lines.append(f"\n⏱ Last updated: {time}")
    return "\n".join(lines)
