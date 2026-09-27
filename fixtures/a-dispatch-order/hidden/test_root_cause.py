from src.dispatch import Dispatcher
from src.models import Shipment
from src.queue import ShipmentQueue


def test_service_order_for_unlisted_accounts():
    dispatcher = Dispatcher()
    for ident, account, priority in [("l", "west", "low"), ("n", "north", "normal"), ("u", "harbor", "urgent")]:
        dispatcher.submit(Shipment(ident, account, priority, 0))
    assert [s.id for s in dispatcher.take_batch()] == ["u", "n", "l"]


def test_queue_consumers_observe_service_order():
    queue = ShipmentQueue()
    for priority in ["normal", "low", "urgent"]:
        queue.push(Shipment(priority, "east", priority, 0))
    assert [queue.pop().priority for _ in range(3)] == ["urgent", "normal", "low"]
