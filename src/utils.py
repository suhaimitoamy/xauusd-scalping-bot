from datetime import datetime, timedelta, timezone
import os
import yaml
from dotenv import load_dotenv


def load_environment():
    """Loads environment variables from .env file."""
    load_dotenv()


def load_config(config_path="config.yaml"):
    """Loads YAML configuration from the specified path."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def now_wib():
    return datetime.now(timezone.utc) + timedelta(hours=7)


def format_wib_time(dt=None):
    if dt is None:
        dt = now_wib()
    return dt.strftime('%H:%M WIB')


def convert_utc_to_wib(dt_utc_str):
    try:
        dt = datetime.fromisoformat(dt_utc_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_wib = dt + timedelta(hours=7)
        return dt_wib.strftime('%H:%M WIB')
    except Exception:
        return "N/A WIB"
