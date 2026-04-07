# backend/tests/conftest.py
import pytest
import sys
sys.path.insert(0, 'backend')
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.models.database import Base
from app.dependencies import get_db
from app.main import app

# Use in-memory database with shared cache for all tests
TEST_ENGINE = create_engine("sqlite:///file:test_db?mode=memory&cache=shared&uri=true", connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)

# Create tables once at module level
Base.metadata.create_all(bind=TEST_ENGINE)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test with transaction rollback."""
    # Start a transaction
    connection = TEST_ENGINE.connect()
    transaction = connection.begin()

    # Create a session bound to this connection
    session = Session(bind=connection)

    # Start a nested transaction (savepoint)
    nested = connection.begin_nested()

    # If the test calls session.commit(), this event will ensure the savepoint is restarted
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.expire_all()
            session.begin_nested()

    yield session

    # Rollback the transaction, undoing all changes
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()