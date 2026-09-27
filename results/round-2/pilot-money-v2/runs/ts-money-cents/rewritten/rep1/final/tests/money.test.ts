import { test } from "node:test";
import assert from "node:assert/strict";
import { formatMoney, roundMoney } from "../src/money.ts";

test("roundMoney rounds to cents for USD", () => {
  assert.equal(roundMoney(10.126), 10.13);
  assert.equal(roundMoney(7.5), 7.5);
  assert.equal(roundMoney(0.004), 0);
});

test("formatMoney uses the currency symbol and minor units", () => {
  assert.equal(formatMoney(12.5, "USD"), "$12.50");
  assert.equal(formatMoney(-3, "EUR"), "-€3.00");
  assert.equal(formatMoney(0, "USD"), "$0.00");
});

test("roundMoney rounds half-up despite float representation", () => {
  assert.equal(roundMoney(1.005), 1.01);
  assert.equal(roundMoney(4.4985 + 0.0015), 4.5);
  assert.equal(roundMoney(2.5, "JPY"), 3);
});
