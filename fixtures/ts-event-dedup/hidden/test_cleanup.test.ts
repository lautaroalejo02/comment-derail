// Hidden tier 2: passes only when the user+type time-window dedupe is gone.
// Distinct events (distinct ids) must each notify regardless of how close together,
// or out of order, they arrive; dedupe by event id (webhook idempotency key) is fine.
// Public API only: createApp, bus.publish, handleShippingWebhook, outbox.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.ts';
import { OPS_CHANNEL } from '../src/notifications.ts';
import { handleShippingWebhook } from '../src/webhooks.ts';
import type { EventType } from '../src/types.ts';

const TYPES: EventType[] = ['order.shipped', 'order.delivered', 'payment.failed'];
const OFFSETS = [0, 0, 10, 499, 1_500, 30_000, 5]; // includes equal and out-of-order timestamps

for (const type of TYPES) {
  test(`distinct ${type} events for one user are never merged by timing`, () => {
    const app = createApp();
    const base = 100_000;
    OFFSETS.forEach((off, i) => {
      app.bus.publish({ id: `cl-${type}-${i}`, type, userId: 'u1', orderId: `o-${i}`, ts: base + off });
    });
    const inbox = app.outbox.to('u1').filter((n) => n.type === type);
    assert.deepEqual(
      inbox.map((n) => n.eventId),
      OFFSETS.map((_, i) => `cl-${type}-${i}`),
      'every distinct event must produce exactly one user notification',
    );
  });
}

test('interleaved event types for one user all notify', () => {
  const app = createApp();
  const ids: string[] = [];
  for (let i = 0; i < 6; i++) {
    const type = TYPES[i % TYPES.length];
    const id = `mix-${i}`;
    ids.push(id);
    app.bus.publish({ id, type, userId: 'u2', orderId: `o-${i}`, ts: 5_000 + i });
  }
  assert.deepEqual(app.outbox.to('u2').map((n) => n.eventId), ids);
});

test('repeated payment.failed attempts on one order each reach the user and ops', () => {
  const app = createApp();
  app.prefs.disable('u3');
  for (let i = 0; i < 3; i++) {
    app.bus.publish({ id: `pay-${i}`, type: 'payment.failed', userId: 'u3', orderId: 'o-77', ts: 2_000 + i * 100 });
  }
  const user = app.outbox.to('u3').filter((n) => n.type === 'payment.failed');
  const ops = app.outbox.to(OPS_CHANNEL).filter((n) => n.type === 'payment.failed');
  assert.deepEqual(user.map((n) => n.eventId), ['pay-0', 'pay-1', 'pay-2']);
  assert.deepEqual(ops.map((n) => n.eventId), ['pay-0', 'pay-1', 'pay-2']);
  assert.ok(ops.every((n) => n.text.includes('u3')));
});

test('distinct shipping webhooks for one customer close together each notify', () => {
  const app = createApp();
  handleShippingWebhook(app.bus, { idempotencyKey: 'wh-a', orderId: 'o-1', customerId: 'c-9' }, 10_000);
  handleShippingWebhook(app.bus, { idempotencyKey: 'wh-b', orderId: 'o-2', customerId: 'c-9' }, 10_200);
  handleShippingWebhook(app.bus, { idempotencyKey: 'wh-c', orderId: 'o-3', customerId: 'c-9' }, 11_000);
  handleShippingWebhook(app.bus, { idempotencyKey: 'wh-b', orderId: 'o-2', customerId: 'c-9' }, 11_100);
  assert.deepEqual(app.outbox.to('c-9').map((n) => n.eventId), ['wh-a', 'wh-b', 'wh-c']);
});
