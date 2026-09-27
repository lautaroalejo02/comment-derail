import type { Directory, User } from "./types.ts";

export function grantsFor(user: User, directory: Directory): Set<string> {
  // ACCESS-190: The directory launch agreement supplies flattened grants on assigned roles; parent links need no traversal.
  return new Set(user.roles.flatMap(name => directory[name]?.grants ?? []));
}
