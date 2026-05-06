from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone
import enum


class TradeType(str, enum.Enum):
    buy = "buy"
    sell = "sell"


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    balance = Column(Float, default=10000.0)  # Starting balance in USD

    trades = relationship("Trade", back_populates="team")
    holdings = relationship("Holding", back_populates="team")


class Crypto(Base):
    __tablename__ = "cryptos"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, nullable=False)  # e.g. INFOR, CMIOC, IZCC
    name = Column(String, nullable=False)
    current_price = Column(Float, nullable=False)

    price_history = relationship("PriceHistory", back_populates="crypto")
    trades = relationship("Trade", back_populates="crypto")
    holdings = relationship("Holding", back_populates="crypto")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    crypto_id = Column(Integer, ForeignKey("cryptos.id"), nullable=False)
    price = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    crypto = relationship("Crypto", back_populates="price_history")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    crypto_id = Column(Integer, ForeignKey("cryptos.id"), nullable=False)
    trade_type = Column(Enum(TradeType), nullable=False)
    quantity = Column(Float, nullable=False)
    price_at_trade = Column(Float, nullable=False)
    total_value = Column(Float, nullable=False)  # quantity * price_at_trade
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    team = relationship("Team", back_populates="trades")
    crypto = relationship("Crypto", back_populates="trades")


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    crypto_id = Column(Integer, ForeignKey("cryptos.id"), nullable=False)
    quantity = Column(Float, default=0.0)

    team = relationship("Team", back_populates="holdings")
    crypto = relationship("Crypto", back_populates="holdings")
