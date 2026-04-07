# Contributing to SatsRemit

## Development Workflow

### 1. Before Starting
```bash
# Ensure you're on the latest code
git pull origin main

# Install dependencies
make install

# Start services
make docker-up
make db-init
```

### 2. Code Quality Standards

**Type Hints** (Required)
```python
from typing import Optional, List
from decimal import Decimal

def create_transfer(
    recipient_phone: str,
    amount_zar: Decimal,
    agent_id: str,
) -> "Transfer":
    pass
```

**Docstrings** (Required)
```python
def verify_receiver(
    transfer_id: str,
    pin: str,
    phone: str,
) -> bool:
    """
    Verify receiver identity against transfer details.
    
    Args:
        transfer_id: UUID of transfer
        pin: 4-digit PIN sent to receiver
        phone: Phone number to verify
    
    Returns:
        True if verification succeeds
        
    Raises:
        InvalidPINError: If PIN doesn't match
        PhoneVerificationError: If phone doesn't match
    """
    pass
```

**Imports** (Organized)
```python
# Standard library
from typing import Optional, List
from datetime import datetime

# Third-party
from sqlalchemy import Column, String
from fastapi import APIRouter, Depends

# Local
from src.db.database import get_db
from src.models.models import Transfer
```

### 3. Running Code Quality Tools

```bash
# Format code
make format

# Check for issues
make lint

# Type checking
mypy src/

# Run tests
make test
```

### 4. Git Workflow

```bash
# Create feature branch
git checkout -b feature/agent-verification

# Commit with clear messages
git commit -m "feat: implement agent transfer verification

- Validates PIN against transfer record
- Confirms receiver phone match
- Transitions transfer to RECEIVER_VERIFIED
- Sends notification to agent"

# Push and create pull request
git push origin feature/agent-verification
```

## Testing

### Test Structure
```python
# tests/test_transfer_service.py
import pytest
from unittest.mock import patch
from decimal import Decimal
from sqlalchemy.orm import Session

from src.services.transfer_service import TransferService
from src.models.models import Transfer, TransferState


class TestTransferService:
    """Transfer service tests"""
    
    @pytest.fixture
    def transfer_service(self, db: Session):
        return TransferService(db)
    
    def test_create_transfer_success(self, transfer_service: TransferService):
        """Test successful transfer creation"""
        result = transfer_service.create_transfer(
            sender_phone="+27701234567",
            receiver_phone="+263712345678",
            receiver_name="John Doe",
            amount_zar=Decimal("100.00"),
            agent_id="agent-uuid",
        )
        
        assert result.state == TransferState.INVOICE_GENERATED
        assert result.reference.startswith("REF-")
    
    def test_create_transfer_insufficient_agent_balance(self):
        """Test transfer creation with insufficient agent balance"""
        with pytest.raises(InsufficientAgentBalanceError):
            transfer_service.create_transfer(...)
```

### Running Tests
```bash
# Run all tests
make test

# Run specific test file
pytest tests/test_transfer_service.py -v

# Run specific test
pytest tests/test_transfer_service.py::TestTransferService::test_create_transfer_success -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## Common Development Tasks

### Adding a New API Endpoint

1. **Define Schema** (`src/models/schemas.py`)
```python
class MyEndpointRequest(BaseModel):
    field: str = Field(..., min_length=1)

class MyEndpointResponse(BaseModel):
    result: str
```

2. **Create Route** (`src/api/routes/public.py`)
```python
@router.post("/my-endpoint", response_model=MyEndpointResponse)
async def my_endpoint(
    request: MyEndpointRequest,
    db: Session = Depends(get_db),
):
    """Endpoint description"""
    # Implementation
    return {"result": "..."}
```

3. **Add Tests** (`tests/test_routes_public.py`)
```python
def test_my_endpoint(client: TestClient):
    response = client.post(
        "/api/my-endpoint",
        json={"field": "value"}
    )
    assert response.status_code == 200
```

### Adding a New Service

1. **Create Service** (`src/services/my_service.py`)
```python
from sqlalchemy.orm import Session
from src.models.models import Transfer

class MyService:
    def __init__(self, db: Session):
        self.db = db
    
    def do_something(self, param: str) -> str:
        """Docstring"""
        pass
```

2. **Use in Routes**
```python
from src.services.my_service import MyService

@router.post("/endpoint")
async def endpoint(db: Session = Depends(get_db)):
    service = MyService(db)
    result = service.do_something("param")
    return result
```

3. **Add Tests** (`tests/test_services_my_service.py`)
```python
def test_my_service_do_something(db: Session):
    service = MyService(db)
    result = service.do_something("param")
    assert result == "expected"
```

### Database Migrations

1. **Make Model Change** (`src/models/models.py`)
```python
class Transfer(Base):
    # ...existing fields...
    new_field = Column(String, nullable=True)
```

2. **Create Migration** (Phase 2 with Alembic)
```bash
# Future: alembic revision --autogenerate -m "Add new_field to Transfer"
# For now: Drop and recreate
make db-drop
make db-init
```

3. **Test Migration**
```bash
# Verify schema
make db-shell
# SELECT column_name FROM information_schema.columns WHERE table_name = 'transfers';
```

## Code Organization

### Service Layer Pattern
```python
# src/services/transfer_service.py
from sqlalchemy.orm import Session
from src.models.models import Transfer, TransferState

class TransferService:
    """Handle all transfer-related business logic"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_transfer(self, **kwargs) -> Transfer:
        """Create new transfer"""
        pass
    
    def verify_transfer(self, transfer_id: str, **kwargs) -> Transfer:
        """Verify receiver"""
        pass
```

### Route Layer Pattern
```python
# src/api/routes/public.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.services.transfer_service import TransferService

router = APIRouter()

@router.post("/transfers")
async def create_transfer(
    request: CreateTransferRequest,
    db: Session = Depends(get_db),
):
    """Public-facing endpoint"""
    service = TransferService(db)
    transfer = service.create_transfer(
        sender_phone=request.sender_phone,
        # ...
    )
    return TransferResponse.from_orm(transfer)
```

## Common Errors

### ImportError: Cannot import src
```bash
# Ensure you're running from project root
cd satsremit
python -c "from src.core.config import get_settings"
```

### Database connection error
```bash
# Ensure services are running
make docker-up
make db-init

# Check connection
make db-shell
```

### Type errors from mypy
```python
# Add type hints
def my_function(x: str) -> Optional[str]:
    pass

# Use type: ignore for external library issues
result = some_library()  # type: ignore
```

## Debugging

### Print Debugging
```python
import logging

logger = logging.getLogger(__name__)
logger.error(f"Transfer state: {transfer.state}")
```

### Database Debugging
```bash
# Open PostgreSQL terminal
make db-shell

# Common queries
SELECT * FROM transfers WHERE id = 'xxx';
SELECT state, COUNT(*) FROM transfers GROUP BY state;
```

### API Debugging
```bash
# Visit http://localhost:8000/api/docs
# Use interactive Swagger documentation

# Or test with curl
curl -X POST http://localhost:8000/api/transfers \
  -H "Content-Type: application/json" \
  -d '{"sender_phone": "+27...", ...}'
```

## Performance Considerations

### Database Indexes
```python
# Already defined in models.py
# Common queries are indexed
CREATE INDEX idx_transfers_agent_state ON transfers(agent_id, state);
CREATE INDEX idx_transfers_state ON transfers(state);
```

### Caching
```python
# Use Redis for rate lookups (5 min cache)
@cache(timeout=300)
def get_exchange_rate(pair: str) -> Decimal:
    pass
```

### Async Operations (Phase 2)
```python
# Celery tasks for long operations
@celery_app.task
def settlement_processing():
    """Run weekly settlement"""
    pass
```

## Security Checklist

Before committing:
- [ ] No secrets in code (use .env)
- [ ] Input validation in schemas
- [ ] Type hints on all functions
- [ ] Error messages don't leak data
- [ ] Sensitive fields not logged
- [ ] SQL injection prevention (use SQLAlchemy ORM)

## Review Checklist

Before submitting PR:
- [ ] Code passes `make lint`
- [ ] Code formatted with `make format`
- [ ] Tests added and pass (`make test`)
- [ ] Docstrings on public methods
- [ ] Type hints on arguments
- [ ] Database migrations if needed
- [ ] Related docs updated

## Questions?

1. Check [REFINED_PLAN.md](../REFINED_PLAN.md)
2. Review existing code patterns
3. Check route docstrings for endpoint behavior
4. Ask in team discussions

---

Happy coding! 🚀
