from sqlalchemy import create_engine, Column, String, Integer, Numeric, DateTime, Text,Float, BigInteger
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime,timedelta
from sqlalchemy import JSON
from sqlalchemy import func
import time
from dotenv import load_dotenv
import os

load_dotenv()  # ⛔ overrides Railway environment if .env is missing
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()
Base = declarative_base()

# Token Table (stores total supply)
class Token(Base):
    __tablename__ = "token_static"

    id = Column(Integer, primary_key=True, index=True)
    token_address = Column(String, unique=True, index=True)
    token_name = Column(String)
    token_symbol = Column(String)
    token_decimal = Column(Integer)
    total_supply = Column(Integer)
    total_recivedB = Column(Numeric)
    total_recivedS = Column(Numeric)
    recivedB_percent = Column(Numeric)
    recivedS_percent = Column(Numeric)
    b_count = Column(Integer)
    s_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    links = Column(JSON, nullable=True)
    pairA = Column(String, nullable=True)
    tax = Column(JSON, nullable=True)  # ✅ Add this
    trade_addresses= Column(JSON, nullable=True)

class TokenDynamic(Base):
    __tablename__ = "token_dinamics"

    id = Column(Integer, primary_key=True, index=True)
    token_address = Column(String, index=True, unique=True)

    # Dynamic values
    market_cap_usd = Column(Numeric)
    reserveUSD = Column(Numeric)
    tx_count = Column(Integer)
    totalVolumen = Column(Numeric)
    totalVolumen1 = Column(Numeric)
    clog = Column(Numeric)
    clog_percent = Column(Numeric)
    curent_bundle_balance_token = Column(Numeric)
    curent_sniper_balance_token_percent = Column(Numeric)
    unsold = Column(Numeric)
    total_ethb = Column(Numeric)
    total_eths = Column(Numeric)
    bundle_arrow = Column(String, nullable=True)
    sniper_arrow = Column(String, nullable=True)
    market_cap_arrow = Column(String, nullable=True)
    total_bundle_worth=Column(Numeric)
    total_sniper_worth=Column(Numeric)
    buys_24h=Column(Numeric)
    sells_24h=Column(Numeric)

    updated_at = Column(DateTime, default=datetime.utcnow)

class TransactionSnapshot(Base):
    __tablename__ = 'transaction_snapshots'

    tx_hash = Column(String, primary_key=True)
    token_address = Column(String, index=True)
    from_address = Column(String)
    to_address = Column(String)
    input_data = Column(String)
    token_value = Column(Float)
    token_balance = Column(Float)
    balance_percent = Column(Float)
    received_percent = Column(Float)
    eth_balance = Column(Float)
    gas_price = Column(BigInteger)
    gas_used = Column(BigInteger)
    cumulative_gas_used = Column(BigInteger)
    tx_index = Column(Integer)
    method_id = Column(String)
    block_number = Column(Integer)
    value = Column(BigInteger)
    value_in_ether = Column(Float)
    tags = Column(JSON)
    transfer_amount = Column(Float)  

    def to_dict(self):
        return {
            "transactionHash": self.tx_hash,
            "token_address": self.token_address,
            "from": self.from_address,
            "to": self.to_address,
            "input": self.input_data,
            "tokenValue": self.token_value,
            "tokenBalance": self.token_balance,
            "balancePercentage": self.balance_percent,
            "receivedPercentage": self.received_percent,
            "ethBalance": self.eth_balance,
            "gasPrice": self.gas_price,
            "gasUsed": self.gas_used,
            "cumulativeGasUsed": self.cumulative_gas_used,
            "transactionIndex": self.tx_index,
            "methodId": self.method_id,
            "blockNumber": self.block_number,
            "value": self.value,
            "valueInEther": self.value_in_ether,
            "tags": self.tags,
        }

class UserInteraction(Base):
    __tablename__ = "user_interactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer,index=True)
    username = Column(String)
    message_id = Column(Integer, index=True)
    token_address = Column(String, index=True)
    refresh_count = Column(Integer, default=1)
    requested_at = Column(DateTime, default=datetime.utcnow)

class SavedWallets(Base):
    __tablename__ = "saved_wallets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username= Column(Text, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=False)
    slot = Column(Integer, nullable=False)
    address = Column(Text, nullable=False)
    nickname = Column(String, nullable=True)

class TokenCall(Base):
    __tablename__ = "token_calls"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer,index=True)
    username = Column(String)
    first_name = Column(String)
    name = Column(String)
    token_address = Column(String, index=True)
    symbol = Column(String)
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)


# Create the table
def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()


def get_total_supply(token_address):
    session = SessionLocal()
    token = session.query(Token).filter_by(token_address=token_address).first()
    session.close()
    return token.total_supply if token else None

def save_static_token_data(data: dict):
    session = SessionLocal()
    try:
        token_address = data.get("token_address")
        existing = session.query(Token).filter_by(token_address=token_address).first()

        if existing:
            for key, value in data.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
        else:
            new_entry = Token(**data)
            session.add(new_entry)

        session.commit()
    except Exception as e:
        print("❌ Error saving static token data:", e)
    finally:
        session.close()

def get_static_token_data(token_address):
    session = SessionLocal()
    try:
        token = session.query(Token).filter_by(token_address=token_address).first()
        if token:
            return {
                "token_name": token.token_name,
                "token_symbol": token.token_symbol,
                "token_decimal": token.token_decimal,
                "total_supply": token.total_supply,
                "total_recivedB": token.total_recivedB,
                "total_recivedS": token.total_recivedS,
                "recivedB_percent": token.recivedB_percent,
                "recivedS_percent": token.recivedS_percent,
                "b_count": token.b_count,
                "s_count": token.s_count,
                "links": token.links,
                "pairA": token.pairA
            }
        else:
            return None
    finally:
        session.close()

def token_static_exists(token_address):
    session = SessionLocal()
    exists = session.query(Token).filter_by(token_address=token_address).first() is not None
    session.close()
    return exists

def get_dynamic_token_data(token_address):
    session = SessionLocal()
    try:
        record = session.query(TokenDynamic).filter_by(token_address=token_address).first()
        return record
    finally:
        session.close()

def save_token_dynamics(
    token_address,
    market_cap_usd=None,
    reserveUSD=None,
    tx_count=None,
    totalVolumen=None,
    totalVolumen1=None,
    clog=None,
    clog_percent=None,
    curent_bundle_balance_token=None,
    curent_sniper_balance_token_percent=None,
    total_bundle_worth=None,
    total_sniper_worth=None,
    total_ethb=None,
    total_eths=None,
    bundle_arrow=None,
    sniper_arrow=None,
    market_cap_arrow=None,
    buys_24h=None,
    sells_24h=None
):
    session = SessionLocal()
    try:
        existing = session.query(TokenDynamic).filter_by(token_address=token_address).first()
        if existing:
            if market_cap_usd is not None:
                existing.market_cap_usd = market_cap_usd
            if reserveUSD is not None:
                existing.reserveUSD = reserveUSD
            if tx_count is not None:
                existing.tx_count = tx_count
            if totalVolumen is not None:
                existing.totalVolumen = totalVolumen
            if totalVolumen1 is not None:
                existing.totalVolumen1 = totalVolumen1
            if clog is not None:
                existing.clog = clog
            if clog_percent is not None:
                existing.clog_percent = clog_percent
            if curent_bundle_balance_token is not None:
                existing.curent_bundle_balance_token = curent_bundle_balance_token
            if curent_sniper_balance_token_percent is not None:
                existing.curent_sniper_balance_token_percent = curent_sniper_balance_token_percent
            if total_bundle_worth is not None:
                existing.total_bundle_worth = total_bundle_worth
            if total_sniper_worth is not None:
                existing.total_sniper_worth = total_sniper_worth
            if total_ethb is not None:
                existing.total_ethb = total_ethb
            if total_eths is not None:
                existing.total_eths = total_eths
            #if bundle_arrow is not None:
            #    existing.bundle_arrow = bundle_arrow
            #if sniper_arrow is not None:
            #    existing.sniper_arrow = sniper_arrow
            #if market_cap_arrow is not None:
            #    existing.market_cap_arrow = market_cap_arrow
            if buys_24h is not None:
                existing.buys_24h=buys_24h
            if sells_24h is not None:
                existing.sells_24h=sells_24h
            existing.bundle_arrow = bundle_arrow  # force overwrite
            existing.sniper_arrow = sniper_arrow
            existing.market_cap_arrow = market_cap_arrow

            existing.updated_at = datetime.utcnow()
        else:
            new_entry = TokenDynamic(
                token_address=token_address,
                market_cap_usd=market_cap_usd,
                reserveUSD=reserveUSD,
                tx_count=tx_count,
                totalVolumen=totalVolumen,
                totalVolumen1=totalVolumen1,
                clog=clog,
                clog_percent=clog_percent,
                curent_bundle_balance_token=curent_bundle_balance_token,
                curent_sniper_balance_token_percent=curent_sniper_balance_token_percent,
                total_sniper_worth=total_sniper_worth,
                total_bundle_worth=total_bundle_worth,
                total_ethb=total_ethb,
                total_eths=total_eths,
                bundle_arrow=bundle_arrow,
                sniper_arrow=sniper_arrow,
                market_cap_arrow=market_cap_arrow,
                buys_24h=buys_24h,
                sells_24h=sells_24h,
                updated_at=datetime.utcnow()
            )
            session.add(new_entry)

        session.commit()
    finally:
        session.close()

def save_transaction_snapshot(token_address, tx_data, update_dynamic_only=False):
    session = SessionLocal()
    try:
        tx_hash = tx_data.get("transactionHash")
        if not tx_hash:
            return

        # 🔁 Field mapping
        field_map = {
            "transactionHash": "tx_hash",
            "from": "from_address",
            "to": "to_address",
            "input": "input_data",
            "tokenValue": "token_value",
            "tokenBalance": "token_balance",
            "balancePercentage": "balance_percent",
            "receivedPercentage": "received_percent",
            "ethBalance": "eth_balance",
            "gasPrice": "gas_price",
            "gasUsed": "gas_used",
            "cumulativeGasUsed": "cumulative_gas_used",
            "transactionIndex": "tx_index",
            "methodId": "method_id",
            "blockNumber": "block_number",
            "value": "value",                      # 👈 raw wei
            "valueInEther": "value_in_ether",
            "transfer_amount": "transfer_amount",
        }

        # Build mapped data
        mapped_data = {}
        for key, value in tx_data.items():
            db_key = field_map.get(key, key)
            if value is not None:
                mapped_data[db_key] = value

        mapped_data["token_address"] = token_address.lower()

        # ✅ Filter out unmapped/unexpected keys
        allowed_fields = {col.name for col in TransactionSnapshot.__table__.columns}
        cleaned_data = {k: v for k, v in mapped_data.items() if k in allowed_fields}

        # Dynamic-only update scope
        dynamic_fields = {
            "token_value",
            "token_balance",
            "balance_percent",
            "received_percent",
            "eth_balance",
            "token_address",
        }

        # Insert/update
        existing = session.query(TransactionSnapshot).filter_by(tx_hash=cleaned_data["tx_hash"]).first()
        if existing:
            for key, value in cleaned_data.items():
                if hasattr(existing, key):
                    if not update_dynamic_only or key in dynamic_fields or key == "token_address":
                        setattr(existing, key, value)
        else:
            new_snapshot = TransactionSnapshot(**cleaned_data)
            session.add(new_snapshot)

        session.commit()
    except Exception as e:
        session.rollback()
    finally:
        session.close()

def get_transaction_snapshots(token_address):
    token_address = token_address.lower()
    session = SessionLocal()
    try:
        snapshots = session.query(TransactionSnapshot).filter(func.lower(TransactionSnapshot.token_address) == token_address.lower())
        return snapshots
    except Exception as e:
        return []
    finally:
        session.close()

def save_user_interaction(message_id, user_id=None ,username=None,token_address=None, refresh_count=1, requested_at=None):
    session = SessionLocal()
    try:
        if requested_at is None:
            requested_at = datetime.utcnow()

        # ✅ Query by message_id to ensure uniqueness per interaction
        existing = session.query(UserInteraction).filter_by(message_id=message_id).first()

        if existing:
            existing.refresh_count = refresh_count
            existing.requested_at = requested_at
        else:
            new_interaction = UserInteraction(
                user_id=user_id,
                username=username,
                message_id=message_id,
                token_address=token_address,
                refresh_count=refresh_count,
                requested_at=requested_at
            )
            session.add(new_interaction)

        session.commit()

    except Exception as e:
        session.rollback()
    finally:
        session.close()

def get_token_address_by_message_id(message_id):
    session = SessionLocal()
    try:
        record = session.query(UserInteraction).filter_by(message_id=message_id).first()
        return record.token_address if record else None
    finally:
        session.close()

def save_wallet_to_db(user_id: int, slot: int, address: str, nickname: str = None, username: str=None):
    existing = session.query(SavedWallets).filter_by(user_id=user_id, slot=slot).first()

    if existing:
        existing.address = address
        existing.nickname = nickname
    else:
        new_wallet = SavedWallets(
            user_id=user_id,
            username=username,
            slot=slot,
            address=address,
            nickname=nickname
        )
        session.add(new_wallet)

    session.commit()

def get_user_wallets(user_id, max_slots=4):
    all_slots = [None] * max_slots
    wallets = session.query(SavedWallets).filter_by(user_id=user_id).all()
    for wallet in wallets:
        if 0 <= wallet.slot < max_slots:
            all_slots[wallet.slot] = {
                "nickname": wallet.nickname or f"Wallet {wallet.slot + 1}",
                "address": wallet.address
            }
    return all_slots

def save_token_call(user_id, token_address, symbol, price, name, username=None, first_name=None):

    session = SessionLocal()
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        # Check if this user already called this token in last 24h
        existing = session.query(TokenCall).filter(
            TokenCall.user_id == user_id,
            TokenCall.token_address == token_address.lower(),
            TokenCall.timestamp > cutoff_time
        ).first()

        if existing:
            return False  # Already called in last 24h

        call = TokenCall(
            user_id=user_id,
            token_address=token_address,
            name=name,
            symbol=symbol,
            price=price,
            timestamp=datetime.utcnow(),
            username=username,
            first_name=first_name
            )

        session.add(call)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"❌ Error saving token call: {e}")
        return False
    finally:
        session.close()

def get_user_calls(user_id, hours=24):
    session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return session.query(TokenCall).filter(
            TokenCall.user_id == user_id,
            TokenCall.timestamp > cutoff
        ).all()
    finally:
        session.close()

def get_recent_token_calls(hours=24):
    session = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return session.query(TokenCall).filter(TokenCall.timestamp > cutoff).all()
    finally:
        session.close()
price_cache={}
def get_cached_price(token_address: str, max_age: int = 300):
    entry = price_cache.get(token_address.lower())
    if not entry:
        return None
    if time.time() - entry["timestamp"] > max_age:
        return None
    return entry["price"]

def update_price_cache(token_address: str, price: float):
    price_cache[token_address.lower()] = {
        "price": price,
        "timestamp": time.time()
    }