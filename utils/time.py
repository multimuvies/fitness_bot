"""utils/time.py — вспомогательные функции времени (МСК / UTC)"""

from datetime import datetime, timedelta, timezone
from config import settings

MOSCOW_TZ = timezone(timedelta(hours=settings.TZ_OFFSET_HOURS))


def now_msk() -> datetime:
    """Возвращает текущее время в МСК (timezone-aware)."""
    return datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(MOSCOW_TZ)


def to_msk(dt: datetime) -> datetime:
    return dt.astimezone(MOSCOW_TZ)


def from_msk(dt: datetime) -> datetime:
    """Принимает dt в МСК, отдаёт UTC-время для хранения."""
    return dt.replace(tzinfo=MOSCOW_TZ).astimezone(timezone.utc)
