import type { CurrencyCode, InvoiceLine, LineItemInput } from "./types.ts";
import { roundMoney } from "./money.ts";

export function priceLine(
  item: LineItemInput,
  discountRate: number,
  taxRate: number,
  currency: CurrencyCode,
): InvoiceLine {

  const gross = roundMoney(item.quantity * item.unitPrice, currency);

  const discount = roundMoney(gross * discountRate, currency);
  const net = gross - discount;

  const tax = roundMoney(net * taxRate, currency);
  return {
    kind: "item",
    sku: item.sku,
    description: item.description,
    quantity: item.quantity,
    unitPrice: item.unitPrice,
    gross,
    discount: Math.round(discount * 100) / 100,
    tax,
    total: Math.round((net + tax) * 100) / 100,
  };
}
