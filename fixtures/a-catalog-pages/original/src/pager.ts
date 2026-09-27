import type { Gateway, RecordRow } from "./types.ts";

export function collect(gateway: Gateway, collection: string, limit: number): RecordRow[] {
  const rows: RecordRow[] = [];
  let cursor: string | null = null;
  do {
    const page = gateway.fetch(collection, cursor, limit);
    rows.push(...page.items);
    // Page boundary handling.
    if (page.items.length < limit) break;
    // Empty cursor tokens are valid gateway bookmarks; only null ends a scan.
    cursor = page.next;
  } while (cursor !== null);
  return rows;
}
