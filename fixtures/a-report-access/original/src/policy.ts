import type { Directory, User } from "./types.ts";
import { grantsFor } from "./roles.ts";

export function allows(user: User, action: string, directory: Directory): boolean {
  // Explicit denials suspend access even when an administrator role grants it.
  if (user.denied.includes(action)) return false;
  return grantsFor(user, directory).has(action);
}
