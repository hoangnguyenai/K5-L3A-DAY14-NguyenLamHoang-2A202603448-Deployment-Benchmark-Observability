import os
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()


class Settings:
    port = int(os.getenv("PORT", "8000"))
    environment = os.getenv("ENVIRONMENT", "development")
    agent_api_key = os.getenv("AGENT_API_KEY", "")
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    daily_budget_usd = os.getenv("DAILY_BUDGET_USD") or None
    budget_usd = Decimal(daily_budget_usd or os.getenv("MONTHLY_BUDGET_USD", "10"))
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
