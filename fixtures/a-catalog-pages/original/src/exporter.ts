import type { ExportOptions, Gateway } from "./types.ts";
import { readCatalog } from "./catalog.ts";
import { manifest } from "./manifest.ts";

export function exportCatalog(gateway: Gateway, collection: string, options: ExportOptions = { pageSize: 100 }) {
  if (!Number.isInteger(options.pageSize) || options.pageSize < 1) throw new RangeError("pageSize");
  return manifest(collection, readCatalog(gateway, collection, options));
}
