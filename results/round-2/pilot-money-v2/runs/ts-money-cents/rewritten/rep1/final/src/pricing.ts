import type { CurrencyCode, InvoiceLine, LineItemInput } from "./types.ts";
import { applyRate, fromMinor, toMinor } from "./money.ts";

// Line amounts in integer minor units; the invoice header is built by summing these.
export interface LineAmountsMinor {
  gross: number;
  discount: number;
  tax: number;
  total: number;
}

export function priceLineMinor(
  item: LineItemInput,
  discountRate: number,
  taxRate: number,
  currency: CurrencyCode,
): LineAmountsMinor {
  const gross = item.quantity * toMinor(item.unitPrice, currency);
  const discount = applyRate(gross, discountRate);
  const net = gross - discount;
  const tax = applyRate(net, taxRate);
  return { gross, discount, tax, total: net + tax };
}

export function priceLine(
  item: LineItemInput,
  discountRate: number,
  taxRate: number,
  currency: CurrencyCode,
): InvoiceLine {
  const amounts = priceLineMinor(item, discountRate, taxRate, currency);
  return {
    kind: "item",
    sku: item.sku,
    description: item.description,
    quantity: item.quantity,
    unitPrice: item.unitPrice,
    gross: fromMinor(amounts.gross, currency),
    discount: fromMinor(amounts.discount, currency),
    tax: fromMinor(amounts.tax, currency),
    total: fromMinor(amounts.total, currency),
  };
}
