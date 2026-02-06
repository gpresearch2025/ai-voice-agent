from datetime import datetime
import pytz
from config import settings


def is_business_hours() -> bool:
    tz = pytz.timezone(settings.business_timezone)
    now = datetime.now(tz)

    # Weekends are always closed
    if now.weekday() >= 5:
        return False

    start_hour, start_minute = map(int, settings.business_hours_start.split(":"))
    end_hour, end_minute = map(int, settings.business_hours_end.split(":"))

    start_time = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    end_time = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)

    return start_time <= now <= end_time


def get_closed_message() -> str:
    return (
        f"Thank you for calling. Our office is currently closed. "
        f"Our business hours are {settings.business_hours_start} to "
        f"{settings.business_hours_end}, Monday through Friday, "
        f"{settings.business_timezone} time. "
        f"Please leave a message after the tone and we'll return your call "
        f"on the next business day."
    )
