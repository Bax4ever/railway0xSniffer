import re
from telegram import Update
from bot.config import INFURA_URL
import asyncio
import aiohttp
import json
from db import SessionLocal,TransactionSnapshot
from web3 import Web3
from bot.config import ANKR_URL
import requests
import httpx

# Free public Ethereum RPC
w3 = Web3(Web3.HTTPProvider(ANKR_URL))
COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price"
# Simple in-memory cache
address_type_cache = {}
COINS = [
    "bitcoin", "ethereum", "binancecoin", "solana", "toncoin", "sui", "pulsechain",
    "polygon", "cardano"
]

def is_contract_address(address: str) -> bool:
    """
    Returns True if the address is a contract, False if it's a wallet (EOA).
    Caches results to avoid repeated RPC calls.
    """
    address = Web3.to_checksum_address(address)

    if address in address_type_cache:
        return address_type_cache[address] == "contract"

    try:
        code = w3.eth.get_code(address)
        is_contract = code != b''
        address_type_cache[address] = "contract" if is_contract else "wallet"
        return is_contract
    except Exception as e:
        print(f"Error checking address type: {e}")
        return False  # default to wallet if error

def format_number_with_spaces(number):
    if number is None:
        return "N/A"
    try:
        return "{:,.0f}".format(float(number)).replace(",", " ")
    except (ValueError, TypeError):
        return str(number)

def escape_markdown(text: str) -> str:
    """Escapes special characters for Markdown to prevent formatting issues."""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def get_user_data(update: Update):
    """Extract user ID and username from an update."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    return user_id, username

def get_change_arrow(old_value, new_value, precision=2):
    old = round(float(old_value), precision)
    new = round(float(new_value), precision)
    
    if new > old:
        return "🔼"
    elif new < old:
        return "🔽"
    else:
        return ""

def extract_token_from_message(text):
    if not text:
        #print("❌ No message text provided!")
        return None

    match = re.search(r'0x[a-fA-F0-9]{40}', text)  # ✅ Regex to find Ethereum addresses
    
    if match:
        return match.group(0)
    else:
        #print("❌ No valid token address found in message!")
        return None

async def send_batch_requests_ankr(session, batch_requests, chunk_size=50, retries=5, delay=2):
    results = []
    for i in range(0, len(batch_requests), chunk_size):
        chunk = batch_requests[i:i + chunk_size]
        attempt = 0
        while attempt < retries:
            try:
                async with session.post(ANKR_URL, json=chunk, timeout=20) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # ✅ Validation: only accept dicts with 'id'
                        valid = [r for r in data if isinstance(r, dict) and "id" in r]
                        if len(valid) != len(chunk):
                            print(f"⚠️ {len(chunk) - len(valid)} invalid responses, retrying...")
                            raise ValueError("Some responses were invalid.")

                        results.extend(valid)
                        break  # success

                    elif response.status == 429:
                        print("⏳ Rate limited by Ankr. Retrying...")
                        await asyncio.sleep(delay)
                        delay *= 2

                    else:
                        print(f"❌ Unexpected status code: {response.status}")
                        await asyncio.sleep(delay)
                        delay *= 2

                attempt += 1

            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                print(f"❌ Error during batch: {e}")
                await asyncio.sleep(delay)
                attempt += 1

    return results

def load_transaction_snapshots(token_address):
    session = SessionLocal()
    transactions = session.query(TransactionSnapshot).filter_by(token_address=token_address).all()
    session.close()
    return [tx.to_dict() for tx in transactions]  # convert ORM objects to plain dicts

def parse_tags(tags_raw):
    if isinstance(tags_raw, str):
        try:
            return json.loads(tags_raw)
        except json.JSONDecodeError:
            return []
    return tags_raw if isinstance(tags_raw, list) else []

def get_addresses_from_wallet_balances(wallet_token_list):
    """
    Takes output from get_wallet_token_balances() and returns a list of token addresses.
    All addresses are returned in lowercase.
    """
    return [
        token["address"].lower()
        for token in wallet_token_list
        if isinstance(token, dict) and "address" in token
    ]

def test_dexscreener_pair(pair_address):
    url = f"https://api.dexscreener.com/latest/dex/pairs/ethereum/{pair_address}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        pair_info = data.get("pair")

        if pair_info:
            volumen24h = pair_info.get("volume", {}).get("h24", 0)
            price = pair_info.get("priceUsd", "0")
            buys_24h = pair_info.get("txns", {}).get("h24", {}).get("buys", 0)
            sells_24h = pair_info.get("txns", {}).get("h24", {}).get("sells", 0)
        else:
            print(f"⚠️ Dexscreener returned no data for pair: {pair_address}")
            volumen24h, price, buys_24h, sells_24h = 0, "0", 0, 0

        return volumen24h, price, buys_24h, sells_24h

    else:
        print(f"❌ Dexscreener API error {response.status_code}: {response.text}")
        return 0, "0", 0, 0

async def fetch_market_prices():
    ids = ",".join(COINS)
    params = {
        "ids": ids,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true"
    }

    async with httpx.AsyncClient() as client:
        r = await client.get(COINGECKO_API, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    
def format_mc(mc):
   if not mc:
       return " N/A"
   elif mc >= 1_000_000_000:
       return f" ${mc / 1_000_000_000:.2f}B"
   elif mc >= 1_000_000:
       return f" ${mc / 1_000_000:.2f}M"
   elif mc >= 1_000:
       return f" ${mc / 1_000:.1f}K"
   else:
       return f" ${mc:.0f}"
   