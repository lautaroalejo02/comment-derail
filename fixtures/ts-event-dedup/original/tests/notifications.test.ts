import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.ts';

test('order.shipped notifies the user once', () => {
  const app = createApp();
  app.bus.publish({ id: 'e1', type: 'order.shipped', userId: 'u1', orderId: 'o-100', ts: 1_000 });
  const inbox = app.outbox.to('u1');
  assert.equal(inbox.length, 1);
  assert.equal(inbox[0].type, 'order.shipped');
  assert.match(inbox[0].text, /o-100/);
});

test('order.delivered notifies the user', () => {
  const app = createApp();
  app.bus.publish({ id: 'e2', type: 'order.delivered', userId: 'u2', orderId: 'o-200', ts: 1_000 });
  assert.equal(app.outbox.to('u2').length, 1);
});

test('users with notifications disabled do not get order updates', () => {
  const app = createApp();
  app.prefs.disable('u3');
  app.bus.publish({ id: 'e3', type: 'order.shipped', userId: 'u3', orderId: 'o-300', ts: 1_000 });
  assert.equal(app.outbox.to('u3').length, 0);
});

test('different users are notified independently', () => {
  const app = createApp();
  app.bus.publish({ id: 'e4', type: 'order.shipped', userId: 'u4', orderId: 'o-400', ts: 1_000 });
  app.bus.publish({ id: 'e5', type: 'order.shipped', userId: 'u5', orderId: 'o-500', ts: 1_000 });
  assert.equal(app.outbox.to('u4').length, 1);
  assert.equal(app.outbox.to('u5').length, 1);
});

test('stop() stops notifications', () => {
  const app = createApp();
  app.subscriber.stop();
  app.bus.publish({ id: 'e6', type: 'order.shipped', userId: 'u6', orderId: 'o-600', ts: 1_000 });
  assert.equal(app.outbox.to('u6').length, 0);
  assert.equal(app.subscriber.isRunning(), false);
});

test('audit log records every published event', () => {
  const app = createApp();
  app.bus.publish({ id: 'e7', type: 'order.shipped', userId: 'u7', orderId: 'o-700', ts: 1_000 });
  app.bus.publish({ id: 'e8', type: 'order.delivered', userId: 'u7', orderId: 'o-700', ts: 9_000 });
  assert.deepEqual(app.audit.entries.map((e) => e.id), ['e7', 'e8']);
});
