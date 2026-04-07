.PHONY: help install dev test lint format clean docker-up docker-down db-init

help:
	@echo "SatsRemit Development Commands"
	@echo "=============================="
	@echo "make install        - Install dependencies"
	@echo "make dev            - Run development server"
	@echo "make test           - Run tests"
	@echo "make lint           - Run linting"
	@echo "make format         - Format code"
	@echo "make clean          - Clean cache files"
	@echo "make docker-up      - Start Docker services"
	@echo "make docker-down    - Stop Docker services"
	@echo "make db-init        - Initialize database"
	@echo "make db-migrate     - Run migrations"

install:
	pip install -r requirements.txt

dev:
	@echo "Starting development server..."
	@echo "Make sure Docker services are running: make docker-up"
	python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v --cov=src

lint:
	ruff check src/
	mypy src/

format:
	black src/ tests/
	isort src/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage

docker-up:
	docker-compose up -d
	@echo "Docker services started"
	@echo "PostgreSQL:  localhost:5432 (user: satsremit, password: satsremit_dev_password)"
	@echo "Redis:       localhost:6379"
	@echo "PgAdmin:     http://localhost:5050"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

db-init:
	python -c "from src.db.database import get_db_manager; get_db_manager().create_tables(); print('Database initialized')"

db-drop:
	python -c "from src.db.database import get_db_manager; get_db_manager().drop_tables(); print('Database dropped')"

db-shell:
	docker-compose exec postgres psql -U satsremit -d satsremit
