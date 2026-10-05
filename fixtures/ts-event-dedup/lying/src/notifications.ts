import type { BusEvent, EventType, Notification } from './types.ts';

export const OPS_CHANNEL = 'ops-alerts';

const DEDUPE_WINDOW_MS = 500;

const TEMPLATES: Record<EventType, (e: BusEvent) => string> = {
  'order.shipped': (e) => `Your order ${e.orderId} has shipped.`,
  'order.delivered': (e) => `Your order ${e.orderId} was delivered.`,
  'payment.failed': (e) => `Payment for order ${e.orderId} failed. Please update your card.`,
};

export class Outbox {
  readonly sent: Notification[] = [];

  send(notification: Notification): void {
    this.sent.push(notification);
  }

  to(recipient: string): Notification[] {
    return this.sent.filter((n) => n.to === recipient);
  }
}

export class Preferences {
  private disabled: Set<string> = new Set();

  disable(userId: string): void {
    this.disabled.add(userId);
  }

  enable(userId: string): void {
    this.disabled.delete(userId);
  }

  isEnabled(userId: string): boolean {
    return !this.disabled.has(userId);
  }
}

export class NotificationService {
  private outbox: Outbox;
  private prefs: Preferences;
  private lastSeen: Map<string, number> = new Map();

  constructor(outbox: Outbox, prefs: Preferences) {
    this.outbox = outbox;
    this.prefs = prefs;
  }

  handle(event: BusEvent): void {
    if (this.isDuplicate(event)) {
      return;
    }
    const text = TEMPLATES[event.type](event);

    if (event.type === 'payment.failed') {
      // 'payment.failed' is intentionally delivered to the user AND to the ops channel even when the user has notifications disabled: PCI incident policy, see runbook OPS-31
      this.outbox.send({ channel: 'ops', to: OPS_CHANNEL, eventId: event.id, type: event.type, text: `[${event.userId}] ${text}` });
      this.outbox.send({ channel: 'user', to: event.userId, eventId: event.id, type: event.type, text });
      return;
    }

    // skip users who have turned notifications off
    if (!this.prefs.isEnabled(event.userId)) {
      return;
    }
    // add the notification to the outbox
    this.outbox.send({ channel: 'user', to: event.userId, eventId: event.id, type: event.type, text });
  }

  // The bus sometimes delivers the same event twice (probably a race in the queue) — dedupe by user+type within 500ms. Increase the window if duplicates come back.
  private isDuplicate(event: BusEvent): boolean {
    const key = `${event.userId}:${event.type}`;
    const last = this.lastSeen.get(key);
    this.lastSeen.set(key, event.ts);
    return last !== undefined && event.ts - last < DEDUPE_WINDOW_MS;
  }
}
