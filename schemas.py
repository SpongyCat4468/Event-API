from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import enum

class TransactionType(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"

# User schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    balance: float
    created_at: datetime

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    balance: Optional[float] = None

# Cryptocurrency schemas
class CryptocurrencyBase(BaseModel):
    symbol: str
    name: str
    current_price: float
    market_cap: Optional[float] = None
    volume_24h: Optional[float] = None
    price_change_24h: Optional[float] = None

class CryptocurrencyCreate(CryptocurrencyBase):
    pass

class CryptocurrencyUpdate(BaseModel):
    current_price: Optional[float] = None
    market_cap: Optional[float] = None
    volume_24h: Optional[float] = None
    price_change_24h: Optional[float] = None

class CryptocurrencyResponse(CryptocurrencyBase):
    last_updated: datetime

    class Config:
        from_attributes = True

# Portfolio schemas
class PortfolioBase(BaseModel):
    crypto_symbol: str
    amount_owned: float
    average_buy_price: float

class PortfolioCreate(PortfolioBase):
    pass

class PortfolioUpdate(BaseModel):
    amount_owned: Optional[float] = None
    average_buy_price: Optional[float] = None

class PortfolioResponse(PortfolioBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PortfolioWithCrypto(PortfolioResponse):
    cryptocurrency: CryptocurrencyResponse

# Transaction schemas
class TransactionBase(BaseModel):
    crypto_symbol: str
    transaction_type: TransactionType
    amount: float
    price_per_unit: float
    total_value: float

class TransactionCreate(TransactionBase):
    pass

class TransactionResponse(TransactionBase):
    id: int
    user_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class TransactionWithCrypto(TransactionResponse):
    cryptocurrency: CryptocurrencyResponse

# Trading schemas
class TradeRequest(BaseModel):
    crypto_symbol: str
    amount: float  # Positive for buy, negative for sell

class TradeResponse(BaseModel):
    success: bool
    message: str
    transaction: Optional[TransactionResponse] = None
    new_balance: float
    portfolio_update: Optional[PortfolioResponse] = None

# Portfolio summary
class PortfolioSummary(BaseModel):
    total_value: float
    total_invested: float
    total_pnl: float
    total_pnl_percentage: float
    holdings: List[PortfolioWithCrypto]

class CryptocurrencyPriceHistoryResponse(BaseModel):
    id: int
    crypto_symbol: str
    price: float
    timestamp: datetime

    class Config:
        from_attributes = True