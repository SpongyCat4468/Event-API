from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from models import TradeType


# ── Crypto schemas ──────────────────────────────────────────────────────────

class CryptoOut(BaseModel):
    id: int
    symbol: str
    name: str
    current_price: float

    model_config = {"from_attributes": True}


class CryptoPriceUpdate(BaseModel):
    price: float = Field(..., gt=0, description="New price must be positive")


class PriceHistoryOut(BaseModel):
    price: float
    recorded_at: datetime

    model_config = {"from_attributes": True}


# ── Team schemas ─────────────────────────────────────────────────────────────

class TeamOut(BaseModel):
    id: int
    name: str
    balance: float

    model_config = {"from_attributes": True}


class HoldingOut(BaseModel):
    crypto_symbol: str
    crypto_name: str
    quantity: float
    current_price: float
    current_value: float

    model_config = {"from_attributes": True}


class TeamDetailOut(BaseModel):
    id: int
    name: str
    balance: float
    holdings: list[HoldingOut]
    total_portfolio_value: float

    model_config = {"from_attributes": True}


# ── Trade schemas ─────────────────────────────────────────────────────────────

class TradeRequest(BaseModel):
    team_name: str
    crypto_symbol: str
    quantity: float = Field(..., gt=0, description="Quantity must be positive")


class TradeOut(BaseModel):
    id: int
    team_name: str
    crypto_symbol: str
    trade_type: TradeType
    quantity: float
    price_at_trade: float
    total_value: float
    executed_at: datetime

    model_config = {"from_attributes": True}