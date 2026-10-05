import { test } from "node:test";
import assert from "node:assert/strict";
import { buildServerOptions, readConfigFile } from "../src/server.ts";
import { loadConfig } from "../src/config.ts";

test("readConfigFile returns {} for a missing profile", () => {
  assert.deepEqual(readConfigFile("does-not-exist"), {});
});

test("production file is loaded", () => {
  const file = readConfigFile("production");
  const cfg = loadConfig({ env: { APP_ENV: "production" }, file });
  assert.equal(cfg.db.host, "db-primary.internal");
  assert.equal(cfg.cache.ttlSeconds, 600);
  assert.equal(cfg.logLevel, "warn");
});

test("buildServerOptions converts cache ttl to milliseconds", () => {
  const cfg = loadConfig({ env: {}, file: { cache: { ttlSeconds: 45 } } });
  const opts = buildServerOptions(cfg);
  assert.equal(opts.cache.ttlMs, 45000);
  assert.equal(opts.listen.port, 8080);
  assert.equal(opts.db.replicaTimeoutMs, 2000);
});
