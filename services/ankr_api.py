import aiohttp
from bot.utils import send_batch_requests_ankr
from bot.config import ANKR_URL
from bot.data_processing import process_response_data
import requests
import time

def fetch_prices_from_ankr(token_addresses, chain="eth"):
    ankr_prices = {}

    for address in token_addresses:
        url = ANKR_URL
        payload = {
            "jsonrpc": "2.0",
            "method": "ankr_getTokenPrice",
            "params": {
                "blockchain": chain,
                "contractAddress": address
            },
            "id": 1
        }

        try:
            response = requests.post(url, json=payload)
            data = response.json()

            price_str = data.get("result", {}).get("usdPrice")
            if price_str:
                ankr_prices[address.lower()] = float(price_str)

        except Exception as e:
            print(f"⚠️ Ankr error for {address}: {e}")

        # Avoid rate limiting
        time.sleep(0.2)

    return ankr_prices


async def batch_get_eth_balances_ankr(addresses, token_decimal=18):
    balances = {}

    batch_requests = [
        {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [address, "latest"],
            "id": idx
        }
        for idx, address in enumerate(addresses)
    ]

    async with aiohttp.ClientSession() as session:
        results = await send_batch_requests_ankr(session, batch_requests, chunk_size=50, retries=5, delay=2,)
        
        for r in results:
            idx = r.get("id")
            hex_value = r.get("result", "0x0")
            balance = int(hex_value, 16) / 10 ** token_decimal
            balances[addresses[idx]] = balance

    return balances

async def batch_get_token_balances_ankr(token_address, addresses, token_decimal):
    balances = {}

    # Lowercase token address to standardize
    token_address = token_address.lower()

    # Prepare batch request payloads
    batch_requests = [
        {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {
                    "to": token_address,
                    "data": f"0x70a08231{address[2:].zfill(64)}"  # balanceOf(address)
                },
                "latest"
            ],
            "id": idx
        }
        for idx, address in enumerate(addresses)
    ]

    async with aiohttp.ClientSession() as session:
        results = await send_batch_requests_ankr(session, batch_requests, chunk_size=50, retries=5, delay=2)

        for r in results:
            idx = r.get("id")
            hex_value = r.get("result", "0x0")
            balance = int(hex_value, 16) / 10 ** token_decimal
            balances[addresses[idx]] = balance

    return balances

async def get_transaction_details_and_receipt_ankr(tx_hashes, address, chunk_size=50):
    payload = []

    for tx_hash in tx_hashes:
        payload.append({
            "jsonrpc": "2.0",
            "method": "eth_getTransactionByHash",
            "params": [tx_hash],
            "id": len(payload)
        })
        payload.append({
            "jsonrpc": "2.0",
            "method": "eth_getTransactionReceipt",
            "params": [tx_hash],
            "id": len(payload)
        })

    async with aiohttp.ClientSession() as session:
        response_data = await send_batch_requests_ankr(session, payload, chunk_size=chunk_size)
        

    transactions = []
    if response_data:
        process_response_data(response_data, transactions, address)
    return transactions

async def batch_get_method_ids(tx_hashes, chunk_size=50):
    method_ids = {}

    batch_requests = [
        {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionByHash",
            "params": [tx_hash],
            "id": idx
        }
        for idx, tx_hash in enumerate(tx_hashes)
    ]

    async with aiohttp.ClientSession() as session:
        responses = await send_batch_requests_ankr(session, batch_requests, chunk_size=chunk_size)

        for result in responses:
            tx = result.get("result")
            if tx:
                tx_hash = tx.get("hash")
                input_data = tx.get("input")
                if tx_hash:
                    method_ids[tx_hash] = input_data[:10] if input_data and input_data != "0x" else None
    return method_ids

