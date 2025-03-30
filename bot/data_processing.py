from db import save_transaction_snapshot,save_static_token_data

WETH_ADDRESS = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"

def process_response_data(response_data, transactions, address):
    zero_block = None
    first_block = None
    second_block = None
    zero_block_set = False  # Ensure this is initialized
    trade_addresses = set()  # Ensure this is initialized
    method = None
    for i in range(0, len(response_data), 2):
        tx = response_data[i].get("result")
        receipt = response_data[i + 1].get("result")
        if tx and receipt:
            transaction_hash = tx.get('hash')
            input_data = tx.get('input', '')
            method_id =  method_id = input_data[:10] if input_data and input_data != "0x" else None
            TRANSACTION_TAGS = []
            
            # Construct transaction data
            transaction_data = {
                'transactionHash': tx.get('hash'),
                'blockNumber': int(tx['blockNumber'], 16) if tx.get('blockNumber') else None,
                'from': tx.get('from'),
                'to': tx.get('to'),
                'gas': int(tx['gas'], 16) if tx.get('gas') else None,
                'gasPrice': int(tx['gasPrice'], 16) if tx.get('gasPrice') else None,
                'input': tx.get('input'),
                'value': int(tx['value'], 16) if tx.get('value') else None,
                'nonce': tx.get('nonce'),
                'transactionIndex': tx.get('transactionIndex'),
                'status': int(receipt['status'], 16) if receipt.get('status') else None,
                'cumulativeGasUsed': int(receipt['cumulativeGasUsed'], 16) if receipt.get('cumulativeGasUsed') else None,
                'gasUsed': int(receipt['gasUsed'], 16) if receipt.get('gasUsed') else None,
                'contractAddress': receipt.get('contractAddress'),
                'valueInEther': int(tx['value'], 16) / 10**18 if tx.get('value') else None,
                'tags': [],
                "methodId": method_id
            }
            
            SYNC_TOPIC = "0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1"
            LIQ_TOPIC = "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9"
            TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            
            found_trade_or_liq = False
            
            # Detect trade / liq
            if is_add_liquidity(receipt.get("logs", [])):
                TRANSACTION_TAGS.append("liq")

            
            for log in receipt.get("logs", []):
                topics = log.get("topics", [])
                if not topics:
                    continue
                
                topic0 = topics[0].lower()
            
                if topic0 == LIQ_TOPIC:
                    TRANSACTION_TAGS.append("liq")
                    found_trade_or_liq = True
            
                if topic0 == SYNC_TOPIC:
                    if "liq" not in TRANSACTION_TAGS:
                        TRANSACTION_TAGS.append("trade")
                    found_trade_or_liq = True
            
                if topic0 == TRANSFER_TOPIC and len(topics) >= 3:
                    log_address = log.get("address", "").lower()
                
                    if log_address == address.lower():  # Only care about transfers of the target token
                        from_address = "0x" + topics[1][-40:].lower()
                        to_address = "0x" + topics[2][-40:].lower()
                
                        # Skip if from == 0x0 and it's LP mint (covered by liq tag already)
                        if from_address == "0x0000000000000000000000000000000000000000":
                            continue
                        if "transfer" not in TRANSACTION_TAGS:
                            TRANSACTION_TAGS.append("transfer")
                        
                
                        try:
                            transfer_raw = log.get("data")
                            if transfer_raw:
                                transfer_amount = int(transfer_raw, 16)
                                readable_amount = transfer_amount / 10**18  # optional: fetch actual decimals
                                transaction_data["transfer_amount"] = readable_amount
                        except Exception as e:
                            print(f"Failed to parse transfer amount: {e}")
                
                    try:
                        # topics[1] = from, topics[2] = to
                        transfer_raw = log.get("data")
                        if transfer_raw:
                            # This is hex string, like '0x000000000000...'
                            transfer_amount = int(transfer_raw, 16)
                            decimals = 18  # Default ERC-20, unless you fetched actual decimals
                            readable_amount = transfer_amount / 10**decimals
                            transaction_data["transfer_amount"] = readable_amount
                    except Exception as e:
                        print(f"Failed to parse transfer amount: {e}")
                    
            # Set zero_block and add appropriate tags
            if "trade" in TRANSACTION_TAGS and not zero_block_set:
                zero_block = transaction_data['blockNumber']
                first_block = zero_block + 1
                second_block = first_block + 1
                zero_block_set = True
                method=method_id
                TRANSACTION_TAGS.append("zero_block")

            # Add block-specific tags
            if transaction_data['blockNumber'] == zero_block:
                TRANSACTION_TAGS.append("zero_block")
                if method_id == method:
                    TRANSACTION_TAGS.append("📚bundle")
                else:
                    TRANSACTION_TAGS.append("🤖sniper")

            elif transaction_data['blockNumber'] == first_block:
                TRANSACTION_TAGS.extend(["first_block", "🤖sniper"])

            elif transaction_data['blockNumber'] == second_block:
                TRANSACTION_TAGS.extend(["second_block", "🤖sniper"])

            # Detect known bots
            known_bots = {
                "0x034131bcc29b9801af37a826925e58a4a6e0e866": "📚TitanDeployer",
                "0x3328f7f4a1d1c57c35df56bbf0c9dcafca309c49": "🤖Banana",
                "0x80a64c6d7f12c47b7c66c5b4e20e72bc1fcd5d9e": "🤖Maestro",
                "0x3a10dc1a145da500d5fba38b9ec49c8ff11a981f": "🤖Sigma"
            }
            to_address = transaction_data.get('to', '').lower()
            bot_name = known_bots.get(to_address)
            if bot_name:
                transaction_data['botUsed'] = bot_name
                TRANSACTION_TAGS.append(bot_name)
            from_address = transaction_data.get("from")

            # Update transaction_data tags
            transaction_data['tags'] = TRANSACTION_TAGS

            transactions.append(transaction_data)
            if "trade" in transaction_data["tags"] and from_address and from_address not in trade_addresses:
                trade_addresses.add(from_address)
            save_static_token_data({
                "token_address": address,
                "trade_addresses": list(trade_addresses)  # optional: convert set to list
            })
            transaction_data['token_address'] = address.lower()
            save_transaction_snapshot(address, transaction_data,trade_addresses)

def combine_transaction_data(details, receipt, token_value,balances,total_supply,eth_balances,token_address):

    if not isinstance(details, dict) or not isinstance(receipt, dict):
        return None
    # Skip non-trade transactions
    if 'trade' not in details.get('tags', []):
        return None
    from_address = details.get("from")
    token_balance = balances.get(from_address, 0.0)
    eth_balance=eth_balances.get(from_address,0.0)
    
    # Calculate percentages
    balance_percentage = (token_balance / total_supply) * 100 if total_supply else 0
    received_percentage = (token_value / total_supply) * 100 if total_supply else 0
    combined_data = {
        "transactionHash": details.get("transactionHash"),
        "token_address": token_address,
        "blockNumber": details.get("blockNumber"),
        "from": details.get("from"),
        "to": details.get("to"),
        "input": details.get("input"),
        "value": details.get("value"),
        "valueInEther": details.get("valueInEther"),
        "status": receipt.get("status"),
        "cumulativeGasUsed": receipt.get("cumulativeGasUsed"),
        "gasUsed": receipt.get("gasUsed"),
        "contractAddress": receipt.get("contractAddress"),
        "tags": details.get("tags", []),
        "tokenValue": token_value, # Add token value directly
        "tokenBalance": balances.get(from_address, 0.0),
        "balancePercentage": balance_percentage,     # Token balance as a percentage of total supply
        "receivedPercentage": received_percentage,    # Tokens received as a percentage of total supply
        "ethBalance": eth_balance
         }

    save_transaction_snapshot(
        token_address=token_address,
        tx_data=combined_data,
        update_dynamic_only=True
    )

        
    return combined_data

def is_trade_transaction(receipt: dict, token_address: str) -> bool:
    if not receipt or 'logs' not in receipt:
        return False

    for log in receipt['logs']:
        log_address = log.get('address', '').lower()

        # Check if WETH or token involved in any log
        if log_address in (WETH_ADDRESS.lower(), token_address.lower()):
            topics = log.get('topics', [])

            # Typical UniswapV2 Pair topics (e.g., Transfer, Sync, Swap)
            if topics and len(topics) > 0:
                # SWAP signature (or others, depending on your granularity)
                if topics[0].startswith("0xd78ad95fa46c994b"):  # Swap event signature
                    return True

                # fallback: if there's a Transfer event and WETH/token involved
                if topics[0].startswith("0xddf252ad"):  # Transfer
                    return True

    return False

def is_add_liquidity(logs):
    TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    SYNC_TOPIC = "0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1"
    ZERO_TOPIC = "0x" + "00" * 32

    sync_addresses = set()
    liq_detected = False

    for log in logs:
        topics = log.get("topics", [])
        if not topics or not isinstance(topics, list):
            continue

        topic0 = topics[0].lower()
        log_address = log.get("address", "").lower()

        # Store any addresses that emitted a Sync event
        if topic0 == SYNC_TOPIC:
            sync_addresses.add(log_address)

    for log in logs:
        topics = log.get("topics", [])
        if not topics or len(topics) < 2:
            continue

        topic0 = topics[0].lower()
        from_topic = topics[1].lower()
        log_address = log.get("address", "").lower()

        # Check for LP token mint (Transfer from 0x0)
        if topic0 == TRANSFER_TOPIC and from_topic == ZERO_TOPIC:
            if log_address in sync_addresses:
                return True  # Liquidity was added

    return False
