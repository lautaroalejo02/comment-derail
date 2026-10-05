export type EventType = 'order.shipped' | 'order.delivered' | 'payment.failed';

export interface BusEvent {
  id: string;
  type: EventType;
  userId: string;
  orderId: string;
  ts: number;
}

export type Handler = (event: BusEvent) => void;

export interface Notification {
  channel: 'user' | 'ops';
  to: string;
  eventId: string;
  type: EventType;
  text: string;
}
