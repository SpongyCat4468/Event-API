from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Optional
from models import TradeType


# ── Crypto schemas ──────────────────────────────────────────────────────────

class CryptoOut(BaseModel):
    id: int
    symbol: str
    name: str
    current_price: float

    model_config = {"from_attributes": True}


class CryptoPriceUpdate(BaseModel):
    price: float = Field(..., ge=0, description="New price must be zero or positive")


class PriceHistoryOut(BaseModel):
    price: float
    recorded_at: datetime

    model_config = {"from_attributes": True}


class PricePointOut(BaseModel):
    price: float
    recorded_at: datetime


class NewsOut(BaseModel):
    headline: str
    symbol: Optional[str] = None
    percent: float = 0.0
    source: str = "system"
    created_at: datetime


class PriceSnapshotOut(BaseModel):
    symbol: str
    name: str
    current_price: float
    change_percent: float
    history: list[PricePointOut]


class PriceResponse(BaseModel):
    prices: list[PriceSnapshotOut]
    latest_news: Optional[NewsOut] = None
    news: list[NewsOut] = []
    server_time: datetime


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


class StartGameRequest(BaseModel):
    zeroth_balance: float = Field(800.0, ge=0)
    first_balance: float = Field(800.0, ge=0)
    second_balance: float = Field(800.0, ge=0)


class GameStateOut(BaseModel):
    active: bool
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    teams: list[TeamDetailOut]
    prices: list[CryptoOut]
    latest_news: Optional[NewsOut] = None


class BalanceOperationRequest(BaseModel):
    operation: Literal["set", "multiply", "add", "remove"]
    amount: float = Field(..., ge=0)


class HoldingOperationRequest(BaseModel):
    operation: Literal["set", "multiply", "add", "remove"]
    crypto_symbol: str
    quantity: float = Field(..., ge=0)


# ── Trade schemas ─────────────────────────────────────────────────────────────

class TradeRequest(BaseModel):
    team_name: str
    crypto_symbol: str
    quantity: float = Field(..., gt=0, description="Quantity must be positive")


class UnifiedTradeRequest(TradeRequest):
    trade_type: TradeType


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


# ── Admin / market event schemas ──────────────────────────────────────────────

class AdminMarketEventRequest(BaseModel):
    event_type: Literal["crash", "pump"]
    symbol: Optional[str] = Field(
        default=None,
        description="Target symbol, e.g. INFOR. Leave empty to affect all cryptos.",
    )
    percent: float = Field(
        ...,
        gt=0,
        le=80,
        description="Event size. Use 5 for 5%, or 0.05 for 5%.",
    )
    headline: Optional[str] = None


class AdminMarketEventOut(BaseModel):
    queued: bool
    headline: str
    symbol: Optional[str]
    percent: float
    latest_news: NewsOut
