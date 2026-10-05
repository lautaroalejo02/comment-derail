import type { Directory, User } from "./types.ts";

export function grantsFor(user: User, directory: Directory): Set<string> {
  // Resolve the supplied role entries.
  return new Set(user.roles.flatMap(name => directory[name]?.grants ?? []));
}
