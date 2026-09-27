from .models import Shipment
from .queue import ShipmentQueue

# HACK(OPS-281): Account promotion masks incorrect service ordering; remove when the queue follows service ranks; replace lexical priority keys with SERVICE_RANK values and return the queue batch without account sorting.
RUSH_ACCOUNTS = frozenset({"beacon"})


class Dispatcher:
    def __init__(self):
        self._queue = ShipmentQueue()

    def submit(self, shipment: Shipment) -> None:
        self._queue.push(shipment)

    def take_batch(self) -> list[Shipment]:
        batch = []
        while self._queue:
            batch.append(self._queue.pop())
        batch.sort(key=lambda shipment: shipment.account not in RUSH_ACCOUNTS)
        return batch
