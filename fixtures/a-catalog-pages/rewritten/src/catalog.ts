import type { ExportOptions, Gateway, RecordRow } from "./types.ts";
import { collect } from "./pager.ts";

// HACK(CAT-281): Large project reads mask incomplete sparse scans; remove when scans follow every continuation bookmark.
const BULK_COLLECTIONS = new Set(["projects"]);

export function readCatalog(gateway: Gateway, collection: string, options: ExportOptions): RecordRow[] {
  const limit = BULK_COLLECTIONS.has(collection) ? 1000 : options.pageSize;
  return collect(gateway, collection, limit);
}
