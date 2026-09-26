import { test } from "node:test";
import assert from "node:assert/strict";
import { priceLine } from "../src/pricing.ts";

test("priceLine applies discount before tax", () => {
  const line = priceLine(
    { sku: "BOOK-1", description: "Notebook", quantity: 2, unitPrice: 10 },
    0.1,
    0.05,
    "USD",
  );
  assert.equal(line.kind, "item");
  assert.equal(line.gross, 20);
  assert.equal(line.discount, 2);
  assert.equal(line.tax, 0.9);
  assert.equal(line.total, 18.9);
});

test("priceLine with no discount", () => {
  const line = priceLine(
    { sku: "PEN-3", description: "Pens", quantity: 3, unitPrice: 4.5 },
    0,
    0.0825,
    "USD",
  );
  assert.equal(line.gross, 13.5);
  assert.equal(line.discount, 0);
  assert.equal(line.tax, 1.11);
  assert.equal(line.total, 14.61);
});
