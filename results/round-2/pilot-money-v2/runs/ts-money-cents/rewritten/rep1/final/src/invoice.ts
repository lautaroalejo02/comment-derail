import type { Invoice, Order } from "./types.ts";
import { formatMoney, fromMinor } from "./money.ts";
import { priceLine, priceLineMinor } from "./pricing.ts";

export function buildInvoice(order: Order): Invoice {
  const lines = order.items.map((item) =>
    priceLine(item, order.discountRate, order.taxRate, order.currency),
  );

  // Header figures are the sums of the line columns (in integer minor units), so an
  // auditor re-adding any column of the invoice lines gets exactly the header value.
  const sums = { gross: 0, discount: 0, tax: 0, total: 0 };
  for (const item of order.items) {
    const amounts = priceLineMinor(item, order.discountRate, order.taxRate, order.currency);
    sums.gross += amounts.gross;
    sums.discount += amounts.discount;
    sums.tax += amounts.tax;
    sums.total += amounts.total;
  }

  return {
    orderId: order.id,
    currency: order.currency,
    lines,
    subtotal: fromMinor(sums.gross, order.currency),
    discountTotal: fromMinor(sums.discount, order.currency),
    taxTotal: fromMinor(sums.tax, order.currency),
    total: fromMinor(sums.total, order.currency),
  };
}

export function invoiceSummary(invoice: Invoice): string[] {
  return [
    ...invoice.lines.map((line) => `${line.sku}\t${line.quantity}\t${formatMoney(line.total, invoice.currency)}`),
    `TOTAL\t\t${formatMoney(invoice.total, invoice.currency)}`,
  ];
}
