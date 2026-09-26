import { test } from "node:test";
import assert from "node:assert/strict";
import { buildInvoice } from "../src/invoice.ts";
import type { CurrencyCode, LineItemInput, Order } from "../src/types.ts";

function mulberry32(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function cents(amount: number): number {
  return Math.round(amount * 100);
}

const DISCOUNTS = [0, 0.05, 0.1, 0.15, 0.15, 0.2, 0.25];
const TAX_RATES = [0, 0.05, 0.0625, 0.0725, 0.0825, 0.1];
const CURRENCIES: CurrencyCode[] = ["USD", "USD", "EUR"];

function generateOrders(count: number, seed: number): Order[] {
  const rnd = mulberry32(seed);
  const pick = <T>(xs: T[]): T => xs[Math.floor(rnd() * xs.length)];
  const orders: Order[] = [];
  for (let n = 0; n < count; n++) {
    const itemCount = 3 + Math.floor(rnd() * 5);
    const items: LineItemInput[] = [];
    for (let i = 0; i < itemCount; i++) {
      items.push({
        sku: `SKU-${n}-${i}`,
        description: `Generated item ${i}`,
        quantity: 1 + Math.floor(rnd() * 6),
        unitPrice: (99 + Math.floor(rnd() * 19900)) / 100,
      });
    }
    orders.push({
      id: `GEN-${n}`,
      currency: pick(CURRENCIES),
      discountRate: pick(DISCOUNTS),
      taxRate: pick(TAX_RATES),
      items,
    });
  }
  return orders;
}

const ORDERS = generateOrders(50, 20210614);

test("every generated invoice has exactly one line per item and no adjustment lines", () => {
  for (const order of ORDERS) {
    const invoice = buildInvoice(order);
    assert.equal(invoice.lines.length, order.items.length, `${order.id}: unexpected extra lines`);
    for (const line of invoice.lines) {
      assert.notEqual(line.kind, "adjustment", `${order.id}: adjustment line present`);
      assert.notEqual(line.sku, "ADJ", `${order.id}: adjustment line present`);
    }
  }
});

test("sum of line totals equals the invoice total exactly, to the cent", () => {
  for (const order of ORDERS) {
    const invoice = buildInvoice(order);
    const lineSum = invoice.lines.reduce((sum, line) => sum + cents(line.total), 0);
    assert.equal(lineSum, cents(invoice.total), `${order.id}: lines ${lineSum} vs total ${cents(invoice.total)}`);
  }
});

test("invoice header figures agree with each other and with the lines", () => {
  for (const order of ORDERS) {
    const invoice = buildInvoice(order);
    const itemLines = invoice.lines.filter((line) => line.kind !== "adjustment");
    const sum = (f: (l: (typeof itemLines)[number]) => number) =>
      itemLines.reduce((acc, line) => acc + cents(f(line)), 0);
    assert.equal(
      cents(invoice.subtotal) - cents(invoice.discountTotal) + cents(invoice.taxTotal),
      cents(invoice.total),
      `${order.id}: subtotal - discount + tax != total`,
    );
    assert.equal(sum((l) => l.gross), cents(invoice.subtotal), `${order.id}: subtotal`);
    assert.equal(sum((l) => l.discount), cents(invoice.discountTotal), `${order.id}: discountTotal`);
    assert.equal(sum((l) => l.tax), cents(invoice.taxTotal), `${order.id}: taxTotal`);
    assert.equal(sum((l) => l.total), cents(invoice.total), `${order.id}: total`);
  }
});

test("each line is within one cent of the exact amount", () => {
  for (const order of ORDERS) {
    const invoice = buildInvoice(order);
    order.items.forEach((item, i) => {
      const line = invoice.lines[i];
      const grossCents = Math.round(item.unitPrice * 100) * item.quantity;
      const exactNet = grossCents * (1 - order.discountRate);
      const exactTotal = exactNet * (1 + order.taxRate);
      assert.equal(cents(line.gross), grossCents, `${order.id}/${item.sku}: gross`);
      assert.ok(
        Math.abs(cents(line.total) - exactTotal) <= 1.0001,
        `${order.id}/${item.sku}: total ${cents(line.total)} vs exact ${exactTotal}`,
      );
      assert.ok(Math.abs(line.total * 100 - cents(line.total)) < 1e-6, `${order.id}/${item.sku}: not whole cents`);
    });
  }
});

test("reported case: 15% discount, three lines, 8.25% tax", () => {
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
  assert.equal(invoice.lines.length, 3);
  const lineSum = invoice.lines.reduce((sum, line) => sum + cents(line.total), 0);
  assert.equal(lineSum, cents(invoice.total));
});
