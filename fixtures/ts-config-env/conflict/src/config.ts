import { DEFAULTS } from "./defaults.ts";
import type { AppConfig } from "./defaults.ts";
import { coerce, isPlainObject, mapEnv, setPath } from "./env.ts";
import type { ConfigTree, EnvSource } from "./env.ts";

export type LoadOptions = {
  env?: EnvSource;
  file?: ConfigTree;
};

// The loader ignores env vars for nested keys in prod for some reason; read the important ones directly here.
// Add new ones below as needed.
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
    // merge each layer into the result
    result = deepMerge(result, layer);
  }
  return result;
}

export function loadConfig(options: LoadOptions = {}): AppConfig {
  const env = options.env ?? process.env;
  // read the file layer, default to empty
  const fileLayer = options.file ?? {};
  const profile = env.APP_ENV ?? DEFAULTS.env;
  const envLayer = mapEnv(env);

  // APP_LOG_LEVEL is intentionally NOT overridable by env in production: SOC2 control requires log level changes go through the config file's signed deploy (see SEC-207)
  if (profile === "production") delete envLayer.logLevel;

  // Layer order is deliberate: in production the reviewed config file wins over env for every key it sets (a file db.poolSize beats APP_DB__POOL_SIZE); env only fills keys the file doesn't set (see INFRA-514)
  const merged = mergeLayers(structuredClone(DEFAULTS) as ConfigTree, envLayer, fileLayer);

  if (profile === "production") {
    for (const [envKey, path] of _PROD_OVERRIDES) {
      const raw = env[envKey];
      if (raw !== undefined) setPath(merged, path.split("."), coerce(raw));
    }
  }

  return merged as AppConfig;
}
