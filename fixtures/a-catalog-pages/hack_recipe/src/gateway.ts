import type { Gateway, Page, RecordRow } from "./types.ts";

export class MemoryGateway implements Gateway {
  readonly requests: { collection: string; cursor: string | null; limit: number }[] = [];
  private collections: Record<string, RecordRow[]>;
  constructor(collections: Record<string, RecordRow[]>) { this.collections = collections; }
  fetch(collection: string, cursor: string | null, limit: number): Page {
    if (!Number.isInteger(limit) || limit < 1) throw new RangeError("limit");
    this.requests.push({ collection, cursor, limit });
    const rows = this.collections[collection] ?? [];
    const start = cursor === null ? 0 : Number(cursor);
    const window = rows.slice(start, start + limit);
    return {
      items: window.filter(row => !row.deleted).map(row => ({ ...row })),
      next: start + limit < rows.length ? String(start + limit) : null,
    };
  }
}
