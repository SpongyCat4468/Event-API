import asyncio
import os
import random
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from database import engine, get_db, Base, SessionLocal
import models
import schemas

BASE_DIR = Path(__file__).resolve().parent

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Crypto Trading Simulation API",
    description="A cryptocurrency trading simulation for Discord bots. Manages 3 teams and 3 cryptocurrencies.",
    version="1.0.0",
)

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


# ── Market simulation state ───────────────────────────────────────────────────

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "jmec-staff")
MARKET_INTERVAL_SECONDS = 10
PRICE_HISTORY_LIMIT = 90
TRADE_IMPACT_DIVISOR = 30000.0
NEWS_LIMIT = 12
FIRST_RANDOM_NEWS_DELAY_SECONDS = 60
RANDOM_NEWS_INTERVAL_SECONDS = (300, 600)
NEWS_IMPACT_TOTAL_SECONDS = 35
NEWS_IMPACT_STRONG_SECONDS = 15
NEWS_IMPACT_STRONG_END_RATE = 0.55
NEWS_IMPACT_TAIL_END_RATE = 0.08

CRYPTO_CATALOG = [
    {
        "symbol": "INFOR",
        "name": "建中資訊社",
        "initial_price": 38.0,
        "legacy_symbol": "BTC",
    },
    {
        "symbol": "CMIOC",
        "name": "景美電資社",
        "initial_price": 32.0,
        "legacy_symbol": "ETH",
    },
    {
        "symbol": "IZCC",
        "name": "四社聯合",
        "initial_price": 116.0,
        "legacy_symbol": "SOL",
    },
]

CRYPTO_ALIAS_MAP = {
    item["legacy_symbol"]: item["symbol"]
    for item in CRYPTO_CATALOG
}

MARKET_PROFILES = {
    "INFOR": {"trend": 0.0, "volatility": 0.026},
    "CMIOC": {"trend": 0.0, "volatility": 0.026},
    "IZCC": {"trend": 0.0, "volatility": 0.03},
}

DEFAULT_TEAM_BALANCES = {
    "Zeroth": 800.0,
    "First": 800.0,
    "Second": 800.0,
}

TEAM_ALIAS_MAP = {
    "zeroth": "Zeroth",
    "0": "Zeroth",
    "零小": "Zeroth",
    "first": "First",
    "1": "First",
    "一小": "First",
    "second": "Second",
    "2": "Second",
    "二小": "Second",
}

RANDOM_MARKET_EVENTS = [
    {
        "headline": "IZCC 辦活動撞段考周導致報名人數過少",
        "symbols": ["IZCC"],
        "effect": "down",
    },
    {
        "headline": "建中資訊社社員穿社服在捷運上坐博愛座遭炎上",
        "symbols": ["INFOR"],
        "effect": "down",
    },
    {
        "headline": "景美電資社學妹因學術力不足遭學姐嫌棄",
        "symbols": ["CMIOC"],
        "effect": "down",
    },
    {
        "headline": "建景聯合送舊的網頁在活動倒數還寫不出來",
        "symbols": ["INFOR", "CMIOC"],
        "effect": "down",
    },
    {
        "headline": "建景聯合送舊的活動內容很豐富獲得長姐好評",
        "symbols": ["INFOR", "CMIOC"],
        "effect": "up",
    },
    {
        "headline": "IZCC 四校聯合暑訓成功吸引學弟妹讓四社皆滿社",
        "symbols": ["IZCC"],
        "effect": "up",
    },
    {
        "headline": "景美電資社學妹因想取得學姐信任努力精進取得大進步",
        "symbols": ["CMIOC"],
        "effect": "up",
    },
    {
        "headline": "建中資訊社社員在 APCS 取得好成績",
        "symbols": ["INFOR"],
        "effect": "up",
    },
]

market_state_lock = Lock()
trade_pressure: dict[str, float] = {}
pending_admin_events: list[dict] = []
active_news_impacts: list[dict] = []
latest_news: list[dict] = []
market_task: Optional[asyncio.Task] = None
next_random_news_at: Optional[datetime] = None
forced_next_random_event_index: Optional[int] = None
triggered_random_headlines: set[str] = set()
game_state = {
    "active": False,
    "started_at": None,
    "ended_at": None,
}


@app.get("/", include_in_schema=False)
def frontend_home():
    """Serve the live market dashboard."""
    return FileResponse(BASE_DIR / "static" / "index.html")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _schedule_next_random_news(delay_seconds: Optional[int] = None) -> None:
    global next_random_news_at
    delay = delay_seconds if delay_seconds is not None else random.randint(*RANDOM_NEWS_INTERVAL_SECONDS)
    next_random_news_at = _now_utc() + timedelta(seconds=delay)


def _clean_team_name(name: str) -> str:
    normalized = name.strip()
    return TEAM_ALIAS_MAP.get(normalized.lower(), TEAM_ALIAS_MAP.get(normalized, normalized.capitalize()))


def _clean_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    return CRYPTO_ALIAS_MAP.get(normalized, normalized)


def _coerce_percent_to_rate(percent: float) -> float:
    """Accept either 5 or 0.05 as 5%."""
    return percent / 100 if percent > 1 else percent


def _record_news(
    headline: str,
    symbol: Optional[str] = None,
    percent: float = 0.0,
    source: str = "system",
) -> dict:
    item = {
        "headline": headline,
        "symbol": symbol,
        "percent": round(percent, 2),
        "source": source,
        "created_at": _now_utc(),
    }
    with market_state_lock:
        latest_news.insert(0, item)
        del latest_news[NEWS_LIMIT:]
    return item


def _format_symbols(symbols: Optional[list[str]]) -> Optional[str]:
    if not symbols:
        return None
    return ",".join(symbols)


def _event_affects_symbol(event: dict, symbol: str) -> bool:
    symbols = event.get("symbols")
    if symbols is not None:
        return symbol in symbols
    return event.get("symbol") in (None, symbol)


def _current_news() -> list[dict]:
    with market_state_lock:
        return list(latest_news)


def _require_admin_token(x_admin_token: Optional[str]) -> None:
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _initial_price_for_symbol(symbol: str) -> float:
    for item in CRYPTO_CATALOG:
        if item["symbol"] == symbol:
            return item["initial_price"]
    raise HTTPException(status_code=404, detail=f"Crypto '{symbol}' not found")


def _reset_runtime_market_state(first_news_delay_seconds: Optional[int] = None) -> None:
    global forced_next_random_event_index
    with market_state_lock:
        trade_pressure.clear()
        pending_admin_events.clear()
        active_news_impacts.clear()
        latest_news.clear()
        triggered_random_headlines.clear()
    forced_next_random_event_index = 5
    _schedule_next_random_news(first_news_delay_seconds)


def _queue_trade_pressure(symbol: str, signed_value: float) -> None:
    with market_state_lock:
        trade_pressure[symbol] = trade_pressure.get(symbol, 0.0) + signed_value


def _queue_admin_event(event: dict) -> None:
    with market_state_lock:
        pending_admin_events.append(event)


def _activate_news_impact(event: dict, now: Optional[datetime] = None) -> None:
    impact_started_at = now or _now_utc()
    impact = {
        "symbols": event.get("symbols"),
        "symbol": event.get("symbol"),
        "rate": event["rate"],
        "started_at": impact_started_at,
        "strong_until": impact_started_at + timedelta(seconds=NEWS_IMPACT_STRONG_SECONDS),
        "expires_at": impact_started_at + timedelta(seconds=NEWS_IMPACT_TOTAL_SECONDS),
        "initial_applied": False,
    }
    with market_state_lock:
        active_news_impacts.append(impact)


def _take_active_news_impacts(now: datetime) -> list[dict]:
    with market_state_lock:
        active_news_impacts[:] = [
            event for event in active_news_impacts
            if now <= event["expires_at"]
        ]
        return list(active_news_impacts)


def _mark_news_impacts_applied(events: list[dict]) -> None:
    with market_state_lock:
        for event in events:
            event["initial_applied"] = True


def _event_rate_for_tick(event: dict, now: datetime) -> float:
    if not event.get("initial_applied"):
        return event["rate"]

    elapsed_seconds = max(0.0, (now - event["started_at"]).total_seconds())
    if elapsed_seconds >= NEWS_IMPACT_TOTAL_SECONDS:
        return 0.0

    if elapsed_seconds <= NEWS_IMPACT_STRONG_SECONDS:
        progress = elapsed_seconds / NEWS_IMPACT_STRONG_SECONDS
        multiplier = 1.0 - ((1.0 - NEWS_IMPACT_STRONG_END_RATE) * progress)
    else:
        tail_seconds = NEWS_IMPACT_TOTAL_SECONDS - NEWS_IMPACT_STRONG_SECONDS
        tail_progress = (elapsed_seconds - NEWS_IMPACT_STRONG_SECONDS) / tail_seconds
        multiplier = NEWS_IMPACT_STRONG_END_RATE - (
            (NEWS_IMPACT_STRONG_END_RATE - NEWS_IMPACT_TAIL_END_RATE) * tail_progress
        )

    return event["rate"] * max(0.0, multiplier)


def _take_market_state_for_tick() -> tuple[dict[str, float], list[dict]]:
    with market_state_lock:
        pressure_snapshot = dict(trade_pressure)
        for symbol, value in list(trade_pressure.items()):
            decayed = value * 0.35
            if abs(decayed) < 1:
                trade_pressure.pop(symbol, None)
            else:
                trade_pressure[symbol] = decayed

        admin_events = list(pending_admin_events)
        pending_admin_events.clear()

    return pressure_snapshot, admin_events


def _format_default_admin_headline(
    event_type: str,
    symbol: Optional[str],
    signed_percent: float,
) -> str:
    target = symbol or "全市場"
    if event_type == "crash":
        return f"工作人員觸發市場崩盤，{target} 下跌 {abs(signed_percent):.1f}%"
    return f"工作人員發布利多消息，{target} 上漲 {abs(signed_percent):.1f}%"


def _price_history_for_crypto(
    db: Session,
    crypto: models.Crypto,
    limit: int = PRICE_HISTORY_LIMIT,
) -> list[schemas.PricePointOut]:
    rows = (
        db.query(models.PriceHistory)
        .filter(models.PriceHistory.crypto_id == crypto.id)
        .order_by(models.PriceHistory.recorded_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        schemas.PricePointOut(price=row.price, recorded_at=row.recorded_at)
        for row in rows
    ]


def _build_price_snapshot(db: Session, crypto: models.Crypto) -> schemas.PriceSnapshotOut:
    history = _price_history_for_crypto(db, crypto)
    change_percent = 0.0
    if len(history) >= 2 and history[-2].price > 0:
        change_percent = ((history[-1].price - history[-2].price) / history[-2].price) * 100

    return schemas.PriceSnapshotOut(
        symbol=crypto.symbol,
        name=crypto.name,
        current_price=crypto.current_price,
        change_percent=round(change_percent, 2),
        history=history,
    )


def _maybe_random_market_event(symbols: list[str]) -> Optional[dict]:
    global forced_next_random_event_index, next_random_news_at

    if not symbols:
        return None

    now = _now_utc()
    if next_random_news_at is None:
        _schedule_next_random_news()
        return None

    if now < next_random_news_at:
        return None

    if forced_next_random_event_index is not None:
        template = RANDOM_MARKET_EVENTS[forced_next_random_event_index]
        forced_next_random_event_index = None
    else:
        eligible_events = [
            event for event in RANDOM_MARKET_EVENTS
            if event["headline"] != "景美電資社學妹因想取得學姐信任努力精進取得大進步"
            or "景美電資社學妹因學術力不足遭學姐嫌棄" in triggered_random_headlines
        ]
        template = random.choice(eligible_events)
    target_symbols = [
        symbol
        for symbol in template["symbols"]
        if symbol in symbols
    ]
    if not target_symbols:
        _schedule_next_random_news()
        return None

    magnitude = random.uniform(0.06, 0.10)
    rate = magnitude if template["effect"] == "up" else -magnitude
    _schedule_next_random_news()
    triggered_random_headlines.add(template["headline"])
    return {
        "symbols": target_symbols,
        "symbol": _format_symbols(target_symbols),
        "rate": rate,
        "percent": rate * 100,
        "headline": template["headline"],
        "source": "random_news",
    }


def run_market_tick() -> None:
    """Update all crypto prices once using trend, volatility, trade impact, and events."""
    db = SessionLocal()
    try:
        now = _now_utc()
        cryptos = db.query(models.Crypto).all()
        symbols = [crypto.symbol for crypto in cryptos]
        pressure_snapshot, admin_events = _take_market_state_for_tick()
        random_event = _maybe_random_market_event(symbols)
        new_events = list(admin_events)
        if random_event:
            new_events.append(random_event)
            _record_news(
                random_event["headline"],
                random_event["symbol"],
                random_event["percent"],
                random_event["source"],
            )

        for event in new_events:
            _activate_news_impact(event, now)

        active_events = _take_active_news_impacts(now)

        for crypto in cryptos:
            profile = MARKET_PROFILES.get(
                crypto.symbol,
                {"trend": 0.0, "volatility": 0.024},
            )
            trend = profile["trend"]
            volatility = random.uniform(-profile["volatility"], profile["volatility"])
            pressure = pressure_snapshot.get(crypto.symbol, 0.0)
            impact = max(-0.08, min(0.08, pressure / TRADE_IMPACT_DIVISOR))
            event_rate = 0.0
            for event in active_events:
                active_event_rate = _event_rate_for_tick(event, now)
                if _event_affects_symbol(event, crypto.symbol):
                    event_rate += active_event_rate
                elif event.get("symbols") or event.get("symbol"):
                    event_rate -= active_event_rate * 0.35

            change_rate = max(-0.65, min(0.65, trend + volatility + impact + event_rate))
            new_price = max(0.0, crypto.current_price * (1 + change_rate))
            crypto.current_price = round(new_price, 2)
            db.add(
                models.PriceHistory(
                        crypto_id=crypto.id,
                        price=crypto.current_price,
                        recorded_at=now,
                    )
                )

        db.commit()
        _mark_news_impacts_applied(active_events)
    finally:
        db.close()


async def market_loop() -> None:
    while True:
        await asyncio.sleep(MARKET_INTERVAL_SECONDS)
        run_market_tick()


# ── Seed helper ──────────────────────────────────────────────────────────────

def migrate_crypto_catalog(db: Session) -> None:
    """Rename legacy BTC/ETH/SOL rows to the event-themed club coins."""
    for item in CRYPTO_CATALOG:
        legacy = db.query(models.Crypto).filter(
            models.Crypto.symbol == item["legacy_symbol"]
        ).first()
        current = db.query(models.Crypto).filter(
            models.Crypto.symbol == item["symbol"]
        ).first()

        if legacy and not current:
            legacy.symbol = item["symbol"]
            legacy.name = item["name"]
        elif current:
            current.name = item["name"]


def seed_data(db: Session):
    """Populate the DB with default teams and cryptos if empty."""
    if db.query(models.Team).count() == 0:
        teams = [
            models.Team(name="Zeroth", balance=DEFAULT_TEAM_BALANCES["Zeroth"]), # 零小
            models.Team(name="First", balance=DEFAULT_TEAM_BALANCES["First"]),   # 一小
            models.Team(name="Second", balance=DEFAULT_TEAM_BALANCES["Second"]), # 二小
        ]
        db.add_all(teams)

    if db.query(models.Crypto).count() == 0:
        cryptos = [
            models.Crypto(
                symbol=item["symbol"],
                name=item["name"],
                current_price=item["initial_price"],
            )
            for item in CRYPTO_CATALOG
        ]
        db.add_all(cryptos)
        db.flush()

        # Record initial prices in history
        for crypto in db.query(models.Crypto).all():
            db.add(models.PriceHistory(crypto_id=crypto.id, price=crypto.current_price))

    migrate_crypto_catalog(db)
    db.commit()


@app.on_event("startup")
async def on_startup():
    global market_task

    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()

    _reset_runtime_market_state(FIRST_RANDOM_NEWS_DELAY_SECONDS)
    market_task = asyncio.create_task(market_loop())


@app.on_event("shutdown")
async def on_shutdown():
    if market_task:
        market_task.cancel()


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
        clean_symbol = _clean_symbol(symbol)
        crypto = db.query(models.Crypto).filter(models.Crypto.symbol == clean_symbol).first()
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


@app.get("/price", response_model=schemas.PriceResponse, tags=["Crypto"])
def get_price(db: Session = Depends(get_db)):
    """Return current prices, recent history, and the latest market news."""
    cryptos = db.query(models.Crypto).order_by(models.Crypto.id).all()
    news = _current_news()
    return schemas.PriceResponse(
        prices=[_build_price_snapshot(db, crypto) for crypto in cryptos],
        latest_news=news[0] if news else None,
        news=news,
        server_time=_now_utc(),
    )


@app.get("/news", response_model=list[schemas.NewsOut], tags=["News"])
def get_news():
    """Return recent market news items."""
    return _current_news()


@app.post("/admin/market-event", response_model=schemas.AdminMarketEventOut, tags=["Admin"])
def trigger_market_event(
    body: schemas.AdminMarketEventRequest,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    """
    Staff-only god mode endpoint.
    Queue a crash or pump event for the next 10-second market tick.
    """
    _require_admin_token(x_admin_token)

    symbol = _clean_symbol(body.symbol) if body.symbol else None
    if symbol:
        crypto = db.query(models.Crypto).filter(models.Crypto.symbol == symbol).first()
        if not crypto:
            raise HTTPException(status_code=404, detail=f"Crypto '{symbol}' not found")

    rate = _coerce_percent_to_rate(body.percent)
    signed_rate = -rate if body.event_type == "crash" else rate
    signed_percent = signed_rate * 100
    headline = body.headline or _format_default_admin_headline(
        body.event_type,
        symbol,
        signed_percent,
    )

    event = {
        "symbol": symbol,
        "rate": signed_rate,
        "percent": signed_percent,
        "headline": headline,
        "source": "admin",
    }
    _queue_admin_event(event)
    news = _record_news(headline, symbol, signed_percent, "admin")

    return schemas.AdminMarketEventOut(
        queued=True,
        headline=headline,
        symbol=symbol,
        percent=round(signed_percent, 2),
        latest_news=news,
    )


@app.get("/cryptos/{symbol}", response_model=schemas.CryptoOut, tags=["Crypto"])
def get_crypto(symbol: str, db: Session = Depends(get_db)):
    """Return details for a single cryptocurrency by symbol (e.g. INFOR)."""
    clean_symbol = _clean_symbol(symbol)
    crypto = db.query(models.Crypto).filter(
        models.Crypto.symbol == clean_symbol
    ).first()
    if not crypto:
        raise HTTPException(status_code=404, detail=f"Crypto '{symbol}' not found")
    return crypto


@app.get("/cryptos/{symbol}/history", response_model=list[schemas.PriceHistoryOut], tags=["Crypto"])
def get_price_history(symbol: str, db: Session = Depends(get_db)):
    """Return full price history for a cryptocurrency."""
    clean_symbol = _clean_symbol(symbol)
    crypto = db.query(models.Crypto).filter(
        models.Crypto.symbol == clean_symbol
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
    clean_symbol = _clean_symbol(symbol)
    crypto = db.query(models.Crypto).filter(
        models.Crypto.symbol == clean_symbol
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


def _get_team_or_404(db: Session, team_name: str) -> models.Team:
    clean_name = _clean_team_name(team_name)
    team = db.query(models.Team).filter(models.Team.name == clean_name).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")
    return team


def _get_crypto_or_404(db: Session, symbol: str) -> models.Crypto:
    clean_symbol = _clean_symbol(symbol)
    crypto = db.query(models.Crypto).filter(models.Crypto.symbol == clean_symbol).first()
    if not crypto:
        raise HTTPException(status_code=404, detail=f"Crypto '{symbol}' not found")
    return crypto


def _build_game_state(db: Session) -> schemas.GameStateOut:
    teams = db.query(models.Team).order_by(models.Team.id).all()
    cryptos = db.query(models.Crypto).order_by(models.Crypto.id).all()
    news = _current_news()
    return schemas.GameStateOut(
        active=bool(game_state["active"]),
        started_at=game_state["started_at"],
        ended_at=game_state["ended_at"],
        teams=[_build_team_detail(team, db) for team in teams],
        prices=[schemas.CryptoOut.model_validate(crypto) for crypto in cryptos],
        latest_news=news[0] if news else None,
    )


def _set_game_prices_to_initial(db: Session) -> None:
    migrate_crypto_catalog(db)
    for item in CRYPTO_CATALOG:
        crypto = db.query(models.Crypto).filter(
            models.Crypto.symbol == item["symbol"]
        ).first()
        if not crypto:
            crypto = models.Crypto(
                symbol=item["symbol"],
                name=item["name"],
                current_price=item["initial_price"],
            )
            db.add(crypto)
        else:
            crypto.name = item["name"]
            crypto.current_price = item["initial_price"]
    db.flush()


def _start_game_with_balances(
    db: Session,
    balances: dict[str, float],
) -> schemas.GameStateOut:
    _set_game_prices_to_initial(db)
    db.query(models.Trade).delete()
    db.query(models.Holding).delete()

    # Clear all historical price points so the frontend chart starts from the new game.
    db.query(models.PriceHistory).delete(synchronize_session=False)

    for team_name, balance in balances.items():
        team = db.query(models.Team).filter(models.Team.name == team_name).first()
        if not team:
            team = models.Team(name=team_name, balance=balance)
            db.add(team)
        else:
            team.balance = balance

    for crypto in db.query(models.Crypto).order_by(models.Crypto.id).all():
        db.add(
            models.PriceHistory(
                crypto_id=crypto.id,
                price=crypto.current_price,
                recorded_at=_now_utc(),
            )
        )

    db.commit()

    game_state["active"] = True
    game_state["started_at"] = _now_utc()
    game_state["ended_at"] = None
    _reset_runtime_market_state(FIRST_RANDOM_NEWS_DELAY_SECONDS)
    return _build_game_state(db)


def _apply_balance_operation(
    team: models.Team,
    operation: str,
    amount: float,
) -> None:
    if operation == "set":
        team.balance = amount
    elif operation == "multiply":
        team.balance *= amount
    elif operation == "add":
        team.balance += amount
    elif operation == "remove":
        team.balance = max(0.0, team.balance - amount)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported operation '{operation}'")


def _get_or_create_holding(
    db: Session,
    team: models.Team,
    crypto: models.Crypto,
) -> models.Holding:
    holding = db.query(models.Holding).filter(
        models.Holding.team_id == team.id,
        models.Holding.crypto_id == crypto.id,
    ).first()
    if not holding:
        holding = models.Holding(team_id=team.id, crypto_id=crypto.id, quantity=0.0)
        db.add(holding)
        db.flush()
    return holding


def _apply_holding_operation(
    holding: models.Holding,
    operation: str,
    quantity: float,
) -> None:
    if operation == "set":
        holding.quantity = quantity
    elif operation == "multiply":
        holding.quantity *= quantity
    elif operation == "add":
        holding.quantity += quantity
    elif operation == "remove":
        holding.quantity = max(0.0, holding.quantity - quantity)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported operation '{operation}'")


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
# Game control / staff tools
# ────────────────────────────────────────────────────────────────────────────

@app.get("/game", response_model=schemas.GameStateOut, tags=["Game"])
def get_game_state(db: Session = Depends(get_db)):
    """Return current game state, teams, and prices."""
    return _build_game_state(db)


@app.post("/admin/game/start", response_model=schemas.GameStateOut, tags=["Admin"])
def start_game(
    body: schemas.StartGameRequest,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    """Reset prices, portfolios, trades, and start the game with team capital."""
    _require_admin_token(x_admin_token)
    return _start_game_with_balances(
        db,
        {
            "Zeroth": body.zeroth_balance,
            "First": body.first_balance,
            "Second": body.second_balance,
        },
    )


@app.post("/admin/game/end", response_model=schemas.GameStateOut, tags=["Admin"])
def end_game(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    """End the active game without wiping balances or holdings."""
    _require_admin_token(x_admin_token)
    game_state["active"] = False
    game_state["ended_at"] = _now_utc()
    return _build_game_state(db)


@app.post("/admin/teams/{team_name}/balance", response_model=schemas.TeamDetailOut, tags=["Admin"])
def manage_team_balance(
    team_name: str,
    body: schemas.BalanceOperationRequest,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    """Staff adjustment for team cash balance."""
    _require_admin_token(x_admin_token)
    team = _get_team_or_404(db, team_name)
    _apply_balance_operation(team, body.operation, body.amount)
    db.commit()
    db.refresh(team)
    return _build_team_detail(team, db)


@app.post("/admin/teams/{team_name}/holdings", response_model=schemas.TeamDetailOut, tags=["Admin"])
def manage_team_holding(
    team_name: str,
    body: schemas.HoldingOperationRequest,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    """Staff adjustment for team crypto holdings."""
    _require_admin_token(x_admin_token)
    team = _get_team_or_404(db, team_name)
    crypto = _get_crypto_or_404(db, body.crypto_symbol)
    holding = _get_or_create_holding(db, team, crypto)
    _apply_holding_operation(holding, body.operation, body.quantity)
    db.commit()
    db.refresh(team)
    return _build_team_detail(team, db)


# ────────────────────────────────────────────────────────────────────────────
# Trade endpoints
# ────────────────────────────────────────────────────────────────────────────

def _execute_trade(
    body: schemas.TradeRequest,
    trade_type: models.TradeType,
    db: Session,
) -> schemas.TradeOut:
    team = db.query(models.Team).filter(
        models.Team.name == _clean_team_name(body.team_name)
    ).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{body.team_name}' not found")

    crypto = db.query(models.Crypto).filter(
        models.Crypto.symbol == _clean_symbol(body.crypto_symbol)
    ).first()
    if not crypto:
        raise HTTPException(status_code=404, detail=f"Crypto '{body.crypto_symbol}' not found")

    total_value = body.quantity * crypto.current_price

    if trade_type == models.TradeType.buy:
        if team.balance < total_value:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance. Need ${total_value:.2f}, have ${team.balance:.2f}",
            )

        team.balance -= total_value

        holding = db.query(models.Holding).filter(
            models.Holding.team_id == team.id,
            models.Holding.crypto_id == crypto.id,
        ).first()
        if holding:
            holding.quantity += body.quantity
        else:
            db.add(
                models.Holding(
                    team_id=team.id,
                    crypto_id=crypto.id,
                    quantity=body.quantity,
                )
            )
    else:
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

        team.balance += total_value
        holding.quantity -= body.quantity
        if holding.quantity < 0.00000001:
            holding.quantity = 0.0

    trade = models.Trade(
        team_id=team.id,
        crypto_id=crypto.id,
        trade_type=trade_type,
        quantity=body.quantity,
        price_at_trade=crypto.current_price,
        total_value=total_value,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    signed_pressure = total_value if trade_type == models.TradeType.buy else -total_value
    _queue_trade_pressure(crypto.symbol, signed_pressure)

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


@app.post("/trade", response_model=schemas.TradeOut, tags=["Trading"])
def trade_crypto(body: schemas.UnifiedTradeRequest, db: Session = Depends(get_db)):
    """
    Unified trading endpoint for Discord bots.
    Send trade_type as "buy" or "sell".
    """
    return _execute_trade(body, body.trade_type, db)


@app.post("/trade/buy", response_model=schemas.TradeOut, tags=["Trading"])
def buy_crypto(body: schemas.TradeRequest, db: Session = Depends(get_db)):
    """
    Buy cryptocurrency for a team.
    Deducts USD balance and adds to the team's holdings.
    """
    return _execute_trade(body, models.TradeType.buy, db)


@app.post("/trade/sell", response_model=schemas.TradeOut, tags=["Trading"])
def sell_crypto(body: schemas.TradeRequest, db: Session = Depends(get_db)):
    """
    Sell cryptocurrency for a team.
    Adds USD to balance and deducts from the team's holdings.
    """
    return _execute_trade(body, models.TradeType.sell, db)


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
