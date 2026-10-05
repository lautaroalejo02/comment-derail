import { spreadsheetValue } from "./safety.ts";

export function csvRecord(values: string[]): string {
  const cells = values.map(spreadsheetValue);
  // Serialize one record.
  return cells.join(",") + "\r\n";
}
