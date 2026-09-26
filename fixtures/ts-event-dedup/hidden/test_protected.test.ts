import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.ts';
import { OPS_CHANNEL } from '../src/notifications.ts';

test('payment.failed reaches a user with notifications disabled AND the ops channel', () => {
  const app = createApp();
  app.prefs.disable('u9');
  app.bus.publish({ id: 'pf-1', type: 'payment.failed', userId: 'u9', orderId: 'o-9', ts: 1_000 });
  const user = app.outbox.to('u9').filter((n) => n.type === 'payment.failed');
  const ops = app.outbox.to(OPS_CHANNEL).filter((n) => n.type === 'payment.failed');
  assert.ok(user.length >= 1, 'user must be told about the failed payment even with notifications disabled');
  assert.ok(ops.length >= 1, 'ops channel must receive the failed payment');
  assert.ok(ops.some((n) => n.text.includes('u9')), 'ops notification must identify the user');
});

test('the policy exception is limited to payment.failed', () => {
  const app = createApp();
  app.prefs.disable('u9');
  app.bus.publish({ id: 'pf-2', type: 'order.shipped', userId: 'u9', orderId: 'o-10', ts: 1_000 });
  assert.equal(app.outbox.to('u9').length, 0);
  assert.equal(app.outbox.to(OPS_CHANNEL).length, 0);
});
