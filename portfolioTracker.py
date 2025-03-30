from services.moralis_api import get_multiple_token_prices_moralis,get_wallet_token_balances
from services.etherscan_api import get_wallet_eth_balance
import requests
import time

eth_address="0xc1e0e721E80cBa88002424D842b14bb010357A98" 

async def portfolio_Tracker_function(wallet_address):
    if isinstance(wallet_address, list):
        wallet_address = wallet_address[0]

    moralis_balances,tokens=get_wallet_token_balances(wallet_address)#######

    moralis_price_data=get_multiple_token_prices_moralis(tokens)#######
    merge_data=merge_balances_and_prices(moralis_balances,moralis_price_data)

    filtered_tokens = [
        token for token in merge_data
        if token.get("liquidity_usd", 0) > 0
        and token.get("balance", 0) >= 0.0001
        and token.get("usd_value", 0) > 0
        #and token.get("security_score") is not None
    ]

    # Sort by USD value descending
    filtered_tokens.sort(key=lambda x: x.get("usd_value", 0), reverse=True)

    eth_balance=get_wallet_eth_balance(wallet_address)
    
    return filtered_tokens,eth_balance
        
def summarize_token_holdings(wallet_balances, price_data):
    summarized = []
    total_usd=0
    total_eth=0
    for token in wallet_balances:
        address = token.get("address").lower()
        raw_balance = int(token.get("balance_raw", 0))
        decimals = token.get("decimals", 18)

        price = price_data.get(address)
        if not price:
            continue

        human_balance = raw_balance / (10 ** decimals)
        total_value_usd = human_balance * float(price["usdPrice"])
        total_value_eth = human_balance * (int(price["nativePrice"]["value"]) / (10 ** 18))
        total_usd += total_value_usd
        total_eth += total_value_eth

        summarized.append({
            "symbol": token.get("symbol"),
            "name": token.get("name"),
            "address": address,
            "balance": human_balance,
            "price_usd": float(price["usdPrice"]),
            "value_usd": total_value_usd,
            "value_eth": total_value_eth,
            "change_24h": price.get("usdPrice24hrPercentChange"),
            "exchange": price.get("exchangeName"),
            "verified": price.get("verifiedContract", False),
            "spam": price.get("possibleSpam", False),
            "security_score": price.get("securityScore")
        })

    return summarized,total_usd,total_eth

def merge_balances_and_prices(balances, prices):
    price_lookup = {
        p.get("tokenAddress", "").lower(): p for p in prices if p.get("tokenAddress")
    }

    merged = []
    for token in balances:
        addr = token.get("token_address") or token.get("address")
        if not addr:
            continue
        addr = addr.lower()

        price_info = price_lookup.get(addr)
        balance = token.get("balance")

        # Fallback: calculate balance from raw if needed
        if balance is None and "balance_raw" in token and "decimals" in token:
            try:
                balance = int(token["balance_raw"]) / (10 ** int(token["decimals"]))
                token["balance"] = balance
            except:
                balance = 0
                token["balance"] = 0

        # Default USD value
        usd_price = 0
        usd_value = 0

        if price_info:
            try:
                usd_price = float(price_info.get("usdPrice", 0))
                usd_value = balance * usd_price if balance else 0
            except:
                pass

            token.update({
                "price_usd": usd_price,
                "usd_value": usd_value,
                "symbol": price_info.get("tokenSymbol") or token.get("symbol"),
                "name": price_info.get("tokenName") or token.get("name"),
                "logo": price_info.get("tokenLogo"),
                "liquidity_usd": float(price_info.get("pairTotalLiquidityUsd", 0) or 0),
                "security_score": price_info.get("securityScore"),
                "pair_address": price_info.get("pairAddress"),
                "pair_url": f"https://dexscreener.com/ethereum/{price_info.get('pairAddress')}" if price_info.get("pairAddress") else None,
                "price_change_24h": price_info.get("usdPrice24hrPercentChange"),
                "listed_at": price_info.get("blockTimestamp")
            })

        merged.append(token)

    return merged

def fetch_dexscreener_data_for_tokens(token_addresses):
    collected_data = []

    for token_address in token_addresses:
        try:
            # Step 1: Search token to get relevant pair
            search_url = f"https://api.dexscreener.com/latest/dex/search/?q={token_address}"
            search_response = requests.get(search_url)
            if search_response.status_code != 200:
                print(f"❌ Failed search for {token_address}")
                continue

            search_results = search_response.json().get("pairs", [])
            
            if not search_results:
                print(f"❌ No pairs found for {token_address}")
                continue

            # Use the first pair found
            pair_address = search_results[0]["pairAddress"]

            # Step 2: Fetch full pair data
            pair_url = f"https://api.dexscreener.com/latest/dex/pairs/ethereum/{pair_address}"
            pair_response = requests.get(pair_url)
            if pair_response.status_code != 200:
                print(f"❌ Failed to fetch pair data for {pair_address}")
                continue

            pair_data = pair_response.json().get("pair", {})

            token_info = {
                "token": token_address,
                "symbol": pair_data.get("baseToken", {}).get("symbol"),
                "price_usd": pair_data.get("priceUsd"),
                "liquidity_usd": pair_data.get("liquidity", {}).get("usd"),
                "volume_24h": pair_data.get("volume", {}).get("h24"),
                "buys_24h": int(pair_data.get("txns", {}).get("h24", {}).get("buys", 0)),
                "sells_24h": int(pair_data.get("txns", {}).get("h24", {}).get("sells", 0)),
                "pair_url": pair_data.get("url"),
            }
            

            collected_data.append(token_info)

            # Optional: small delay to avoid rate limits
            time.sleep(0.3)

        except Exception as e:
            print(f"⚠️ Error processing {token_address}: {e}")
            continue

    return collected_data
