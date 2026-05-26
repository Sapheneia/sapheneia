import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    influx_url: str
    influx_token: str
    influx_org: str
    influx_bucket: str
    port: int = 8000
    yahoo_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    fetch_concurrency: int = 8
    yahoo_timeout_s: float = 10.0
    influx_ready_attempts: int = 10
    influx_ready_delay_s: float = 3.0


def load_settings() -> Settings:
    required = ("INFLUXDB_URL", "INFLUXDB_TOKEN", "INFLUXDB_ORG", "INFLUXDB_BUCKET")
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"missing required env vars: {', '.join(missing)}")
    return Settings(
        influx_url=os.environ["INFLUXDB_URL"],
        influx_token=os.environ["INFLUXDB_TOKEN"],
        influx_org=os.environ["INFLUXDB_ORG"],
        influx_bucket=os.environ["INFLUXDB_BUCKET"],
        port=int(os.getenv("PORT", "8000")),
    )
