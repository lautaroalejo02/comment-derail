import { test } from "node:test";
import assert from "node:assert/strict";
import { loadConfig } from "../src/config.ts";
import { DEFAULTS } from "../src/defaults.ts";

test("no env and no file yields defaults", () => {
  const cfg = loadConfig({ env: {} });
  assert.deepEqual(cfg, DEFAULTS);
});

test("loading does not mutate DEFAULTS", () => {
  const before = structuredClone(DEFAULTS);
  loadConfig({ env: { APP_ENV: "production", APP_DB__POOL_SIZE: "99" }, file: { db: { poolSize: 5 } } });
  assert.deepEqual(DEFAULTS, before);
});

test("file values override defaults and keep sibling defaults", () => {
  const cfg = loadConfig({ env: {}, file: { db: { poolSize: 25 }, cache: { ttlSeconds: 120 } } });
  assert.equal(cfg.db.poolSize, 25);
  assert.equal(cfg.db.host, "localhost");
  assert.equal(cfg.cache.ttlSeconds, 120);
  assert.equal(cfg.cache.redis.port, 6379);
});

test("top-level env vars override defaults", () => {
  const cfg = loadConfig({ env: { APP_PORT: "9090" } });
  assert.equal(cfg.port, 9090);
});

test("top-level env vars apply in production", () => {
  const cfg = loadConfig({ env: { APP_ENV: "production", APP_PORT: "443" }, file: { db: { poolSize: 20 } } });
  assert.equal(cfg.port, 443);
});

test("production: APP_DB__POOL_SIZE overrides the file", () => {
  const cfg = loadConfig({ env: { APP_ENV: "production", APP_DB__POOL_SIZE: "50" }, file: { db: { poolSize: 20 } } });
  assert.equal(cfg.db.poolSize, 50);
});

test("production: APP_DB__HOST overrides the file", () => {
  const cfg = loadConfig({
    env: { APP_ENV: "production", APP_DB__HOST: "db-failover.internal" },
    file: { db: { host: "db-primary.internal" } },
  });
  assert.equal(cfg.db.host, "db-failover.internal");
});

test("production: APP_CACHE__ENABLED=false disables the cache", () => {
  const cfg = loadConfig({ env: { APP_ENV: "production", APP_CACHE__ENABLED: "false" }, file: { cache: { enabled: true } } });
  assert.equal(cfg.cache.enabled, false);
});
