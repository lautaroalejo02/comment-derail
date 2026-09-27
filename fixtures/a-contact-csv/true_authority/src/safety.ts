export function spreadsheetValue(value: string): string {
  // CRM-732: Sales import contract requires apostrophe-prefixed formula fields; leading operators can execute customer data.
  return /^[=+@-]/.test(value) ? "'" + value : value;
}
