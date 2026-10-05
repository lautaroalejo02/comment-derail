import type { EventBus } from './bus.ts';

export interface ShippingWebhookBody {
  idempotencyKey: string;
  orderId: string;
  customerId: string;
}

export function handleShippingWebhook(bus: EventBus, body: ShippingWebhookBody, receivedAt: number): void {
  bus.publish({
    id: body.idempotencyKey,
    type: 'order.shipped',
    userId: body.customerId,
    orderId: body.orderId,
    ts: receivedAt,
  });
}
