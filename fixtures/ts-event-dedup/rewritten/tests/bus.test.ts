import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EventBus } from '../src/bus.ts';
import type { BusEvent } from '../src/types.ts';

const shipped = (id: string): BusEvent => ({ id, type: 'order.shipped', userId: 'u1', orderId: 'o-1', ts: 0 });

test('publish delivers to subscribers of that type', () => {
  const bus = new EventBus();
  const seen: string[] = [];
  bus.subscribe('order.shipped', (e) => seen.push(e.id));
  bus.publish(shipped('e1'));
  assert.deepEqual(seen, ['e1']);
});

test('publish does not deliver to subscribers of other types', () => {
  const bus = new EventBus();
  const seen: string[] = [];
  bus.subscribe('order.delivered', (e) => seen.push(e.id));
  bus.publish(shipped('e1'));
  assert.deepEqual(seen, []);
});

test('unsubscribe removes the handler', () => {
  const bus = new EventBus();
  const seen: string[] = [];
  const off = bus.subscribe('order.shipped', (e) => seen.push(e.id));
  off();
  bus.publish(shipped('e1'));
  assert.deepEqual(seen, []);
  assert.equal(bus.listenerCount('order.shipped'), 0);
});

test('listenerCount reflects subscriptions', () => {
  const bus = new EventBus();
  bus.subscribe('order.shipped', () => {});
  bus.subscribe('order.shipped', () => {});
  assert.equal(bus.listenerCount('order.shipped'), 2);
  assert.equal(bus.listenerCount('payment.failed'), 0);
});
