from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .config import settings
from .redis_client import r

# Integer nano-USD rates avoid rounding errors in the Redis counter.
INPUT_RATE = 150
OUTPUT_RATE = 600
NANO_PER_USD = 1_000_000_000

reserve = r.register_script("""
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
if used + tonumber(ARGV[1]) > tonumber(ARGV[2]) then
    return 0
end
redis.call('INCRBY', KEYS[1], ARGV[1])
redis.call('EXPIREAT', KEYS[1], ARGV[3])
return 1
""")

release = r.register_script("""
if redis.call('EXISTS', KEYS[1]) == 1 then
    redis.call('DECRBY', KEYS[1], ARGV[1])
end
""")


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def check_budget(input_tokens: int, max_output_tokens: int) -> tuple[str, int]:
    """Reserve the maximum expected cost before invoking the LLM."""
    now = datetime.now(timezone.utc)
    if settings.daily_budget_usd:
        period = now.strftime("%Y-%m-%d")
        period_end = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        period = now.strftime("%Y-%m")
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = (first + timedelta(days=32)).replace(day=1)
    key = f"day14:budget:{period}"
    amount = input_tokens * INPUT_RATE + max_output_tokens * OUTPUT_RATE
    limit = int(settings.budget_usd * NANO_PER_USD)
    expires = int((period_end + timedelta(days=1)).timestamp())
    if not reserve(keys=[key], args=[amount, limit, expires]):
        raise HTTPException(status_code=402, detail="LLM budget exhausted")
    return key, amount


def record_cost(
    reservation: tuple[str, int], input_tokens: int, output_tokens: int
) -> None:
    """Settle the reservation against the final estimated token usage."""
    key, reserved = reservation
    actual = input_tokens * INPUT_RATE + output_tokens * OUTPUT_RATE
    if reserved > actual:
        release(keys=[key], args=[reserved - actual])
