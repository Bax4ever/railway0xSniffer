import requests
from web3 import Web3
from bot.config import MORALIS_API_KEY
import time

MORALIS_BASE_URL = "https://deep-index.moralis.io/api/v2.2"
cached_moralis_data = {}
cache_expiry_time = 300  # 5 minutes

def get_erc20_token_price_stats(token_address, chain="eth"):
    global cached_moralis_data
    current_time = time.time()

    # Check if cached value exists and is valid
    if token_address in cached_moralis_data and current_time - cached_moralis_data[token_address]["timestamp"] < cache_expiry_time:
        return cached_moralis_data[token_address]["data"]

    # Otherwise, make API request
    checksum_address = Web3.to_checksum_address(token_address)
    url = f"https://deep-index.moralis.io/api/v2.2/erc20/{checksum_address}/price?chain={chain}"
    headers = {"Accept": "application/json", "X-API-Key": MORALIS_API_KEY}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        cached_moralis_data[token_address] = {"data": data, "timestamp": current_time}
        return data

    return {"error": "Failed to fetch token price"}

def get_token_pairs_info(token_address, chain="eth"):
    """
    Retrieves liquidity, volume, price, and pair address information for an ERC20 token using the Moralis API.

    Args:
    - token_address (str): The token address for which you want to get liquidity pair information.
    - chain (str): The blockchain chain, default is Ethereum ("eth").

    Returns:
    - A list of dictionaries containing the token pair address, price in USD, liquidity in USD, and 24-hour volume.
    """

    # Convert token address to checksum format using Web3
    checksum_address = Web3.to_checksum_address(token_address)

    # Moralis API endpoint to get token pair information
    url = f"https://deep-index.moralis.io/api/v2.2/erc20/{checksum_address}/pairs?chain={chain}"

    # Set headers with API key
    headers = {
        "Accept": "application/json",
        "X-API-Key": MORALIS_API_KEY
    }

    # Make the request
    response = requests.get(url, headers=headers)

    # Check if request was successful
    if response.status_code != 200:
        #(f"Error: {response.status_code}, Message: {response.text}")
        return {"error": f"Error: {response.status_code}, Message: {response.text}"}

    # Parse JSON response
    response_json = response.json()

    # Ensure we have 'pairs' in the response
    if 'pairs' not in response_json or not isinstance(response_json['pairs'], list):
        #print("No valid 'pairs' key found in the response.")
        return []

    pairs_info = response_json['pairs']

    # Extract relevant information
    extracted_data = []
    for idx, pair in enumerate(pairs_info):

        # Extract required fields from each pair
        if isinstance(pair, dict):
            pair_data = {
                "pair_address": pair.get("pair_address", "N/A"),
                "price_usd": pair.get("usd_price", "N/A"),
                "liquidity_usd": pair.get("liquidity_usd", "N/A"),
                "volume_24h_usd": pair.get("volume_24h_usd", "N/A"),
                "token0_symbol": pair.get('pair', [])[0].get('token_symbol', 'N/A') if 'pair' in pair and len(pair.get('pair', [])) > 0 else 'N/A',
                "token1_symbol": pair.get('pair', [])[1].get('token_symbol', 'N/A') if 'pair' in pair and len(pair.get('pair', [])) > 1 else 'N/A'
            }
            extracted_data.append(pair_data)
          
        pair_address=pair_data.get("pair_address", "N/A")
        price_usd=pair_data.get("price_usd", "N/A")
        liquidity_usd=pair_data.get("liquidity_usd", "N/A")
        volume_24h_usd= pair_data.get("volume_24h_usd", "N/A")
        token0_symbol= pair.get('pair', [])[0].get('token_symbol', 'N/A') if 'pair' in pair and len(pair.get('pair', [])) > 0 else 'N/A'
        token1_symbol= pair.get('pair', [])[1].get('token_symbol', 'N/A') if 'pair' in pair and len(pair.get('pair', [])) > 1 else 'N/A'

    return pair_address,price_usd,liquidity_usd,volume_24h_usd,token0_symbol,token1_symbol

def get_erc20_token_total_transactions(token_address, chain="eth"):
    """
    Retrieves the total transaction count for an ERC20 token using the Moralis API.

    Args:
    - token_address (str): The token address for which you want to get the total transaction count.
    - chain (str): The blockchain chain, default is Ethereum ("eth").

    Returns:
    - An integer representing the total transaction count or an error message if unsuccessful.
    """

    # Convert token address to checksum format using Web3
    try:
        checksum_address = Web3.to_checksum_address(token_address)
    except ValueError as e:
        return {"error": f"Invalid token address: {e}"}

    # Moralis API endpoint to get token stats
    url = f"https://deep-index.moralis.io/api/v2.2/erc20/{checksum_address}/stats"

    # Set headers with API key
    headers = {
        "Accept": "application/json",
        "X-API-Key": MORALIS_API_KEY
    }

    # Make the request
    response = requests.get(url, headers=headers)

    # Check if request was successful
    if response.status_code != 200:
        return {"error": f"Error: {response.status_code}, Message: {response.text}"}
    # Parse JSON response
    response_json = response.json()
    # Extract the total transaction count from the response
    total_transactions = response_json.get("transfers", {}).get("total")
    if total_transactions is None:
        return {"error": "Total transactions count not found in the response."}
    # Convert total to an integer
    try:
        total_transactions = int(total_transactions)
    except ValueError:
        return {"error": "Failed to convert transaction count to an integer."}
    # Return only the total transaction count
    return total_transactions

def get_erc20_token_transfers(token_address, from_block="0", chain="eth", limit=100):
    """
    Fetches ERC20 token transfers for a given token contract address starting from a specific block.

    Args:
    - token_address (str): The ERC20 token contract address.
    - from_block (str): The block number to start fetching transfers from (default is None).
    - chain (str): Blockchain network (default is 'eth' for Ethereum).
    - limit (int): The number of transfer events to fetch (default is 100).

    Returns:
    - list: A list of dictionaries representing token transfers.
    """
    try:
        # Convert to checksum address for consistency
        checksum_address = Web3.to_checksum_address(token_address)

        # Define API URL for getting ERC20 token transfers
        url = f"https://deep-index.moralis.io/api/v2/erc20/{checksum_address}/transfers?chain={chain}&limit={limit}&from_block=0"

        # Add 'from_block' if provided

        # Set the request headers with the Moralis API key
        headers = {
            "Accept": "application/json",
            "X-API-Key": MORALIS_API_KEY
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Raise an error if the response was unsuccessful
        response.raise_for_status()

        # Get the list of transfers
        transfers = response.json().get("result", [])

        # Sort transfers by block number in descending order (most recent first)
        sorted_transfers = sorted(transfers, key=lambda x: int(x.get("block_number", 0)), reverse=True)

        return sorted_transfers

    except requests.RequestException as e:
        return {"error": str(e)}

def get_wallet_token_balances(wallet_address, chain="eth"):
    """
    Fetches all ERC20 token balances for a wallet address from Moralis API.
    """
    headers = {
        "accept": "application/json",
        "X-API-Key": MORALIS_API_KEY
    }

    url = f"{MORALIS_BASE_URL}/{wallet_address}/erc20?chain={chain}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        tokens = response.json()
        results = []
        addresses= []
        for token in tokens:
            results.append({
                "symbol": token.get("symbol"),
                "name": token.get("name"),
                "balance_raw": token.get("balance"),
                "decimals": int(token.get("decimals", 18)),
                "address": token.get("token_address"),
            })
            addresses.append(token.get("token_address"))
        return results,addresses
    else:
        print(f"❌ Moralis API error: {response.status_code} - {response.text}")
        return []
    
def get_multiple_token_prices_moralis(token_addresses, chain="eth"):
    url = "https://deep-index.moralis.io/api/v2.2/erc20/prices"
    headers = {
        "accept": "application/json",
        "X-API-Key": MORALIS_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "tokens": [{"token_address": addr.lower()} for addr in token_addresses],
        "chain": chain,
        "include": "percent_change"  # this must be a string
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        print(f"❌ Price fetch failed: {response.status_code}")
        return {}

    return response.json()

def get_multiple_token_prices_moralis_scoreboard(token_addresses, chain="eth"):
    url = "https://deep-index.moralis.io/api/v2.2/erc20/prices"
    headers = {
        "accept": "application/json",
        "X-API-Key": MORALIS_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "tokens": [{"token_address": addr.lower()} for addr in token_addresses],
        "chain": chain,
        "include": "percent_change"
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"❌ Price fetch failed: {response.status_code}")
        return []

    data = response.json()
    results = []
    for token in data:
        token_address = token.get("tokenAddress", "").lower()
        usd_price = token.get("usdPrice")
        liquidity_usd = float(token.get("pairTotalLiquidityUsd", 0))  # ✅ Fix here

        results.append({
            "token_address": token_address,
            "price": usd_price,
            "liquidity": liquidity_usd,
            "scam": liquidity_usd < 700,
            "low_liq": 700 <= liquidity_usd < 3000
        })

    print(results)
    return results

