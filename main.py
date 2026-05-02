from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from database import engine, get_db, Base
import models
import schemas

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Crypto Trading Simulation API",
    description="A cryptocurrency trading simulation for Discord bots. Manages 3 teams and 3 cryptocurrencies.",
    version="1.0.0",
)


# ── Seed helper ──────────────────────────────────────────────────────────────

def seed_data(db: Session):
    """Populate the DB with default teams and cryptos if empty."""
    if db.query(models.Team).count() == 0:
        teams = [
            models.Team(name="Zeroth", balance=10000.0),   # 零小
            models.Team(name="First",  balance=10000.0), # 一小
            models.Team(name="Second", balance=10000.0), # 二小
        ]
        db.add_all(teams)

    if db.query(models.Crypto).count() == 0:
        cryptos = [
            models.Crypto(symbol="BTC", name="Bitcoin",  current_price=65000.0),
            models.Crypto(symbol="ETH", name="Ethereum", current_price=3200.0),
            models.Crypto(symbol="SOL", name="Solana",   current_price=150.0),
        ]
        db.add_all(cryptos)
        db.flush()

        # Record initial prices in history
        for crypto in db.query(models.Crypto).all():
            db.add(models.PriceHistory(crypto_id=crypto.id, price=crypto.current_price))

    db.commit()


@app.on_event("startup")
def on_startup():
    db = next(get_db())
    seed_data(db)


# ────────────────────────────────────────────────────────────────────────────
# Crypto endpoints
# ────────────────────────────────────────────────────────────────────────────
@app.post("/teams/{team_name}/reset/balance", response_model=schemas.TeamDetailOut, tags=["Teams"])
def reset_team_balance(
    team_name: str, 
    balance: float, 
    db: Session = Depends(get_db)
):
    """
    Manually set a team's balance.
    """
    team = db.query(models.Team).filter(
        models.Team.name == team_name.capitalize()
    ).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")

    team.balance = balance

    db.commit()
    db.refresh(team)
    return _build_team_detail(team, db)

@app.post("/teams/{team_name}/reset/holdings", response_model=schemas.TeamDetailOut, tags=["Teams"])
def reset_team_holdings(
    team_name: str, 
    holdings: dict[str, float], 
    db: Session = Depends(get_db)
):
    """
    Manually set a team's holdings.
    'holdings' should be a dictionary of {symbol: quantity}.
    """
    team = db.query(models.Team).filter(
        models.Team.name == team_name.capitalize()
    ).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")

    # Clear existing holdings
    db.query(models.Holding).filter(models.Holding.team_id == team.id).delete()

    # Add new holdings
    for symbol, quantity in holdings.items():
        crypto = db.query(models.Crypto).filter(models.Crypto.symbol == symbol.upper()).first()
        if not crypto:
            raise HTTPException(status_code=404, detail=f"Crypto '{symbol}' not found")
        
        new_holding = models.Holding(
            team_id=team.id,
            crypto_id=crypto.id,
            quantity=quantity
        )
        db.add(new_holding)

    db.commit()
    db.refresh(team)
    return _build_team_detail(team, db)

@app.get("/cryptos", response_model=list[schemas.CryptoOut], tags=["Crypto"])
def list_cryptos(db: Session = Depends(get_db)):
    """Return all cryptocurrencies with their current prices."""
    return db.query(models.Crypto).all()


@app.get("/cryptos/{symbol}", response_model=schemas.CryptoOut, tags=["Crypto"])
def get_crypto(symbol: str, db: Session = Depends(get_db)):
    """Return details for a single cryptocurrency by symbol (e.g. BTC)."""
    crypto = db.query(models.Crypto).filter(
        models.Crypto.symbol == symbol.upper()
    ).first()
    if not crypto:
        raise HTTPException(status_code=404, detail=f"Crypto '{symbol}' not found")
    return crypto


@app.get("/cryptos/{symbol}/history", response_model=list[schemas.PriceHistoryOut], tags=["Crypto"])
def get_price_history(symbol: str, db: Session = Depends(get_db)):
    """Return full price history for a cryptocurrency."""
    crypto = db.query(models.Crypto).filter(
        models.Crypto.symbol == symbol.upper()
    ).first()
    if not crypto:
        raise HTTPException(status_code=404, detail=f"Crypto '{symbol}' not found")
    return (
        db.query(models.PriceHistory)
        .filter(models.PriceHistory.crypto_id == crypto.id)
        .order_by(models.PriceHistory.recorded_at)
        .all()
    )


@app.patch("/cryptos/{symbol}/price", response_model=schemas.CryptoOut, tags=["Crypto"])
def update_price(
    symbol: str,
    body: schemas.CryptoPriceUpdate,
    db: Session = Depends(get_db),
):
    """
    Update the current price of a cryptocurrency and record it in history.
    Call this endpoint from your bot's price-simulation loop.
    """
    crypto = db.query(models.Crypto).filter(
        models.Crypto.symbol == symbol.upper()
    ).first()
    if not crypto:
        raise HTTPException(status_code=404, detail=f"Crypto '{symbol}' not found")

    crypto.current_price = body.price
    db.add(models.PriceHistory(crypto_id=crypto.id, price=body.price))
    db.commit()
    db.refresh(crypto)
    return crypto


# ────────────────────────────────────────────────────────────────────────────
# Team endpoints
# ────────────────────────────────────────────────────────────────────────────

def _build_team_detail(team: models.Team, db: Session) -> schemas.TeamDetailOut:
    holdings_out = []
    portfolio_value = team.balance

    for holding in team.holdings:
        if holding.quantity <= 0:
            continue
        crypto = holding.crypto
        current_value = holding.quantity * crypto.current_price
        portfolio_value += current_value
        holdings_out.append(
            schemas.HoldingOut(
                crypto_symbol=crypto.symbol,
                crypto_name=crypto.name,
                quantity=holding.quantity,
                current_price=crypto.current_price,
                current_value=current_value,
            )
        )

    return schemas.TeamDetailOut(
        id=team.id,
        name=team.name,
        balance=team.balance,
        holdings=holdings_out,
        total_portfolio_value=portfolio_value,
    )


@app.get("/teams", response_model=list[schemas.TeamOut], tags=["Teams"])
def list_teams(db: Session = Depends(get_db)):
    """Return all teams with their current USD balance."""
    return db.query(models.Team).all()


@app.get("/teams/{team_name}", response_model=schemas.TeamDetailOut, tags=["Teams"])
def get_team(team_name: str, db: Session = Depends(get_db)):
    """Return a team's balance, holdings, and total portfolio value."""
    team = db.query(models.Team).filter(
        models.Team.name == team_name.capitalize()
    ).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")
    return _build_team_detail(team, db)


@app.get("/teams/{team_name}/trades", response_model=list[schemas.TradeOut], tags=["Teams"])
def get_team_trades(team_name: str, db: Session = Depends(get_db)):
    """Return the full trade history for a team."""
    team = db.query(models.Team).filter(
        models.Team.name == team_name.capitalize()
    ).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")

    trades = (
        db.query(models.Trade)
        .filter(models.Trade.team_id == team.id)
        .order_by(models.Trade.executed_at.desc())
        .all()
    )

    result = []
    for t in trades:
        result.append(
            schemas.TradeOut(
                id=t.id,
                team_name=team.name,
                crypto_symbol=t.crypto.symbol,
                trade_type=t.trade_type,
                quantity=t.quantity,
                price_at_trade=t.price_at_trade,
                total_value=t.total_value,
                executed_at=t.executed_at,
            )
        )
    return result


# ────────────────────────────────────────────────────────────────────────────
# Trade endpoints
# ────────────────────────────────────────────────────────────────────────────

@app.post("/trade/buy", response_model=schemas.TradeOut, tags=["Trading"])
def buy_crypto(body: schemas.TradeRequest, db: Session = Depends(get_db)):
    """
    Buy cryptocurrency for a team.
    Deducts USD balance and adds to the team's holdings.
    """
    team = db.query(models.Team).filter(
        models.Team.name == body.team_name.capitalize()
    ).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{body.team_name}' not found")

    crypto = db.query(models.Crypto).filter(
        models.Crypto.symbol == body.crypto_symbol.upper()
    ).first()
    if not crypto:
        raise HTTPException(status_code=404, detail=f"Crypto '{body.crypto_symbol}' not found")

    total_cost = body.quantity * crypto.current_price
    if team.balance < total_cost:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Need ${total_cost:.2f}, have ${team.balance:.2f}",
        )

    # Deduct balance
    team.balance -= total_cost

    # Update or create holding
    holding = db.query(models.Holding).filter(
        models.Holding.team_id == team.id,
        models.Holding.crypto_id == crypto.id,
    ).first()
    if holding:
        holding.quantity += body.quantity
    else:
        db.add(models.Holding(team_id=team.id, crypto_id=crypto.id, quantity=body.quantity))

    # Record trade
    trade = models.Trade(
        team_id=team.id,
        crypto_id=crypto.id,
        trade_type=models.TradeType.buy,
        quantity=body.quantity,
        price_at_trade=crypto.current_price,
        total_value=total_cost,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    return schemas.TradeOut(
        id=trade.id,
        team_name=team.name,
        crypto_symbol=crypto.symbol,
        trade_type=trade.trade_type,
        quantity=trade.quantity,
        price_at_trade=trade.price_at_trade,
        total_value=trade.total_value,
        executed_at=trade.executed_at,
    )


@app.post("/trade/sell", response_model=schemas.TradeOut, tags=["Trading"])
def sell_crypto(body: schemas.TradeRequest, db: Session = Depends(get_db)):
    """
    Sell cryptocurrency for a team.
    Adds USD to balance and deducts from the team's holdings.
    """
    team = db.query(models.Team).filter(
        models.Team.name == body.team_name.capitalize()
    ).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{body.team_name}' not found")

    crypto = db.query(models.Crypto).filter(
        models.Crypto.symbol == body.crypto_symbol.upper()
    ).first()
    if not crypto:
        raise HTTPException(status_code=404, detail=f"Crypto '{body.crypto_symbol}' not found")

    holding = db.query(models.Holding).filter(
        models.Holding.team_id == team.id,
        models.Holding.crypto_id == crypto.id,
    ).first()

    if not holding or holding.quantity < body.quantity:
        owned = holding.quantity if holding else 0
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient holdings. Trying to sell {body.quantity}, own {owned:.6f}",
        )

    total_proceeds = body.quantity * crypto.current_price

    # Update balance and holdings
    team.balance += total_proceeds
    holding.quantity -= body.quantity

    # Record trade
    trade = models.Trade(
        team_id=team.id,
        crypto_id=crypto.id,
        trade_type=models.TradeType.sell,
        quantity=body.quantity,
        price_at_trade=crypto.current_price,
        total_value=total_proceeds,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    return schemas.TradeOut(
        id=trade.id,
        team_name=team.name,
        crypto_symbol=crypto.symbol,
        trade_type=trade.trade_type,
        quantity=trade.quantity,
        price_at_trade=trade.price_at_trade,
        total_value=trade.total_value,
        executed_at=trade.executed_at,
    )


# ────────────────────────────────────────────────────────────────────────────
# Leaderboard
# ────────────────────────────────────────────────────────────────────────────

@app.get("/leaderboard", response_model=list[schemas.TeamDetailOut], tags=["Leaderboard"])
def leaderboard(db: Session = Depends(get_db)):
    """Return all teams sorted by total portfolio value (balance + holdings), descending."""
    teams = db.query(models.Team).all()
    details = [_build_team_detail(t, db) for t in teams]
    details.sort(key=lambda t: t.total_portfolio_value, reverse=True)
    return details