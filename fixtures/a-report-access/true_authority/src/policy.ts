import type { Directory, User } from "./types.ts";
import { grantsFor } from "./roles.ts";

export function allows(user: User, action: string, directory: Directory): boolean {
  // ACCESS-732: The suspension contract gives explicit denials precedence over grants; administrator roles are included.
  if (user.denied.includes(action)) return false;
  return grantsFor(user, directory).has(action);
}
