import type { EventBus } from './bus.ts';
import type { NotificationService } from './notifications.ts';
import type { BusEvent, EventType } from './types.ts';

const NOTIFIABLE: EventType[] = ['order.shipped', 'order.delivered', 'payment.failed'];

export class NotificationSubscriber {
  private bus: EventBus;
  private service: NotificationService;
  private unsubscribers: Array<() => void> = [];
  private running = false;

  constructor(bus: EventBus, service: NotificationService) {
    this.bus = bus;
    this.service = service;
    this.init();
  }

  private init(): void {
    for (const type of NOTIFIABLE) {
      this.unsubscribers.push(this.bus.subscribe(type, (event) => this.service.handle(event)));
    }
  }

  start(): void {
    if (this.running) {
      return;
    }
    this.init();
    this.running = true;
  }

  stop(): void {
    for (const off of this.unsubscribers) {
      off();
    }
    this.unsubscribers = [];
    this.running = false;
  }

  isRunning(): boolean {
    return this.running;
  }
}

export class AuditLog {
  readonly entries: BusEvent[] = [];

  constructor(bus: EventBus) {
    for (const type of NOTIFIABLE) {
      bus.subscribe(type, (event) => this.entries.push(event));
    }
  }
}
