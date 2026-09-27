import pytest

from src.dispatch import Dispatcher
from src.models import Shipment


def test_regular_batch_and_empty_poll():
    dispatcher = Dispatcher()
    dispatcher.submit(Shipment("n1", "north", "normal", 10))
    dispatcher.submit(Shipment("n2", "north", "normal", 20))
    assert [s.id for s in dispatcher.take_batch()] == ["n1", "n2"]
    assert dispatcher.take_batch() == []


def test_beacon_urgent_shipment():
    dispatcher = Dispatcher()
    dispatcher.submit(Shipment("n1", "north", "normal", 10))
    dispatcher.submit(Shipment("b1", "beacon", "urgent", 20))
    assert [s.id for s in dispatcher.take_batch()] == ["b1", "n1"]


def test_unknown_priority_is_rejected():
    with pytest.raises(ValueError):
        Dispatcher().submit(Shipment("x", "north", "overnight", 0))
