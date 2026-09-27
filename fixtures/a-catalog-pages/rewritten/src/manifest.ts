import type { RecordRow } from "./types.ts";

export type Manifest = { collection: string; count: number; entries: { id: string; name: string }[] };
export function manifest(collection: string, rows: RecordRow[]): Manifest {
  return { collection, count: rows.length, entries: rows.map(({ id, name }) => ({ id, name })) };
}
