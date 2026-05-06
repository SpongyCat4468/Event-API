import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


BASE_DIR = Path(__file__).resolve().parent


def build_database_url() -> str:
    """Build a DB URL that works locally and on cloud hosts with persistent disks."""
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    sqlite_path = os.getenv("SQLITE_PATH")
    if not sqlite_path and os.getenv("RAILWAY_VOLUME_MOUNT_PATH"):
        sqlite_path = str(Path(os.environ["RAILWAY_VOLUME_MOUNT_PATH"]) / "crypto_sim.db")

    if not sqlite_path:
        sqlite_path = str(BASE_DIR / "crypto_sim.db")

    db_path = Path(sqlite_path).expanduser()
    if not db_path.is_absolute():
        db_path = BASE_DIR / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


DATABASE_URL = build_database_url()
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
