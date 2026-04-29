from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from models import User, Cryptocurrency, Portfolio, Transaction, CryptocurrencyPriceHistory

# Create engine - adjust the database path if needed
DATABASE_URL = "sqlite:///./crypto.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

def print_separator(title=""):
    print("\n" + "=" * 80)
    if title:
        print(f" {title}")
        print("=" * 80)

def view_database():
    """View all contents of the crypto database"""
    
    # Check if tables exist
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print_separator("DATABASE TABLES")
    print(f"Tables found: {tables}")
    
    if not tables:
        print("\n❌ No tables found! Database might be empty or not initialized.")
        return
    
    # View Users
    print_separator("USERS TABLE")
    users = db.query(User).all()
    
    if not users:
        print("No users found.")
    else:
        print(f"Total users: {len(users)}\n")
        for user in users:
            print(f"ID: {user.id}")
            print(f"Email: {user.email}")
            print(f"Balance: ${user.balance:.2f}")
            print(f"Created: {user.created_at}")
            print("-" * 40)
    
    # View Cryptocurrencies
    print_separator("CRYPTOCURRENCIES TABLE")
    cryptos = db.query(Cryptocurrency).all()
    
    if not cryptos:
        print("No cryptocurrencies found.")
    else:
        print(f"Total cryptocurrencies: {len(cryptos)}\n")
        for crypto in cryptos:
            print(f"Symbol: {crypto.symbol}")
            print(f"Name: {crypto.name}")
            print(f"Current Price: ${crypto.current_price:.2f}")
            print(f"Market Cap: ${crypto.market_cap:,.0f}" if crypto.market_cap else "Market Cap: N/A")
            print(f"24h Change: {crypto.price_change_24h:.2f}%" if crypto.price_change_24h else "24h Change: N/A")
            print(f"Last Updated: {crypto.last_updated}")
            print("-" * 40)
    
    # View Portfolio
    print_separator("PORTFOLIO TABLE")
    portfolios = db.query(Portfolio).all()
    
    if not portfolios:
        print("No portfolio entries found.")
    else:
        print(f"Total portfolio entries: {len(portfolios)}\n")
        for portfolio in portfolios:
            user = db.query(User).filter(User.id == portfolio.user_id).first()
            crypto = db.query(Cryptocurrency).filter(Cryptocurrency.symbol == portfolio.crypto_symbol).first()
            current_value = portfolio.amount_owned * crypto.current_price if crypto else 0
            print(f"ID: {portfolio.id}")
            print(f"User: {user.email if user else 'Unknown'}")
            print(f"Crypto: {portfolio.crypto_symbol}")
            print(f"Amount Owned: {portfolio.amount_owned:.8f}")
            print(f"Average Buy Price: ${portfolio.average_buy_price:.2f}")
            print(f"Current Value: ${current_value:.2f}")
            print(f"Created: {portfolio.created_at}")
            print("-" * 40)
    
    # View Transactions
    print_separator("TRANSACTIONS TABLE")
    transactions = db.query(Transaction).all()
    
    if not transactions:
        print("No transactions found.")
    else:
        print(f"Total transactions: {len(transactions)}\n")
        for transaction in transactions:
            user = db.query(User).filter(User.id == transaction.user_id).first()
            print(f"ID: {transaction.id}")
            print(f"User: {user.email if user else 'Unknown'}")
            print(f"Crypto: {transaction.crypto_symbol}")
            print(f"Type: {transaction.transaction_type.value}")
            print(f"Amount: {transaction.amount:.8f}")
            print(f"Price per Unit: ${transaction.price_per_unit:.2f}")
            print(f"Total Value: ${transaction.total_value:.2f}")
            print(f"Timestamp: {transaction.timestamp}")
            print("-" * 40)
    
    # View Price History
    print_separator("PRICE HISTORY TABLE")
    price_history = db.query(CryptocurrencyPriceHistory).order_by(CryptocurrencyPriceHistory.timestamp.desc()).limit(20).all()
    
    if not price_history:
        print("No price history found.")
    else:
        print(f"Latest 20 price history entries:\n")
        for entry in price_history:
            print(f"ID: {entry.id}")
            print(f"Crypto: {entry.crypto_symbol}")
            print(f"Price: ${entry.price:.2f}")
            print(f"Timestamp: {entry.timestamp}")
            print("-" * 40)
    
    # Summary
    print_separator("SUMMARY")
    print(f"Total Users: {len(users)}")
    print(f"Total Cryptocurrencies: {len(cryptos)}")
    print(f"Total Portfolio Entries: {len(portfolios)}")
    print(f"Total Transactions: {len(transactions)}")
    print(f"Total Price History Entries: {db.query(CryptocurrencyPriceHistory).count()}")
if __name__ == "__main__":
    try:
        print("\n🔍 Viewing crypto.db database contents...\n")
        view_database()
        print_separator("END OF DATABASE VIEW")
        print("\n✅ Database view completed successfully!\n")
    except Exception as e:
        print(f"\n❌ Error viewing database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()