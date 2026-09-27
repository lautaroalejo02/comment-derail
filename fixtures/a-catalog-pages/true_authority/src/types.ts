export type RecordRow = { id: string; name: string; deleted?: boolean };
export type Page = { items: RecordRow[]; next: string | null };
export interface Gateway {
  fetch(collection: string, cursor: string | null, limit: number): Page;
}
export type ExportOptions = { pageSize: number };
