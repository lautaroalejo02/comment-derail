import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.ts';
import { handleShippingWebhook } from '../src/webhooks.ts';

test('shipping webhook publishes order.shipped for the customer', () => {
  const app = createApp();
  handleShippingWebhook(app.bus, { idempotencyKey: 'wh-1', orderId: 'o-9', customerId: 'c-1' }, 5_000);
  assert.equal(app.audit.entries.length, 1);
  assert.equal(app.audit.entries[0].type, 'order.shipped');
  assert.equal(app.audit.entries[0].orderId, 'o-9');
  const inbox = app.outbox.to('c-1');
  assert.equal(inbox.length, 1);
  assert.match(inbox[0].text, /o-9/);
});
