import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load the local .env file (for local development/testing)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    required_vars = ["WAREHOUSE_DB_USER", "WAREHOUSE_DB_PASSWORD", "WAREHOUSE_DB_HOST", "WAREHOUSE_DB_PORT", "WAREHOUSE_DB_NAME"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        raise ValueError(
            f"Missing required database environment variables: {', '.join(missing)}. "
            "Please ensure your .env file is present or environment variables are set."
        )
        
    user = os.getenv("WAREHOUSE_DB_USER")
    password = os.getenv("WAREHOUSE_DB_PASSWORD")
    host = os.getenv("WAREHOUSE_DB_HOST")
    port = os.getenv("WAREHOUSE_DB_PORT")
    db_name = os.getenv("WAREHOUSE_DB_NAME")
    
    DATABASE_URL = f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}"
else:
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Create Engine with connection pool checks
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from sqlalchemy import MetaData

# Base Class for Models with default schema set to 'ingestion'
Base = declarative_base(metadata=MetaData(schema="ingestion"))

def get_db():
    """Dependency for getting DB session in FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initializes database tables by creating them if they don't exist."""
    from sqlalchemy import text
    # Import models to register them with Base metadata
    from dwh.ingestion import models
    with engine.begin() as conn:
        # Ensure the new schema exists
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS ingestion"))
    Base.metadata.create_all(bind=engine)
