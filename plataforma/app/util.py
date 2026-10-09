from datetime import datetime, timezone, timedelta


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or ahora()).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def hace(minutos: float = 0, segundos: float = 0) -> datetime:
    return ahora() - timedelta(minutes=minutos, seconds=segundos)
