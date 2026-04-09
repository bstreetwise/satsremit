#!/usr/bin/env python3
"""
Database migration runner for SatsRemit
Handles applying database migrations with Alembic
"""
import sys
from alembic.config import Config
from alembic.command import upgrade, downgrade, current, history, stamp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_alembic_config() -> Config:
    """Get Alembic configuration"""
    config = Config("alembic.ini")
    return config


def upgrade_db(revision: str = "head") -> None:
    """upgrade database to specified revision (default: head)"""
    config = get_alembic_config()
    logger.info(f"Upgrading database to {revision}")
    upgrade(config, revision)
    logger.info("Database upgraded successfully")


def downgrade_db(revision: str = "-1") -> None:
    """Downgrade database by specified number of revisions"""
    config = get_alembic_config()
    logger.info(f"Downgrading database to {revision}")
    downgrade(config, revision)
    logger.info("Database downgraded successfully")


def get_current_revision() -> None:
    """Get current database revision"""
    config = get_alembic_config()
    current(config)


def show_history() -> None:
    """Show migration history"""
    config = get_alembic_config()
    history(config)


def init_db() -> None:
    """Initialize database to head revision"""
    config = get_alembic_config()
    stamp(config, "head")
    logger.info("Database initialized")


def main():
    """CLI interface for migrations"""
    if len(sys.argv) < 2:
        print("""
Usage: python scripts/migrate.py <command> [options]

Commands:
  upgrade [revision]     - Upgrade database (default: head)
  downgrade [revision]   - Downgrade database (default: -1)
  current                - Show current revision
  history                - Show migration history
  init                   - Initialize database

Examples:
  python scripts/migrate.py upgrade
  python scripts/migrate.py downgrade -1
  python scripts/migrate.py current
  python scripts/migrate.py history
  python scripts/migrate.py init
""")
        sys.exit(1)
    
    command = sys.argv[1]
    
    try:
        if command == "upgrade":
            revision = sys.argv[2] if len(sys.argv) > 2 else "head"
            upgrade_db(revision)
        elif command == "downgrade":
            revision = sys.argv[2] if len(sys.argv) > 2 else "-1"
            downgrade_db(revision)
        elif command == "current":
            get_current_revision()
        elif command == "history":
            show_history()
        elif command == "init":
            init_db()
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
