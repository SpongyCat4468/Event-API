from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import enum

# python -m uvicorn main:app --reload

class TransactionType(enum.Enum):
    BUY = "buy"
    SELL = "sell"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    balance = Column(Float, default=10000.0)  # Starting balance in USD
    created_at = Column(DateTime, default=datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

class Cryptocurrency(Base):
    __tablename__ = "cryptocurrencies"

    symbol = Column(String, primary_key=True, index=True)  # e.g., "BTC", "ETH"
    name = Column(String, nullable=False)
    current_price = Column(Float, nullable=False)
    market_cap = Column(Float, nullable=True)
    volume_24h = Column(Float, nullable=True)
    price_change_24h = Column(Float, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    portfolio_entries = relationship("Portfolio", back_populates="cryptocurrency", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="cryptocurrency", cascade="all, delete-orphan")
    price_history = relationship("CryptocurrencyPriceHistory", back_populates="cryptocurrency", cascade="all, delete-orphan")

class Portfolio(Base):
    __tablename__ = "portfolio"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    crypto_symbol = Column(String, ForeignKey("cryptocurrencies.symbol"), nullable=False)
    amount_owned = Column(Float, nullable=False, default=0.0)
    average_buy_price = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="portfolio")
    cryptocurrency = relationship("Cryptocurrency", back_populates="portfolio_entries")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    crypto_symbol = Column(String, ForeignKey("cryptocurrencies.symbol"), nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)  # Amount of crypto bought/sold
    price_per_unit = Column(Float, nullable=False)  # Price at time of transaction
    total_value = Column(Float, nullable=False)  # amount * price_per_unit
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")
    cryptocurrency = relationship("Cryptocurrency", back_populates="transactions")

class CryptocurrencyPriceHistory(Base):
    __tablename__ = "cryptocurrency_price_history"

    id = Column(Integer, primary_key=True, index=True)
    crypto_symbol = Column(String, ForeignKey("cryptocurrencies.symbol"), nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    cryptocurrency = relationship("Cryptocurrency", back_populates="price_history")