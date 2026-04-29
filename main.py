from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas
from database import engine, get_db
import random
from datetime import datetime, timedelta

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cryptocurrency Simulation API", version="1.0.0")

# CORS middleware for Android app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Android app domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ ROOT ============

@app.get("/")
def root():
    return {"message": "Cryptocurrency Simulation API Connected", "version": "1.0.0"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    return {"status": "healthy", "database": "connected"}

# ============ INITIALIZATION ============

@app.post("/initialize")
def initialize_simulation(db: Session = Depends(get_db)):
    """Initialize the simulation with some sample cryptocurrencies and users"""
    # Sample cryptocurrencies
    cryptos = [
        {"symbol": "BTC", "name": "Bitcoin", "current_price": 45000.0, "market_cap": 850000000000.0},
        {"symbol": "ETH", "name": "Ethereum", "current_price": 3000.0, "market_cap": 360000000000.0},
        {"symbol": "ADA", "name": "Cardano", "current_price": 0.5, "market_cap": 17000000000.0},
        {"symbol": "SOL", "name": "Solana", "current_price": 100.0, "market_cap": 45000000000.0},
        {"symbol": "DOT", "name": "Polkadot", "current_price": 15.0, "market_cap": 18000000000.0},
    ]

    for crypto_data in cryptos:
        existing = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.symbol == crypto_data["symbol"]).first()
        if not existing:
            crypto = models.Cryptocurrency(**crypto_data)
            db.add(crypto)

    # Create sample users
    sample_users = ["user1@example.com", "user2@example.com", "user3@example.com"]
    for email in sample_users:
        existing_user = db.query(models.User).filter(models.User.email == email).first()
        if not existing_user:
            user = models.User(email=email)
            db.add(user)

    db.commit()
    return {"message": "Simulation initialized with sample cryptocurrencies and 3 users"}

@app.post("/simulate-price-changes")
def simulate_price_changes(db: Session = Depends(get_db)):
    """Simulate random price changes for all cryptocurrencies and record price history"""
    cryptos = db.query(models.Cryptocurrency).all()

    for crypto in cryptos:
        # Record current price in history before changing
        price_history = models.CryptocurrencyPriceHistory(
            crypto_symbol=crypto.symbol,
            price=crypto.current_price
        )
        db.add(price_history)

        # Random price change between -5% and +5%
        change_percent = random.uniform(-0.05, 0.05)
        new_price = crypto.current_price * (1 + change_percent)
        crypto.current_price = max(0.01, new_price)  # Ensure price doesn't go below $0.01
        crypto.price_change_24h = change_percent * 100
        crypto.last_updated = datetime.utcnow()

    db.commit()
    return {"message": "Price changes simulated and history recorded", "cryptos_updated": len(cryptos)}

# ============ USER ENDPOINTS ============

@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = models.User(email=user.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/users/{email}", response_model=schemas.UserResponse)
def get_user(email: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# ============ CRYPTOCURRENCY ENDPOINTS ============

@app.get("/cryptocurrencies/", response_model=List[schemas.CryptocurrencyResponse])
def get_cryptocurrencies(db: Session = Depends(get_db)):
    """Get all available cryptocurrencies"""
    return db.query(models.Cryptocurrency).all()

@app.get("/cryptocurrencies/{symbol}/history", response_model=List[schemas.CryptocurrencyPriceHistoryResponse])
def get_cryptocurrency_history(
    symbol: str,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get price history for a specific cryptocurrency"""
    history = db.query(models.CryptocurrencyPriceHistory).filter(
        models.CryptocurrencyPriceHistory.crypto_symbol == symbol.upper()
    ).order_by(models.CryptocurrencyPriceHistory.timestamp.desc()).limit(limit).all()

    return history

# ============ PORTFOLIO ENDPOINTS ============

@app.get("/portfolio/{email}", response_model=schemas.PortfolioSummary)
def get_portfolio(email: str, db: Session = Depends(get_db)):
    """Get user's portfolio summary"""
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    portfolio_entries = db.query(models.Portfolio).filter(models.Portfolio.user_id == user.id).all()

    total_value = 0.0
    total_invested = 0.0

    holdings = []
    for entry in portfolio_entries:
        crypto = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.symbol == entry.crypto_symbol).first()
        if crypto:
            current_value = entry.amount_owned * crypto.current_price
            invested_value = entry.amount_owned * entry.average_buy_price
            total_value += current_value
            total_invested += invested_value

            holdings.append(schemas.PortfolioWithCrypto(
                id=entry.id,
                user_id=entry.user_id,
                crypto_symbol=entry.crypto_symbol,
                amount_owned=entry.amount_owned,
                average_buy_price=entry.average_buy_price,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
                cryptocurrency=crypto
            ))

    total_pnl = total_value - total_invested
    total_pnl_percentage = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    return schemas.PortfolioSummary(
        total_value=total_value,
        total_invested=total_invested,
        total_pnl=total_pnl,
        total_pnl_percentage=total_pnl_percentage,
        holdings=holdings
    )

# ============ TRADING ENDPOINTS ============

@app.post("/trade/{email}", response_model=schemas.TradeResponse)
def execute_trade(email: str, trade: schemas.TradeRequest, db: Session = Depends(get_db)):
    """Execute a buy or sell trade"""
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    crypto = db.query(models.Cryptocurrency).filter(models.Cryptocurrency.symbol == trade.crypto_symbol.upper()).first()
    if not crypto:
        raise HTTPException(status_code=404, detail="Cryptocurrency not found")

    amount = trade.amount
    price_per_unit = crypto.current_price
    total_value = abs(amount) * price_per_unit

    if amount > 0:  # BUY
        if user.balance < total_value:
            return schemas.TradeResponse(
                success=False,
                message=f"Insufficient balance. Required: ${total_value:.2f}, Available: ${user.balance:.2f}",
                new_balance=user.balance,
                transaction=None,
                portfolio_update=None
            )

        # Deduct from balance
        user.balance -= total_value

        # Update or create portfolio entry
        portfolio_entry = db.query(models.Portfolio).filter(
            models.Portfolio.user_id == user.id,
            models.Portfolio.crypto_symbol == trade.crypto_symbol.upper()
        ).first()

        if portfolio_entry:
            # Update existing position
            total_amount = portfolio_entry.amount_owned + amount
            total_cost = (portfolio_entry.amount_owned * portfolio_entry.average_buy_price) + total_value
            portfolio_entry.average_buy_price = total_cost / total_amount
            portfolio_entry.amount_owned = total_amount
        else:
            # Create new position
            portfolio_entry = models.Portfolio(
                user_id=user.id,
                crypto_symbol=trade.crypto_symbol.upper(),
                amount_owned=amount,
                average_buy_price=price_per_unit
            )
            db.add(portfolio_entry)

        transaction_type = models.TransactionType.BUY

    else:  # SELL
        amount = abs(amount)  # Make positive for calculations
        portfolio_entry = db.query(models.Portfolio).filter(
            models.Portfolio.user_id == user.id,
            models.Portfolio.crypto_symbol == trade.crypto_symbol.upper()
        ).first()

        if not portfolio_entry or portfolio_entry.amount_owned < amount:
            return schemas.TradeResponse(
                success=False,
                message=f"Insufficient holdings. Required: {amount}, Available: {portfolio_entry.amount_owned if portfolio_entry else 0}",
                new_balance=user.balance,
                transaction=None,
                portfolio_update=None
            )

        # Add to balance
        user.balance += total_value

        # Update portfolio
        portfolio_entry.amount_owned -= amount
        if portfolio_entry.amount_owned <= 0:
            db.delete(portfolio_entry)
            portfolio_entry = None

        transaction_type = models.TransactionType.SELL

    # Create transaction record
    transaction = models.Transaction(
        user_id=user.id,
        crypto_symbol=trade.crypto_symbol.upper(),
        transaction_type=transaction_type,
        amount=abs(trade.amount),
        price_per_unit=price_per_unit,
        total_value=total_value
    )
    db.add(transaction)

    db.commit()
    db.refresh(transaction)
    if portfolio_entry:
        db.refresh(portfolio_entry)

    return schemas.TradeResponse(
        success=True,
        message=f"Trade executed successfully",
        new_balance=user.balance,
        transaction=transaction,
        portfolio_update=portfolio_entry
    )

# ============ TRANSACTION HISTORY ============

@app.get("/transactions/{email}", response_model=List[schemas.TransactionWithCrypto])
def get_transaction_history(
    email: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get user's transaction history"""
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    transactions = db.query(models.Transaction).filter(
        models.Transaction.user_id == user.id
    ).order_by(models.Transaction.timestamp.desc()).offset(skip).limit(limit).all()

    result = []
    for transaction in transactions:
        crypto = db.query(models.Cryptocurrency).filter(
            models.Cryptocurrency.symbol == transaction.crypto_symbol
        ).first()
        result.append(schemas.TransactionWithCrypto(
            id=transaction.id,
            user_id=transaction.user_id,
            crypto_symbol=transaction.crypto_symbol,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            price_per_unit=transaction.price_per_unit,
            total_value=transaction.total_value,
            timestamp=transaction.timestamp,
            cryptocurrency=crypto
        ))

    return result

# ============ USER STATS ============

@app.get("/stats/{email}")
def get_user_stats(email: str, db: Session = Depends(get_db)):
    """Get user's trading statistics"""
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    transactions = db.query(models.Transaction).filter(models.Transaction.user_id == user.id).all()

    total_trades = len(transactions)
    buy_trades = len([t for t in transactions if t.transaction_type == models.TransactionType.BUY])
    sell_trades = len([t for t in transactions if t.transaction_type == models.TransactionType.SELL])

    total_volume = sum(t.total_value for t in transactions)

    return {
        "user_email": email,
        "current_balance": user.balance,
        "total_trades": total_trades,
        "buy_trades": buy_trades,
        "sell_trades": sell_trades,
        "total_volume": total_volume,
        "member_since": user.created_at
    }