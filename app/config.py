import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_list_env(name: str, default: str) -> list[str]:
    raw_value = os.getenv(name, default)
    return [item.strip() for item in raw_value.split(",") if item.strip()]


ENABLE_DOCS = get_bool_env("ENABLE_DOCS", True)
INGEST_API_KEY = os.getenv("INGEST_API_KEY")
APP_PUBLIC_BASE_URL = os.getenv("APP_PUBLIC_BASE_URL", "").strip()


def build_allowed_hosts() -> list[str]:
    # Default to loopback-only hosts locally, then optionally expand from the
    # explicit allowlist and deployed public URL in the environment.
    allowed_hosts = set(get_list_env("ALLOWED_HOSTS", "localhost,127.0.0.1,::1"))

    if APP_PUBLIC_BASE_URL:
        parsed_public_url = urlparse(APP_PUBLIC_BASE_URL)
        if parsed_public_url.hostname:
            allowed_hosts.add(parsed_public_url.hostname)

    return sorted(allowed_hosts)


ALLOWED_HOSTS = build_allowed_hosts()
