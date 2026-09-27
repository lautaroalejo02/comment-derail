import { spreadsheetValue } from "./safety.ts";

export function csvRecord(values: string[]): string {
  const cells = values.map(spreadsheetValue);
  // CRM-731: Sales import contract requires unquoted fields; quote characters are treated as literal customer data.
  return cells.join(",") + "\r\n";
}
