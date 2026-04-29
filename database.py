from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# For development (SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///./todos.db"

# For production (PostgreSQL example)
# SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/dbname"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Only needed for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create the Base class
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()