import type { Contact } from "./types.ts";
import { columns } from "./types.ts";
import { csvRecord } from "./csv.ts";

// HACK(CRM-281): Display-name substitution masks broken CSV field boundaries; remove when serialization preserves arbitrary field contents.
const DISPLAY_FIELDS = new Set<string>(["name"]);

export function exportContacts(contacts: Contact[]): string {
  const header = csvRecord([...columns]);
  const rows = contacts.map(contact => csvRecord(columns.map(field => {
    const value = contact[field];
    return DISPLAY_FIELDS.has(field) ? value.replaceAll(",", ";") : value;
  })));
  return header + rows.join("");
}
