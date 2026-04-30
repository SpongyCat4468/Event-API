# Crypto Trading Simulation API

A FastAPI + SQLite backend for running a cryptocurrency trading simulation in Discord bots.

## Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI |
| Database | SQLite (via SQLAlchemy ORM) |
| Validation | Pydantic v2 |
| Server | Uvicorn |

SQLite was chosen over a separate DB server for simplicity — perfect for a Discord bot running on a single machine. If you ever need concurrent writes from multiple processes, swap the `DATABASE_URL` in `database.py` to PostgreSQL.

---

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Interactive docs available at: http://localhost:8000/docs

---

## Default Data

On first startup the API seeds:

**Teams** (each starting with $10,000 USD):
- Alpha, Beta, Gamma

**Cryptocurrencies**:
- BTC (Bitcoin) — $65,000
- ETH (Ethereum) — $3,200
- SOL (Solana) — $150

---

## API Reference

### Crypto

| Method | Endpoint | Description |
|---|---|---|
| GET | `/cryptos` | List all cryptos with current prices |
| GET | `/cryptos/{symbol}` | Get a single crypto (e.g. `/cryptos/BTC`) |
| GET | `/cryptos/{symbol}/history` | Full price history for a crypto |
| PATCH | `/cryptos/{symbol}/price` | Update price (use in your simulation loop) |

**Update price example:**
```json
PATCH /cryptos/BTC/price
{ "price": 67500.0 }
```

---

### Teams

| Method | Endpoint | Description |
|---|---|---|
| GET | `/teams` | List all teams and their USD balances |
| GET | `/teams/{team_name}` | Team detail: balance, holdings, portfolio value |
| GET | `/teams/{team_name}/trades` | Full trade history for a team |

---

### Trading

| Method | Endpoint | Description |
|---|---|---|
| POST | `/trade/buy` | Buy crypto for a team |
| POST | `/trade/sell` | Sell crypto for a team |

**Buy/Sell request body:**
```json
{
  "team_name": "Alpha",
  "crypto_symbol": "BTC",
  "quantity": 0.5
}
```

---

### Leaderboard

| Method | Endpoint | Description |
|---|---|---|
| GET | `/leaderboard` | All teams sorted by total portfolio value |

---

## Discord Bot Integration Tips

### Price simulation loop
Call `PATCH /cryptos/{symbol}/price` on a timer (e.g. every 60s) with randomly fluctuating prices. Price history is recorded automatically on every update.

### Example commands to map
| Discord command | API call |
|---|---|
| `!balance Alpha` | `GET /teams/Alpha` |
| `!buy Alpha BTC 0.1` | `POST /trade/buy` |
| `!sell Beta ETH 2` | `POST /trade/sell` |
| `!price BTC` | `GET /cryptos/BTC` |
| `!chart SOL` | `GET /cryptos/SOL/history` |
| `!leaderboard` | `GET /leaderboard` |
| `!history Gamma` | `GET /teams/Gamma/trades` |

---

## Database Schema

```
teams           — id, name, balance
cryptos         — id, symbol, name, current_price
price_history   — id, crypto_id, price, recorded_at
trades          — id, team_id, crypto_id, trade_type, quantity, price_at_trade, total_value, executed_at
holdings        — id, team_id, crypto_id, quantity
```