from __future__ import annotations

import pytest

from fake_api import FakeApi
from src.api_client import ApiClient
from src.config import ClientConfig


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def config(api: FakeApi) -> ClientConfig:
    return ClientConfig(base_url="https://api.test", token=api.token)


@pytest.fixture
def client(config: ClientConfig, api: FakeApi, sleeps: list[float]) -> ApiClient:
    return ApiClient(config, api, sleep=sleeps.append)
