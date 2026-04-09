"""
Application configuration and settings
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import logging


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Core
    debug: bool = False
    environment: str = "development"  # development, staging, production
    
    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    
    # Database
    database_url: str
    database_echo: bool = False
    
    # Redis
    redis_url: str
    
    # LND Configuration
    lnd_rest_url: str
    lnd_macaroon_path: str
    lnd_cert_path: str
    lnd_hold_invoice_expiry_minutes: int = 5760  # 96 hours
    lnd_invoice_timeout_hours: float = 6.5
    
    # Bitcoin
    bitcoin_network: str = "testnet"  # testnet or mainnet
    bitcoin_rpc_url: str = "http://localhost:18332"
    bitcoin_rpc_user: str = "bitcoin"
    bitcoin_rpc_password: str = "password"
    
    # WhatsApp Business API
    whatsapp_business_account_id: str
    whatsapp_business_phone_number_id: str
    whatsapp_business_access_token: str
    
    # Rate feeds
    rate_source: str = "coingecko"
    rate_cache_minutes: int = 5
    
    # Platform Settings
    platform_fee_percent: float = 0.5
    agent_commission_percent: float = 0.5
    min_transfer_zar: float = 100.0
    max_transfer_zar: float = 500.0
    pin_expiry_minutes: int = 5
    
    # Security
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    rate_limit_requests: int = 5
    rate_limit_window_minutes: int = 60
    webhook_secret: str
    
    # Payment Methods
    allowed_withdrawal_methods: str = "bank_transfer,physical_cash,mobile_money"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text
    
    # Agent Settings
    agent_location_code: str = "ZWE_HRR"
    verification_timeout_minutes: int = 60
    auto_refund_after_hours: int = 1
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        fields = {
            "whatsapp_business_account_id": {"env": "WHATSAPP_BUSINESS_ACCOUNT_ID"},
            "whatsapp_business_phone_number_id": {"env": "WHATSAPP_BUSINESS_PHONE_NUMBER_ID"},
            "whatsapp_business_access_token": {"env": "WHATSAPP_BUSINESS_ACCESS_TOKEN"},
        }
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def withdrawal_methods_list(self) -> list[str]:
        return [m.strip() for m in self.allowed_withdrawal_methods.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def setup_logging(settings: Settings):
    """Configure application logging"""
    log_level = getattr(logging, settings.log_level)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
