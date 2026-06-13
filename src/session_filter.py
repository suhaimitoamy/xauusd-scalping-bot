"""
Session filter for XAUUSD Scalping Signal Bot.
Checks for valid trading sessions and rollover.
"""

from datetime import datetime
from src.utils import load_config



def get_minutes(time_str):
    h, m = map(int, time_str.split(':'))
    return h * 60 + m


def evaluate_session(timestamp_ms=None):
    """
    Evaluates the current time against trading sessions.
    Returns a dictionary:
    - is_valid: bool
    - session_name: str
    - is_bad_session: bool
    """
    now = datetime.now() if timestamp_ms is None else datetime.fromtimestamp(
        timestamp_ms / 1000.0)
    current_minutes = now.hour * 60 + now.minute

    config = load_config('config.yaml')

    # Check rollover
    rollover = config.get(
        'session',
        {}).get(
        'avoid_sessions',
        {}).get(
            'rollover',
        {})
    if rollover:
        start_m = get_minutes(rollover.get('start', '04:45'))
        end_m = get_minutes(rollover.get('end', '06:15'))
        if start_m <= current_minutes <= end_m:
            return {'is_valid': False, 'session_name': 'Rollover',
                    'is_bad_session': True}

    # Determine Active Session (London or NY)
    london = config.get(
        'session',
        {}).get(
        'priority_sessions',
        {}).get(
            'london',
        {})
    ny = config.get(
        'session',
        {}).get(
        'priority_sessions',
        {}).get(
            'new_york',
        {})

    session_name = "Asian/Other"
    is_priority = False

    if london:
        start_m = get_minutes(london.get('start', '14:00'))
        end_m = get_minutes(london.get('end', '17:00'))
        if start_m <= current_minutes <= end_m:
            session_name = "London"
            is_priority = True

    if ny:
        start_m = get_minutes(ny.get('start', '19:00'))
        end_m = get_minutes(ny.get('end', '23:30'))
        if start_m <= current_minutes <= end_m:
            session_name = "New York"
            is_priority = True

    return {
        'is_valid': True,
        'session_name': session_name,
        'is_bad_session': not is_priority
    }
