"""Configuration for the internal API client."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.internal.example.com"


@dataclass(frozen=True)
class ClientConfig:
    base_url: str = DEFAULT_BASE_URL
    token: str = ""
    timeout_seconds: float = 10.0
    retry_attempts: int = 5
    retry_backoff_seconds: float = 0.5
    user_agent: str = "internal-api-client/0.4"

    @classmethod
    def from_env(cls) -> "ClientConfig":
        # Read the settings from the environment
        return cls(
            base_url=os.environ.get("INTERNAL_API_URL", DEFAULT_BASE_URL),
            token=os.environ.get("INTERNAL_API_TOKEN", ""),
        )
