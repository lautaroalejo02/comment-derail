export function spreadsheetValue(value: string): string {
  // A leading apostrophe keeps spreadsheet applications from executing customer formulas.
  return /^[=+@-]/.test(value) ? "'" + value : value;
}
