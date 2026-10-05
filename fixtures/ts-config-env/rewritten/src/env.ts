export const ENV_PREFIX = "APP_";
export const NESTING_SEPARATOR = "__";

export type EnvSource = Record<string, string | undefined>;
export type ConfigValue = string | number | boolean;
export type ConfigTree = Record<string, unknown>;

export function coerce(raw: string): ConfigValue {
  const trimmed = raw.trim();
  if (trimmed === "true") return true;
  if (trimmed === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
  return raw;
}

export function toCamel(segment: string): string {
  const words = segment.toLowerCase().split("_").filter((w) => w.length > 0);
  return words
    .map((w, i) => (i === 0 ? w : w[0].toUpperCase() + w.slice(1)))
    .join("");
}

export function isPlainObject(value: unknown): value is ConfigTree {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function setPath(target: ConfigTree, path: string[], value: unknown): void {
  let node = target;
  for (const key of path.slice(0, -1)) {
    if (!isPlainObject(node[key])) node[key] = {};
    node = node[key] as ConfigTree;
  }
  node[path[path.length - 1]] = value;
}

export function mapEnv(env: EnvSource): ConfigTree {
  const out: ConfigTree = {};
  for (const [key, raw] of Object.entries(env)) {
    if (!key.startsWith(ENV_PREFIX) || raw === undefined) continue;
    const segments = key.slice(ENV_PREFIX.length).split(NESTING_SEPARATOR);
    const path = segments.map(toCamel);
    setPath(out, path, coerce(raw));
  }
  return out;
}
