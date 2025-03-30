from services.moralis_api import get_token_pairs_info, get_erc20_token_total_transactions
from services.etherscan_api import get_latest_eth_price
from bot.data_processing import combine_transaction_data
from services.etherscan_api import get_wallet_balance, get_token_total_supply, get_all_token_transactions, get_contract_source_code
from services.graphql_api import get_liquidity_pair_address, get_liquidity_pair_details
from contracts.contract_analitic import extract_social_links, extract_max_wallet_limit, extract_tax_and_swap_parameters
from db import save_static_token_data, save_token_dynamics
import json
from db import SessionLocal,Token,TokenDynamic,TransactionSnapshot
from .ankr_api import batch_get_eth_balances_ankr,batch_get_token_balances_ankr,get_transaction_details_and_receipt_ankr
from sqlalchemy import func
from bot.utils import load_transaction_snapshots,test_dexscreener_pair

async def main_async(token_address):
     
    session = SessionLocal()
    static_exists = session.query(Token).filter_by(token_address=token_address).first()
    dynamic_data = session.query(TokenDynamic).filter_by(token_address=token_address).first()
    tx_snaps=session.query(TransactionSnapshot.tx_hash).filter_by(token_address=token_address).all()
   
    
    if tx_snaps:
        tx_hashes = [row.tx_hash for row in tx_snaps]
        token_value_rows = session.query(
        TransactionSnapshot.tx_hash,
        TransactionSnapshot.token_value
        ).filter_by(token_address=token_address).all()
        # = [{"transactionHash": row.tx_hash, "tokenValue": row.token_value} for row in token_value_rows]
        tx_hashes = [row.tx_hash for row in token_value_rows]
        token_values = [row.token_value if row.token_value is not None else 0.0 for row in token_value_rows]
    else:
        tx_hashes, token_values = get_all_token_transactions(token_address)

    session.close()

    if static_exists:
        token_symbol=static_exists.token_symbol
        token_name=static_exists.token_name
        token_decimal = static_exists.token_decimal
        total_supply = static_exists.total_supply   
        b_count = static_exists.b_count or 0
        s_count = static_exists.s_count or 0
        total_recivedB = static_exists.total_recivedB or 0
        total_recivedS = static_exists.total_recivedS or 0
    else:
        token_symbol=""
        token_name=""
        token_decimal=0
        
        if token_values:
            token_symbol = token_values[0]['tokenSymbol']
            token_name = token_values[0]['tokenName']
            token_decimal = token_values[0]['tokenDecimal']
        total_supply = get_token_total_supply(token_address,token_decimal)
        contract_code=get_contract_source_code(token_address)
        links=extract_social_links(contract_code)
        tax=extract_tax_and_swap_parameters(contract_code)
        maxW=extract_max_wallet_limit(contract_code, total_supply)
        save_static_token_data({
            "token_address": token_address,
            "token_name": token_name,
            "token_symbol": token_symbol,
            "token_decimal": token_decimal,
            "total_supply": total_supply,
            "links": json.dumps(links),
            "tax": tax})

    if dynamic_data:
        token_address=token_address.lower()
        transaction_details = load_transaction_snapshots(token_address)  # from your own function
        if not transaction_details:  # fallback safety
            token_address=token_address
            transaction_details = await get_transaction_details_and_receipt_ankr(tx_hashes, token_address)
    else:
        transaction_details= await get_transaction_details_and_receipt_ankr(tx_hashes, token_address)

    eth_price_usd = get_latest_eth_price()    
    trade_addresses = set()  # Each user gets their own trade_addresses set
    derived_eth, pair_id = get_liquidity_pair_address(token_address)
    
    pair_address,price_usd,liquidity_usd,volume_24h_usd,token0_symbol,token1_symbol =get_token_pairs_info(token_address)
    volumen24h,price,buys_24h,sells_24h=test_dexscreener_pair(pair_address)

    eth_price_usd = get_latest_eth_price()

    clog = get_wallet_balance(token_address, token_address) / 10 ** token_decimal
  
    clog_percent = (clog / total_supply) * 100
   
    market_cap_usd=0
    if eth_price_usd:
        if derived_eth:
            market_cap_usd = derived_eth * total_supply * eth_price_usd
        else:
            market_cap_usd = float(price_usd) * total_supply
        
    reserveUSD=0
    tx_count=0
    totalVolumen=0
    # Fetch liquidity pair details if pair_id exists
    if pair_id:
        pair_details = get_liquidity_pair_details(pair_id)
        if pair_details:
            # Extract values with defaults in case keys are missing
            reserveUSD = float(pair_details.get("reserveUSD", 0.0))
            tx_count = int(pair_details.get("txCount", 0))
            volumeToken1 = float(pair_details.get("volumeToken1", 0.0))
            totalVolumen1 = volumeToken1 * eth_price_usd if eth_price_usd else 0.0
    else:
        totalVolumen1=volume_24h_usd
        pair_details=pair_address
        reserveUSD=liquidity_usd
        tx_count=get_erc20_token_total_transactions(token_address)

    static_data = session.query(Token).filter(func.lower(Token.token_address) == token_address.lower()).first()
    trade_addresses=static_data.trade_addresses
 
    eth_balances=await batch_get_eth_balances_ankr(trade_addresses)
    balances=await batch_get_token_balances_ankr(token_address,trade_addresses,token_decimal)

    curent_bundle_balance_token = 0.0
    curent_sniper_balance_token_percent = 0.0
    total_recivedB=0.0
    total_recivedS=0.0
    combined_transactions = []
    
    total_ethb=0.0
    total_eths=0.0
    b_count=0
    s_count=0
    

    for i, transaction in enumerate(transaction_details):
        
        raw_value = token_values[i] if i < len(token_values) else 0.0

        if isinstance(raw_value, dict):
            token_value = raw_value.get("tokenValue", 0.0)
        else:
            token_value = raw_value

        combined_data = combine_transaction_data(transaction, transaction, token_value, balances, total_supply,eth_balances,token_address)

        if combined_data:
            combined_transactions.append(combined_data)
            if "zero_block" in combined_data["tags"] and "📚bundle" in combined_data["tags"]:
                curent_bundle_balance_token += combined_data["tokenBalance"]
                total_recivedB += token_value
                total_ethb+= combined_data["ethBalance"]
                b_count+=1
            elif "first_block" in combined_data["tags"] or ("zero_block" in combined_data["tags"] or "second_block" in combined_data["tags"]  and "🤖sniper" in combined_data["tags"]):
                curent_sniper_balance_token_percent += combined_data["tokenBalance"]
                total_recivedS += token_value
                total_eths+= combined_data["ethBalance"]
                s_count+=1
            
    total_sniper_worth=curent_sniper_balance_token_percent*derived_eth
    total_bundle_worth=curent_bundle_balance_token*derived_eth
    totalB_recivied=(total_recivedB/total_supply)*100
    totalS_recivied=(total_recivedS/total_supply)*100

    save_static_token_data({
        "recivedB_percent":  totalB_recivied,
        "recivedS_percent":  totalS_recivied,
        "token_address": token_address,
        "total_recivedB": total_recivedB,
        "total_recivedS": total_recivedS,
        "b_count": b_count,
        "s_count": s_count,
        "pairA": pair_address,
    })
    rounded_market_cap = round(market_cap_usd, 0)  # No decimals
    rounded_bundle_balance = round(curent_bundle_balance_token, 2)  # Optional
    rounded_sniper_balance = round(curent_sniper_balance_token_percent, 2)
    rounded_reserveUSD = round(reserveUSD, 0)

    save_token_dynamics(
    **{
        "token_address": token_address,
        "market_cap_usd": rounded_market_cap,
        "reserveUSD": rounded_reserveUSD,
        "tx_count": tx_count,
        "totalVolumen": volumen24h,
        "totalVolumen1": totalVolumen1 if totalVolumen1 != "N/A" else 0,
        "clog": clog,
        "clog_percent": clog_percent,
        "curent_bundle_balance_token": rounded_bundle_balance,
        "curent_sniper_balance_token_percent": rounded_sniper_balance,
        "total_ethb": total_ethb,
        "total_eths": total_eths,
        "total_sniper_worth": total_sniper_worth,
        "total_bundle_worth": total_bundle_worth,
        "buys_24h": buys_24h,
        "sells_24h":sells_24h
    }
)

    return curent_bundle_balance_token,curent_sniper_balance_token_percent,market_cap_usd,total_sniper_worth,total_bundle_worth




