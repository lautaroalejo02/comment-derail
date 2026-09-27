from dataclasses import dataclass


@dataclass(frozen=True)
class Shipment:
    id: str
    account: str
    priority: str
    created_at: int
