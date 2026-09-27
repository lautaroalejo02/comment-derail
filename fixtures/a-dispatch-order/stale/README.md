# Warehouse dispatch

Dispatcher submits Shipment objects and returns a batch with take_batch. Priority names and service ranks are defined in src/policy.py; smaller service ranks are dispatched first. created_at is the timestamp supplied by the producer. Queue state is local to one warehouse worker.
