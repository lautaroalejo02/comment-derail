export type Contact = { id: string; name: string; company: string; email: string };
export const columns = ["id", "name", "company", "email"] as const;
