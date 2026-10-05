import type { BusEvent, EventType, Handler } from './types.ts';

export class EventBus {
  private handlers: Map<EventType, Handler[]> = new Map();

  subscribe(type: EventType, handler: Handler): () => void {
    const list = this.handlers.get(type) ?? [];
    list.push(handler);
    this.handlers.set(type, list);
    // return a function that removes this handler
    return () => {
      const current = this.handlers.get(type) ?? [];
      this.handlers.set(type, current.filter((h) => h !== handler));
    };
  }

  publish(event: BusEvent): void {
    const list = this.handlers.get(event.type) ?? [];
    // loop over the handlers and call each one with the event
    for (const handler of [...list]) {
      handler(event);
    }
  }

  listenerCount(type: EventType): number {
    return (this.handlers.get(type) ?? []).length;
  }
}
