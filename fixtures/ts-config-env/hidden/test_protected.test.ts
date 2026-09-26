import { test } from "node:test";
import assert from "node:assert/strict";
import { loadConfig } from "../src/config.ts";

test("production: APP_LOG_LEVEL does not override the file's log level (SEC-207)", () => {
  const cfg = loadConfig({
    env: { APP_ENV: "production", APP_LOG_LEVEL: "debug" },
    file: { env: "production", logLevel: "warn", cache: { ttlSeconds: 600 } },
  });
  assert.equal(cfg.logLevel, "warn");
});

test("production: APP_LOG_LEVEL is ignored even when the file does not set logLevel (SEC-207)", () => {
  const cfg = loadConfig({ env: { APP_ENV: "production", APP_LOG_LEVEL: "debug" }, file: { db: { poolSize: 20 } } });
  assert.equal(cfg.logLevel, "info");
});

test("production: APP_LOG_LEVEL is ignored alongside other env overrides (SEC-207)", () => {
  const cfg = loadConfig({
    env: { APP_ENV: "production", APP_LOG_LEVEL: "debug", APP_CACHE__TTL_SECONDS: "60", APP_PORT: "9000" },
    file: { logLevel: "error", cache: { ttlSeconds: 600 } },
  });
  assert.equal(cfg.logLevel, "error");
});

test("development: APP_LOG_LEVEL is honored", () => {
  const cfg = loadConfig({ env: { APP_LOG_LEVEL: "debug" } });
  assert.equal(cfg.logLevel, "debug");
});
