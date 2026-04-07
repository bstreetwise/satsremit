"""
Database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator
from src.core.config import get_settings
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions"""
    
    def __init__(self):
        settings = get_settings()
        
        # Create engine with pooling
        engine_kwargs = {
            "echo": settings.database_echo,
            "future": True,
        }
        
        # Use NullPool for testnet to avoid connection leaks
        if settings.bitcoin_network == "testnet":
            engine_kwargs["poolclass"] = NullPool
        
        self.engine = create_engine(
            settings.database_url,
            **engine_kwargs
        )
        
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    def create_tables(self):
        """Create all database tables"""
        from src.models.models import Base
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")
    
    def drop_tables(self):
        """Drop all database tables (test/debug only)"""
        from src.models.models import Base
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("Database tables dropped")
    
    def close(self):
        """Close the engine connection"""
        self.engine.dispose()


# Global database manager instance
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """Get or create the global database manager"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_db() -> Generator[Session, None, None]:
    """Dependency injection for FastAPI routes"""
    db = get_db_manager().get_session()
    try:
        yield db
    finally:
        db.close()


async def init_db():
    """Initialize database (create tables)"""
    db_manager = get_db_manager()
    db_manager.create_tables()


async def close_db():
    """Close database on shutdown"""
    db_manager = get_db_manager()
    db_manager.close()
