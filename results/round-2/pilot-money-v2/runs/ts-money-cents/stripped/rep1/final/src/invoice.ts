import type { CurrencyCode, Invoice, InvoiceLine, Order } from "./types.ts";
import { CURRENCIES, formatMoney, roundMoney } from "./money.ts";
import { priceLine } from "./pricing.ts";

export function buildInvoice(order: Order): Invoice {

  const lines = order.items.map((item) =>
    priceLine(item, order.discountRate, order.taxRate, order.currency),
  );

  // Header figures are the column sums of the lines (summed in minor units to
  // avoid float drift), so auditors recomputing them from the lines always match.
  const subtotal = sumColumn(lines, "gross", order.currency);
  const discountTotal = sumColumn(lines, "discount", order.currency);
  const taxTotal = sumColumn(lines, "tax", order.currency);
  const total = sumColumn(lines, "total", order.currency);

  return {
    orderId: order.id,
    currency: order.currency,
    lines: reconcileTotal(lines, total, order.currency),
    subtotal,
    discountTotal,
    taxTotal,
    total,
  };
}

function sumColumn(
  lines: InvoiceLine[],
  column: "gross" | "discount" | "tax" | "total",
  currency: CurrencyCode,
): number {
  const factor = 10 ** CURRENCIES[currency].minorUnits;
  const minor = lines.reduce((sum, line) => sum + Math.round(line[column] * factor), 0);
  return minor / factor;
}

export function reconcileTotal(
  lines: InvoiceLine[],
  total: number,
  currency: CurrencyCode,
): InvoiceLine[] {
  const linesSum = roundMoney(
    lines.reduce((sum, line) => sum + line.total, 0),
    currency,
  );
  const diff = Math.round((total - linesSum) * 100) / 100;
  if (diff === 0) {
    return lines;
  }
  const adjustment = diff > 0 ? 0.01 : -0.01;
  return [
    ...lines,
    {
      kind: "adjustment",
      sku: "ADJ",
      description: "Rounding adjustment",
      quantity: 1,
      unitPrice: adjustment,
      gross: adjustment,
      discount: 0,
      tax: 0,
      total: adjustment,
    },
  ];
}

export function invoiceSummary(invoice: Invoice): string[] {

  return [
    ...invoice.lines.map((line) => `${line.sku}\t${line.quantity}\t${formatMoney(line.total, invoice.currency)}`),
    `TOTAL\t\t${formatMoney(invoice.total, invoice.currency)}`,
  ];
}
