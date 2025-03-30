import requests
from bot.config import ETHERSCAN_API_KEY



def get_all_token_transactions(token_address):
    url = f"https://api.etherscan.io/api?module=account&action=tokentx&contractaddress={token_address}&page=1&offset=250&sort=asc&apikey={ETHERSCAN_API_KEY}"
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()
        if data['status'] == '1':
            filtered_transactions = [
                tx['hash'] for tx in data["result"]
                if tx["to"].lower() != token_address.lower() and tx["from"].lower() != "0x0000000000000000000000000000000000000000"
            ]
            token_values = [
                {
                    "hash": tx['hash'],
                    "tokenValue": int(tx['value']) / 10**int(tx['tokenDecimal']),
                    "tokenDecimal": int(tx['tokenDecimal']),
                    "tokenSymbol": tx.get('tokenSymbol'),
                    "tokenName": tx.get('tokenName'),
                    "to": tx.get("to"),
                    "from": tx.get("from")
                }
                for tx in data["result"] 
                if tx["to"].lower() != token_address.lower() and tx["from"].lower() != "0x0000000000000000000000000000000000000000"
            ]
            return filtered_transactions, token_values
        else:
            #print("No transactions found or API returned an error.")
            return [], []
    except requests.exceptions.RequestException as e:
        #print(f"An error occurred: {e}")
        return [], []

def get_wallet_balance(wallet_address, contract_address):
    url = f"https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={wallet_address}&tag=latest&apikey={ETHERSCAN_API_KEY}"
    response = requests.get(url)
    data = response.json()
    if data['status'] == '1':
        return int(data['result']) 
    else:
        #print(f"Error fetching balance for wallet: {wallet_address}")
        return 0  
    
def get_latest_eth_price():
    try:
        url = f"https://api.etherscan.io/api?module=stats&action=ethprice&apikey={ETHERSCAN_API_KEY}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == '1':
            return float(data['result']['ethusd'])
        else:
            #print(f"Error: Could not retrieve ETH price. Status: {data.get('status')}, Message: {data.get('message', 'No message available')}")
            return 0
    except requests.exceptions.RequestException as e:
        #print(f"An error occurred: {e}")
        return 0
    
def get_token_total_supply(token_address,token_decimal):
    supply_url = f"https://api.etherscan.io/api?module=stats&action=tokensupply&contractaddress={token_address}&apikey={ETHERSCAN_API_KEY}"
    response = requests.get(supply_url)
    supply_data = response.json()
    if 'status' in supply_data and supply_data['status'] == '1':
        supply=int(supply_data.get('result', 0))
        if supply:
            supply=supply / 10 ** token_decimal
        return (supply)  # ✅ Use `.get()` to avoid crash

    else:
        #print(f"Error fetching total supply for {token_address}: {supply_data['message']}")
        return 0    

def get_contract_source_code(token_address):
    url = f"https://api.etherscan.io/api?module=contract&action=getsourcecode&address={token_address}&apikey={ETHERSCAN_API_KEY}"
    response = requests.get(url)
    data = response.json()
    if data['status'] == '1' and len(data['result']) > 0:
        return data['result'][0].get('SourceCode', '')
    else:
        #print(f"Error fetching source code: {data.get('message', 'Unknown error')}")
        return None

def get_wallet_eth_balance(wallet_address):
    url = f"https://api.etherscan.io/api?module=account&action=balance&address={wallet_address}&tag=latest&apikey={ETHERSCAN_API_KEY}"
    response = requests.get(url)
    data = response.json()
    
    if data['status'] == '1':
        return int(data['result']) / 1e18  # Convert Wei to ETH
    else:
        # print(f"Error fetching ETH balance for wallet: {wallet_address}")
        return 0
