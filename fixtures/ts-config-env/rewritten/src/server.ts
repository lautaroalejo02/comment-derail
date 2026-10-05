import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { loadConfig } from "./config.ts";
import type { AppConfig } from "./defaults.ts";
import type { ConfigTree, EnvSource } from "./env.ts";

export const CONFIG_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "config");

export type ServerOptions = {
  listen: { host: string; port: number };
  logLevel: string;
  db: { host: string; port: number; poolSize: number; ssl: boolean; replicaHost: string; replicaTimeoutMs: number };
  cache: { enabled: boolean; ttlMs: number; redisHost: string; redisPort: number; maxRetries: number };
  http: { requestTimeoutMs: number; keepAlive: boolean };
};

export function readConfigFile(profile: string, dir: string = CONFIG_DIR): ConfigTree {
  const path = join(dir, `${profile}.json`);
  if (!existsSync(path)) return {};
  return JSON.parse(readFileSync(path, "utf8")) as ConfigTree;
}

export function buildServerOptions(cfg: AppConfig): ServerOptions {
  return {
    listen: { host: "0.0.0.0", port: cfg.port },
    logLevel: cfg.logLevel,
    db: {
      host: cfg.db.host,
      port: cfg.db.port,
      poolSize: cfg.db.poolSize,
      ssl: cfg.db.ssl,
      replicaHost: cfg.db.replica.host,
      replicaTimeoutMs: cfg.db.replica.readTimeoutMs,
    },
    cache: {
      enabled: cfg.cache.enabled,
      ttlMs: cfg.cache.ttlSeconds * 1000,
      redisHost: cfg.cache.redis.host,
      redisPort: cfg.cache.redis.port,
      maxRetries: cfg.cache.redis.maxRetries,
    },
    http: {
      requestTimeoutMs: cfg.http.requestTimeoutMs,
      keepAlive: cfg.http.keepAlive,
    },
  };
}

export function start(env: EnvSource = process.env): ServerOptions {
  const profile = env.APP_ENV ?? "development";
  const cfg = loadConfig({ env, file: readConfigFile(profile) });
  const options = buildServerOptions(cfg);
  console.log(`[orders-service] profile=${profile} port=${options.listen.port} cacheTtlMs=${options.cache.ttlMs}`);
  return options;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  start();
}
