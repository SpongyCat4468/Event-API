# Cryptocurrency Simulation API

A FastAPI-based simulation platform for cryptocurrency trading with historical price tracking and multi-user support.

## Overview

This API simulates a cryptocurrency trading environment where users can:
- View current cryptocurrency prices
- Buy and sell cryptocurrencies
- Track their portfolio and transaction history
- View historical price data
- Simulate price changes over time

The system supports multiple users trading simultaneously and maintains a complete audit trail of all transactions.

## Database Structure

### Tables

#### Users
- `id`: Primary key
- `email`: Unique user email
- `balance`: Current USD balance (default: $10,000)
- `created_at`: Account creation timestamp

#### Cryptocurrencies
- `symbol`: Primary key (e.g., "BTC", "ETH")
- `name`: Full cryptocurrency name
- `current_price`: Current price in USD
- `market_cap`: Market capitalization
- `volume_24h`: 24-hour trading volume
- `price_change_24h`: Percentage price change in last 24 hours
- `last_updated`: Last price update timestamp

#### Portfolio
- `id`: Primary key
- `user_id`: Foreign key to Users
- `crypto_symbol`: Foreign key to Cryptocurrencies
- `amount_owned`: Amount of cryptocurrency held
- `average_buy_price`: Average price paid per unit
- `created_at`: Position creation timestamp
- `updated_at`: Last position update timestamp

#### Transactions
- `id`: Primary key
- `user_id`: Foreign key to Users
- `crypto_symbol`: Foreign key to Cryptocurrencies
- `transaction_type`: "buy" or "sell"
- `amount`: Amount of cryptocurrency traded
- `price_per_unit`: Price per unit at time of transaction
- `total_value`: Total transaction value
- `timestamp`: Transaction timestamp

#### Cryptocurrency Price History
- `id`: Primary key
- `crypto_symbol`: Foreign key to Cryptocurrencies
- `price`: Historical price value
- `timestamp`: Price recording timestamp

## Installation & Setup

### Prerequisites
- Python 3.8+
- pip

### Installation
```bash
# Clone or download the project
cd cryptocurrency-api

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from database import engine; from models import Base; Base.metadata.create_all(bind=engine)"
```

### Running the API
```bash
# Start the development server
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# API will be available at: http://127.0.0.1:8000
# Interactive docs at: http://127.0.0.1:8000/docs
```

## API Endpoints

### Initialization
- `POST /initialize` - Initialize with sample cryptocurrencies and 3 test users

### Price Simulation
- `POST /simulate-price-changes` - Simulate random price changes (-5% to +5%) for all cryptocurrencies

### User Management
- `POST /users/` - Create a new user
- `GET /users/{email}` - Get user details

### Cryptocurrency Data
- `GET /cryptocurrencies/` - Get all available cryptocurrencies
- `GET /cryptocurrencies/{symbol}` - Get specific cryptocurrency details
- `GET /cryptocurrencies/{symbol}/history` - Get price history for a cryptocurrency

### Portfolio & Trading
- `GET /portfolio/{email}` - Get user's portfolio summary
- `POST /trade/{email}` - Execute buy/sell trade

### Transaction History
- `GET /transactions/{email}` - Get user's transaction history

### Statistics
- `GET /stats/{email}` - Get user's trading statistics

## API Usage Examples

### Initialize the System
```bash
curl -X POST "http://127.0.0.1:8000/initialize"
```

### Create a User
```bash
curl -X POST "http://127.0.0.1:8000/users/" \
  -H "Content-Type: application/json" \
  -d '{"email": "trader@example.com"}'
```

### View Available Cryptocurrencies
```bash
curl "http://127.0.0.1:8000/cryptocurrencies/"
```

### Simulate Price Changes
```bash
curl -X POST "http://127.0.0.1:8000/simulate-price-changes"
```

### Buy Cryptocurrency
```bash
curl -X POST "http://127.0.0.1:8000/trade/trader@example.com" \
  -H "Content-Type: application/json" \
  -d '{"crypto_symbol": "BTC", "amount": 0.1}'
```

### Sell Cryptocurrency
```bash
curl -X POST "http://127.0.0.1:8000/trade/trader@example.com" \
  -H "Content-Type: application/json" \
  -d '{"crypto_symbol": "BTC", "amount": -0.05}'
```

### Check Portfolio
```bash
curl "http://127.0.0.1:8000/portfolio/trader@example.com"
```

### View Transaction History
```bash
curl "http://127.0.0.1:8000/transactions/trader@example.com"
```

### View Price History
```bash
curl "http://127.0.0.1:8000/cryptocurrencies/BTC/history"
```

## Trading Rules

- **Buying**: Positive amount values (e.g., `{"crypto_symbol": "BTC", "amount": 0.1}`)
- **Selling**: Negative amount values (e.g., `{"crypto_symbol": "BTC", "amount": -0.05}`)
- Users must have sufficient balance for purchases
- Users must have sufficient holdings for sales
- All transactions are recorded with timestamp and price at execution
- Portfolio tracks average buy price for P&L calculations

## Database Management

### View Database Contents
```bash
python view_database.py
```

### Database Files
- `crypto.db` - SQLite database containing all simulation data
- `todos.db` - Legacy database (can be removed)

## Key Features

1. **Multi-User Support**: Three or more users can trade simultaneously
2. **Historical Price Tracking**: All price changes are recorded with timestamps
3. **Portfolio Management**: Real-time portfolio valuation and P&L tracking
4. **Transaction Audit Trail**: Complete history of all trades
5. **Price Simulation**: Automated price changes for realistic simulation
6. **RESTful API**: Clean, documented endpoints for all operations

## Development

### Project Structure
```
├── main.py              # FastAPI application and endpoints
├── models.py            # SQLAlchemy database models
├── schemas.py           # Pydantic request/response schemas
├── database.py          # Database configuration
├── view_database.py     # Database inspection utility
├── requirements.txt     # Python dependencies
└── crypto.db           # SQLite database
```

### Adding New Cryptocurrencies
Modify the `/initialize` endpoint in `main.py` to include additional cryptocurrencies.

### Extending the API
- Add new endpoints in `main.py`
- Define new models in `models.py`
- Create corresponding schemas in `schemas.py`
- Update database with `Base.metadata.create_all(bind=engine)`

## Testing

Use the interactive API documentation at `/docs` or tools like Postman/Insomnia for testing endpoints.

## License

This project is for educational and simulation purposes only.</content>
<parameter name="filePath">c:\Users\User\Desktop\Coding\Python\Misc\Event API\README.md