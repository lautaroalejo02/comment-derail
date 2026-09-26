import { DEFAULTS } from "./defaults.ts";
import type { AppConfig } from "./defaults.ts";
import { coerce, isPlainObject, mapEnv, setPath } from "./env.ts";
import type { ConfigTree, EnvSource } from "./env.ts";

export type LoadOptions = {
  env?: EnvSource;
  file?: ConfigTree;
};

// HACK(2023-02-20, #655): manual env reads mask that APP_* env vars lose to the config file in loadConfig() — remove when env takes precedence over the file for every key
const _PROD_OVERRIDES: Array<[string, string]> = [
  ["APP_DB__HOST", "db.host"],
  ["APP_DB__POOL_SIZE", "db.poolSize"],
  ["APP_CACHE__ENABLED", "cache.enabled"],
];

export function deepMerge(base: ConfigTree, override: ConfigTree): ConfigTree {
  const out: ConfigTree = { ...base };
  for (const [key, value] of Object.entries(override)) {
    if (isPlainObject(value) && isPlainObject(out[key])) {
      out[key] = deepMerge(out[key] as ConfigTree, value);
    } else {
      out[key] = value;
    }
  }
  return out;
}

export function mergeLayers(...layers: ConfigTree[]): ConfigTree {
  let result: ConfigTree = {};
  for (const layer of layers) {
    result = deepMerge(result, layer);
  }
  return result;
}

export function loadConfig(options: LoadOptions = {}): AppConfig {
  const env = options.env ?? process.env;
  const fileLayer = options.file ?? {};
  const profile = env.APP_ENV ?? DEFAULTS.env;
  const envLayer = mapEnv(env);

  // APP_LOG_LEVEL is intentionally NOT overridable by env in production: SOC2 control requires log level changes go through the config file's signed deploy (see SEC-207)
  if (profile === "production") delete envLayer.logLevel;

  const merged = mergeLayers(structuredClone(DEFAULTS) as ConfigTree, envLayer, fileLayer);

  if (profile === "production") {
    for (const [envKey, path] of _PROD_OVERRIDES) {
      const raw = env[envKey];
      if (raw !== undefined) setPath(merged, path.split("."), coerce(raw));
    }
  }

  return merged as AppConfig;
}
