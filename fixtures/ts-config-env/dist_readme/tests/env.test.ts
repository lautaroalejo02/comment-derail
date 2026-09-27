import { test } from "node:test";
import assert from "node:assert/strict";
import { coerce, mapEnv, toCamel } from "../src/env.ts";

test("toCamel converts SCREAMING_SNAKE segments", () => {
  assert.equal(toCamel("PORT"), "port");
  assert.equal(toCamel("POOL_SIZE"), "poolSize");
  assert.equal(toCamel("REQUEST_TIMEOUT_MS"), "requestTimeoutMs");
});

test("coerce handles numbers, booleans and strings", () => {
  assert.equal(coerce("42"), 42);
  assert.equal(coerce("-1.5"), -1.5);
  assert.equal(coerce("true"), true);
  assert.equal(coerce("false"), false);
  assert.equal(coerce("db.internal"), "db.internal");
});

test("mapEnv picks up prefixed top-level keys only", () => {
  const tree = mapEnv({ APP_PORT: "9000", APP_LOG_LEVEL: "debug", HOME: "/root", PATH: "/usr/bin" });
  assert.deepEqual(tree, { port: 9000, logLevel: "debug" });
});
