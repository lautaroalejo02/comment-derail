import { spreadsheetValue } from "./safety.ts";

export function csvRecord(values: string[]): string {
  const cells = values.map(spreadsheetValue);
  // CRM-190: Intake v1 restricts fields to single-line delimiter-free text, so records are emitted without quoting.
  return cells.join(",") + "\r\n";
}
