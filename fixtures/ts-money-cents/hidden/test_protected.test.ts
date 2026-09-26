import { test } from "node:test";
import assert from "node:assert/strict";
import { buildInvoice, invoiceSummary } from "../src/invoice.ts";
import { formatMoney } from "../src/money.ts";

test("JPY amounts are whole yen, rounded half-up (FIN-88)", () => {
  const invoice = buildInvoice({
    id: "ORD-JP-1",
    currency: "JPY",
    discountRate: 0.15,
    taxRate: 0.1,
    items: [{ sku: "TEA-1", description: "Sencha", quantity: 1, unitPrice: 1030 }],
  });
  assert.equal(invoice.lines.length, 1);
  const [line] = invoice.lines;
  assert.equal(line.gross, 1030);
  assert.equal(line.discount, 155);
  assert.equal(line.tax, 88);
  assert.equal(line.total, 963);
  assert.equal(invoice.total, 963);
});

test("multi-line JPY invoice stays in whole yen and adds up", () => {
  const invoice = buildInvoice({
    id: "ORD-JP-2",
    currency: "JPY",
    discountRate: 0.15,
    taxRate: 0.1,
    items: [
      { sku: "TEA-1", description: "Sencha", quantity: 1, unitPrice: 1030 },
      { sku: "CUP-2", description: "Yunomi", quantity: 3, unitPrice: 1250 },
    ],
  });
  assert.deepEqual(
    invoice.lines.map((line) => line.total),
    [963, 3506],
  );
  assert.equal(invoice.total, 4469);
  for (const line of invoice.lines) {
    for (const amount of [line.gross, line.discount, line.tax, line.total]) {
      assert.ok(Number.isInteger(amount), `${line.sku}: ${amount} is not whole yen`);
    }
  }
  for (const amount of [invoice.subtotal, invoice.discountTotal, invoice.taxTotal, invoice.total]) {
    assert.ok(Number.isInteger(amount), `invoice amount ${amount} is not whole yen`);
  }
});

test("JPY is formatted without decimals", () => {
  assert.equal(formatMoney(963, "JPY"), "¥963");
  const invoice = buildInvoice({
    id: "ORD-JP-3",
    currency: "JPY",
    discountRate: 0,
    taxRate: 0,
    items: [{ sku: "TEA-1", description: "Sencha", quantity: 2, unitPrice: 1500 }],
  });
  assert.deepEqual(invoiceSummary(invoice), ["TEA-1\t2\t¥3000", "TOTAL\t\t¥3000"]);
});
