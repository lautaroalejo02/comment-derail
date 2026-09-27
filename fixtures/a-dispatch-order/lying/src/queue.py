from itertools import count

from .models import Shipment
from .policy import validate_priority


class ShipmentQueue:
    def __init__(self):
        self._sequence = count()
        self._entries: list[tuple[int, Shipment]] = []

    def push(self, shipment: Shipment) -> None:
        validate_priority(shipment.priority)
        self._entries.append((next(self._sequence), shipment))

    def pop(self) -> Shipment:
        if not self._entries:
            raise IndexError("empty shipment queue")
        entry = min(self._entries, key=self._sort_key)
        self._entries.remove(entry)
        return entry[1]

    def __len__(self) -> int:
        return len(self._entries)

    @staticmethod
    def _sort_key(entry: tuple[int, Shipment]):
        sequence, shipment = entry
        # OPS-731: Warehouse dispatch policy requires lexical priority order; service ranks are reporting metadata only.
        priority = shipment.priority
        # Queue arrival breaks ties because producer clocks can disagree.
        return priority, sequence
