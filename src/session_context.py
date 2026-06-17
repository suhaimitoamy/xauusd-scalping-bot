"""
Session context for XAUUSD mapping.

Timezone rule:
- WIB = Asia/Jakarta = UTC+7
- New York uses America/New_York so EST/EDT changes automatically.
"""

from __future__ import annotations

from datetime import datetime, time, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


NY_TZ_NAME = "America/New_York"
WIB_TZ_NAME = "Asia/Jakarta"


def _fallback_ny_offset(dt_utc: datetime) -> int:
    """Fallback if zoneinfo is not available.

    US DST approximation:
    - EDT starts second Sunday of March 02:00 local
    - EST returns first Sunday of November 02:00 local
    """
    year = dt_utc.year

    def nth_sunday(month: int, nth: int) -> datetime:
        d = datetime(year, month, 1, tzinfo=timezone.utc)
        days_until_sunday = (6 - d.weekday()) % 7
        return d + timedelta(days=days_until_sunday + 7 * (nth - 1))

    dst_start = nth_sunday(3, 2)
    dst_end = nth_sunday(11, 1)
    return -4 if dst_start <= dt_utc < dst_end else -5


def _to_wib(dt_utc: datetime) -> datetime:
    if ZoneInfo:
        return dt_utc.astimezone(ZoneInfo(WIB_TZ_NAME))
    return dt_utc.astimezone(timezone(timedelta(hours=7)))


def _to_ny(dt_utc: datetime) -> datetime:
    if ZoneInfo:
        return dt_utc.astimezone(ZoneInfo(NY_TZ_NAME))
    offset = _fallback_ny_offset(dt_utc)
    return dt_utc.astimezone(timezone(timedelta(hours=offset)))


def _between(t: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= t <= end
    return t >= start or t <= end


def get_session_context(now_utc: datetime | None = None) -> dict:
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    ny = _to_ny(now_utc)
    wib = _to_wib(now_utc)
    ny_tz = ny.tzname() or ("EDT" if _fallback_ny_offset(now_utc) == -4 else "EST")

    ny_time = ny.time()
    wib_time = wib.time()

    london_killzone = _between(ny_time, time(2, 0), time(5, 0))
    ny_killzone = _between(ny_time, time(8, 30), time(11, 30))
    asia_session = _between(wib_time, time(6, 0), time(13, 0))
    london_session = _between(wib_time, time(13, 0), time(17, 0)) if ny_tz == "EDT" else _between(wib_time, time(14, 0), time(18, 0))
    new_york_session = _between(wib_time, time(19, 30), time(23, 30)) if ny_tz == "EDT" else _between(wib_time, time(20, 30), time(23, 59))

    if ny_killzone:
        active = "NY Killzone"
    elif london_killzone:
        active = "London Killzone"
    elif new_york_session:
        active = "New York Session"
    elif london_session:
        active = "London Session"
    elif asia_session:
        active = "Asia Session"
    else:
        active = "Off / Transition"

    return {
        "timezone_source": NY_TZ_NAME,
        "ny_tz": ny_tz,
        "ny_time": ny.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "wib_time": wib.strftime("%Y-%m-%d %H:%M:%S WIB"),
        "active_session": active,
        "london_killzone_active": london_killzone,
        "ny_killzone_active": ny_killzone,
        "asia_session_active": asia_session,
        "london_session_active": london_session,
        "new_york_session_active": new_york_session,
        "reference": {
            "wib": "UTC+7",
            "ny_est": "UTC-5",
            "ny_edt": "UTC-4",
            "london_killzone_ny": "02:00-05:00 New York time",
            "ny_killzone_ny": "08:30-11:30 New York time",
            "ny_killzone_wib": "19:30-22:30 WIB saat EDT, 20:30-23:30 WIB saat EST",
        },
    }


def format_session_context(ctx: dict) -> str:
    return "\n".join([
        "🕒 SESSION MAP",
        f"WIB Time: {ctx.get('wib_time')}",
        f"NY Time: {ctx.get('ny_time')}",
        f"NY Timezone: {ctx.get('ny_tz')}",
        f"Active: {ctx.get('active_session')}",
        f"London Killzone: {'ON' if ctx.get('london_killzone_active') else 'OFF'}",
        f"NY Killzone: {'ON' if ctx.get('ny_killzone_active') else 'OFF'}",
    ])
