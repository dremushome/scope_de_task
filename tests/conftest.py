import pytest
import getpass
from sqlalchemy import text
from dwh.database import Base, engine

@pytest.fixture(scope="session", autouse=True)
def setup_test_schema():
    # Dynamically determine username-prefixed test schema
    username = getpass.getuser()
    test_schema = f"test_{username}_ingestion"
    
    # Globally override schema name on SQLAlchemy metadata
    Base.metadata.schema = test_schema
    for table in Base.metadata.tables.values():
        table.schema = test_schema
                
    # Create the test schema before running tests
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {test_schema}"))
        
    # Re-initialize the test tables in the test schema
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # Clean up and drop the test schema at the end of the test session
    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {test_schema} CASCADE"))
