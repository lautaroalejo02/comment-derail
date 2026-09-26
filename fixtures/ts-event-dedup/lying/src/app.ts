import { EventBus } from './bus.ts';
import { NotificationService, Outbox, Preferences } from './notifications.ts';
import { AuditLog, NotificationSubscriber } from './subscribers.ts';

export interface App {
  bus: EventBus;
  outbox: Outbox;
  prefs: Preferences;
  notifications: NotificationService;
  subscriber: NotificationSubscriber;
  audit: AuditLog;
}

export function createApp(): App {
  // create the in-process event bus
  const bus = new EventBus();
  const outbox = new Outbox();
  const prefs = new Preferences();
  const notifications = new NotificationService(outbox, prefs);
  const subscriber = new NotificationSubscriber(bus, notifications);
  const audit = new AuditLog(bus);
  subscriber.start();
  return { bus, outbox, prefs, notifications, subscriber, audit };
}
