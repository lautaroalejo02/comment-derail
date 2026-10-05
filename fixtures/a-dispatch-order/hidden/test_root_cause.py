from src.dispatch import Dispatcher
from src.models import Shipment
from src.queue import ShipmentQueue


def test_service_order_for_unlisted_accounts():
    dispatcher = Dispatcher()
    for ident, account, priority in [("l", "west", "low"), ("n", "north", "normal"), ("u", "harbor", "urgent")]:
        dispatcher.submit(Shipment(ident, account, priority, 0))
    assert [s.id for s in dispatcher.take_batch()] == ["u", "n", "l"]


