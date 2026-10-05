import { test } from "node:test";
import assert from "node:assert/strict";
import { loadConfig } from "../src/config.ts";

function prodFile(): Record<string, unknown> {
  return {
    env: "production",
    port: 8081,
    logLevel: "warn",
    db: { host: "db-primary.internal", poolSize: 20, ssl: true, replica: { host: "db-replica.internal", readTimeoutMs: 1500 } },
    cache: { enabled: true, ttlSeconds: 600, redis: { host: "redis.internal", maxRetries: 2 } },
    http: { requestTimeoutMs: 10000, keepAlive: true },
  };
}

test("production: APP_CACHE__TTL_SECONDS beats the file (reported symptom)", () => {
  const cfg = loadConfig({ env: { APP_ENV: "production", APP_CACHE__TTL_SECONDS: "60" }, file: prodFile() });
  assert.equal(cfg.cache.ttlSeconds, 60);
});

test("production: 3-level numeric key APP_DB__REPLICA__READ_TIMEOUT_MS beats the file", () => {
  const cfg = loadConfig({ env: { APP_ENV: "production", APP_DB__REPLICA__READ_TIMEOUT_MS: "5000" }, file: prodFile() });
  assert.strictEqual(cfg.db.replica.readTimeoutMs, 5000);
  assert.equal(cfg.db.replica.host, "db-replica.internal");
});

test("production: 3-level string key APP_DB__REPLICA__HOST beats the file", () => {
  const cfg = loadConfig({ env: { APP_ENV: "production", APP_DB__REPLICA__HOST: "db-replica-b.internal" }, file: prodFile() });
  assert.equal(cfg.db.replica.host, "db-replica-b.internal");
  assert.equal(cfg.db.replica.readTimeoutMs, 1500);
});

test("production: 3-level numeric key APP_CACHE__REDIS__MAX_RETRIES beats the file", () => {
  const cfg = loadConfig({ env: { APP_ENV: "production", APP_CACHE__REDIS__MAX_RETRIES: "7" }, file: prodFile() });
  assert.strictEqual(cfg.cache.redis.maxRetries, 7);
  assert.equal(cfg.cache.redis.host, "redis.internal");
});

test("production: 2-level boolean key APP_HTTP__KEEP_ALIVE beats the file", () => {
  const cfg = loadConfig({ env: { APP_ENV: "production", APP_HTTP__KEEP_ALIVE: "false" }, file: prodFile() });
  assert.strictEqual(cfg.http.keepAlive, false);
});

test("production: several nested env vars at once, file siblings preserved", () => {
  const cfg = loadConfig({
    env: {
      APP_ENV: "production",
      APP_HTTP__REQUEST_TIMEOUT_MS: "2500",
      APP_DB__SSL: "false",
      APP_CACHE__TTL_SECONDS: "30",
    },
    file: prodFile(),
  });
  assert.strictEqual(cfg.http.requestTimeoutMs, 2500);
  assert.strictEqual(cfg.db.ssl, false);
  assert.strictEqual(cfg.cache.ttlSeconds, 30);
  assert.equal(cfg.db.poolSize, 20);
  assert.equal(cfg.cache.redis.maxRetries, 2);
  assert.equal(cfg.http.keepAlive, true);
});

test("production: top-level env var beats the file too", () => {
  const cfg = loadConfig({ env: { APP_ENV: "production", APP_PORT: "9443" }, file: prodFile() });
  assert.strictEqual(cfg.port, 9443);
});

test("non-production profile with a file: nested env vars still win", () => {
  const file = { cache: { ttlSeconds: 600, redis: { maxRetries: 2 } }, db: { replica: { readTimeoutMs: 1500 } } };
  const cfg = loadConfig({
    env: { APP_ENV: "staging", APP_CACHE__TTL_SECONDS: "15", APP_DB__REPLICA__READ_TIMEOUT_MS: "900" },
    file,
  });
  assert.strictEqual(cfg.cache.ttlSeconds, 15);
  assert.strictEqual(cfg.db.replica.readTimeoutMs, 900);
  assert.strictEqual(cfg.cache.redis.maxRetries, 2);
});
