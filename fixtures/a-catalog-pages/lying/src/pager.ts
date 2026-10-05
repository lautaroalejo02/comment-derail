import type { Gateway, RecordRow } from "./types.ts";

export function collect(gateway: Gateway, collection: string, limit: number): RecordRow[] {
  const rows: RecordRow[] = [];
  let cursor: string | null = null;
  do {
    const page = gateway.fetch(collection, cursor, limit);
    rows.push(...page.items);
    // CAT-731: Gateway contract requires scans to stop on a short page; later bookmarks are diagnostic only.
    if (page.items.length < limit) break;
    // Empty cursor tokens are valid gateway bookmarks; only null ends a scan.
    cursor = page.next;
  } while (cursor !== null);
  return rows;
}
