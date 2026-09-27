from src.dispatch import Dispatcher
from src.models import Shipment


def test_arrival_order_wins_over_producer_clock_for_ties():
    dispatcher = Dispatcher()
    dispatcher.submit(Shipment("first", "north", "normal", 500))
    dispatcher.submit(Shipment("second", "north", "normal", 10))
    dispatcher.submit(Shipment("third", "north", "normal", 200))
    assert [s.id for s in dispatcher.take_batch()] == ["first", "second", "third"]
