import { test } from "node:test";
import assert from "node:assert/strict";
import { buildInvoice, invoiceSummary } from "../src/invoice.ts";
import type { Order } from "../src/types.ts";

function cents(amount: number): number {
  return Math.round(amount * 100);
}

function sumLineCents(order: Order): { lines: number; total: number } {
  const invoice = buildInvoice(order);
  return {
    lines: invoice.lines.reduce((sum, line) => sum + cents(line.total), 0),
    total: cents(invoice.total),
  };
}

test("simple invoice without discount or tax", () => {
  const invoice = buildInvoice({
    id: "ORD-1001",
    currency: "USD",
    discountRate: 0,
    taxRate: 0,
    items: [
      { sku: "MUG-01", description: "Coffee mug", quantity: 2, unitPrice: 8 },
      { sku: "TEE-02", description: "T-shirt", quantity: 1, unitPrice: 15.5 },
    ],
  });
  assert.equal(invoice.lines.length, 2);
  assert.equal(invoice.subtotal, 31.5);
  assert.equal(invoice.discountTotal, 0);
  assert.equal(invoice.taxTotal, 0);
  assert.equal(invoice.total, 31.5);
});

test("invoice with discount and tax", () => {
  const invoice = buildInvoice({
    id: "ORD-1002",
    currency: "USD",
    discountRate: 0.1,
    taxRate: 0.05,
    items: [
      { sku: "BOOK-1", description: "Notebook", quantity: 2, unitPrice: 10 },
      { sku: "BAG-7", description: "Tote bag", quantity: 1, unitPrice: 20 },
    ],
  });
  assert.equal(invoice.subtotal, 40);
  assert.equal(invoice.discountTotal, 4);
  assert.equal(invoice.taxTotal, 1.8);
  assert.equal(invoice.total, 37.8);
  assert.deepEqual(
    invoice.lines.map((line) => line.total),
    [18.9, 18.9],
  );
});

test("line totals add up to the invoice total", () => {
  const orders: Order[] = [
    {
      id: "ORD-1003",
      currency: "USD",
      discountRate: 0.2,
      taxRate: 0.0625,
      items: [
        { sku: "LAMP-4", description: "Desk lamp", quantity: 1, unitPrice: 34.99 },
        { sku: "BULB-9", description: "LED bulb", quantity: 4, unitPrice: 3.25 },
      ],
    },
    {
      id: "ORD-1004",
      currency: "EUR",
      discountRate: 0.05,
      taxRate: 0.1,
      items: [
        { sku: "CHAIR-2", description: "Chair", quantity: 2, unitPrice: 79.9 },
        { sku: "PAD-5", description: "Seat pad", quantity: 2, unitPrice: 12.4 },
        { sku: "RUG-8", description: "Rug", quantity: 1, unitPrice: 120 },
      ],
    },
  ];
  for (const order of orders) {
    const { lines, total } = sumLineCents(order);
    assert.equal(lines, total, order.id);
  }
});

test("invoiceSummary lists every line and the total", () => {
  const invoice = buildInvoice({
    id: "ORD-1005",
    currency: "USD",
    discountRate: 0,
    taxRate: 0,
    items: [{ sku: "MUG-01", description: "Coffee mug", quantity: 3, unitPrice: 8 }],
  });
  assert.deepEqual(invoiceSummary(invoice), ["MUG-01\t3\t$24.00", "TOTAL\t\t$24.00"]);
});

test("header figures equal the column sums of the lines (ORD-2231)", () => {
  const invoice = buildInvoice({
    id: "ORD-2231",
    currency: "USD",
    discountRate: 0.15,
    taxRate: 0.0825,
    items: [
      { sku: "MUG-01", description: "Coffee mug", quantity: 1, unitPrice: 9.99 },
      { sku: "HOOD-3", description: "Hoodie", quantity: 1, unitPrice: 29.99 },
      { sku: "BOOT-4", description: "Boots", quantity: 2, unitPrice: 49.99 },
    ],
  });
  const column = (key: "gross" | "discount" | "tax" | "total") =>
    invoice.lines.reduce((sum, line) => sum + cents(line[key]), 0);
  assert.equal(cents(invoice.subtotal), column("gross"));
  assert.equal(cents(invoice.discountTotal), column("discount"));
  assert.equal(cents(invoice.taxTotal), column("tax"));
  assert.equal(cents(invoice.total), column("total"));
  assert.equal(invoice.discountTotal, 21);
  assert.equal(invoice.taxTotal, 9.81);
  assert.equal(invoice.total, 128.77);
});
