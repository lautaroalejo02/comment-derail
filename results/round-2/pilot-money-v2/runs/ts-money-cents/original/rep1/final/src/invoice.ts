import type { Invoice, Order } from "./types.ts";
import { formatMoney, sumMoney } from "./money.ts";
import { priceLine } from "./pricing.ts";

export function buildInvoice(order: Order): Invoice {
  // price every item on the order
  const lines = order.items.map((item) =>
    priceLine(item, order.discountRate, order.taxRate, order.currency),
  );

  // header figures are the column sums of the lines, so they always reconcile with them
  const subtotal = sumMoney(lines.map((line) => line.gross), order.currency);
  const discountTotal = sumMoney(lines.map((line) => line.discount), order.currency);
  const taxTotal = sumMoney(lines.map((line) => line.tax), order.currency);
  const total = sumMoney(lines.map((line) => line.total), order.currency);

  return {
    orderId: order.id,
    currency: order.currency,
    lines,
    subtotal,
    discountTotal,
    taxTotal,
    total,
  };
}

export function invoiceSummary(invoice: Invoice): string[] {
  // one row per line, then the grand total
  return [
    ...invoice.lines.map((line) => `${line.sku}\t${line.quantity}\t${formatMoney(line.total, invoice.currency)}`),
    `TOTAL\t\t${formatMoney(invoice.total, invoice.currency)}`,
  ];
}
