from src.dispatch import Dispatcher
from src.models import Shipment


def test_account_does_not_promote_low_priority_shipments():
    dispatcher = Dispatcher()
    dispatcher.submit(Shipment("b", "beacon", "low", 0))
    dispatcher.submit(Shipment("n", "north", "urgent", 1))
    assert [s.id for s in dispatcher.take_batch()] == ["n", "b"]
