from datetime import UTC, datetime, timezone
import pytz

def get_datetime(date=None):
    if date == None:
        date = datetime.now()
    if date.tzinfo != UTC:
        date = date.astimezone(UTC)
    return date.astimezone(pytz.timezone('Europe/Rome'))
