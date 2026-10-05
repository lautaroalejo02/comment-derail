import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.ts';
import { NotificationService } from '../src/notifications.ts';
import { handleShippingWebhook } from '../src/webhooks.ts';

test('a single publish invokes the notification handler exactly once', (t) => {
  const handle = t.mock.method(NotificationService.prototype, 'handle');
  const app = createApp();
  app.bus.publish({ id: 'rc-1', type: 'order.shipped', userId: 'u1', orderId: 'o-1', ts: 1_000 });
  assert.equal(handle.mock.callCount(), 1);
});

test('two distinct order.shipped events for the same user 10ms apart both notify', () => {
  const app = createApp();
  app.bus.publish({ id: 'rc-2', type: 'order.shipped', userId: 'u1', orderId: 'o-1', ts: 1_000 });
  app.bus.publish({ id: 'rc-3', type: 'order.shipped', userId: 'u1', orderId: 'o-2', ts: 1_010 });
  const inbox = app.outbox.to('u1');
  assert.equal(inbox.length, 2);
  assert.match(inbox[0].text, /o-1/);
  assert.match(inbox[1].text, /o-2/);
});

test('the same shipping webhook delivered twice ~800ms apart notifies once', () => {
  const app = createApp();
  const body = { idempotencyKey: 'wh-42', orderId: 'o-42', customerId: 'c-42' };
  handleShippingWebhook(app.bus, body, 10_000);
  handleShippingWebhook(app.bus, body, 10_800);
  assert.equal(app.outbox.to('c-42').length, 1);
});
