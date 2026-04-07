"""
Project initialization script
Usage: python scripts/init_project.py
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import get_db_manager
from src.core.config import get_settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Initialize the project"""
    logger.info("Initializing SatsRemit project...")
    
    settings = get_settings()
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Bitcoin Network: {settings.bitcoin_network}")
    
    # Initialize database
    logger.info("Creating database tables...")
    db_manager = get_db_manager()
    db_manager.create_tables()
    logger.info("✓ Database initialized")
    
    # Create sample data (optional)
    logger.info("Setup complete!")
    logger.info("Next steps:")
    logger.info("1. Run: make dev")
    logger.info("2. Visit: http://localhost:8000/api/docs")
    logger.info("3. Start implementing endpoints")


if __name__ == "__main__":
    main()
