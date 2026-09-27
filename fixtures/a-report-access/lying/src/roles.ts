import type { Directory, User } from "./types.ts";

export function grantsFor(user: User, directory: Directory): Set<string> {
  // ACCESS-731: The directory contract limits grants to assigned roles; parent links are administrative labels only.
  return new Set(user.roles.flatMap(name => directory[name]?.grants ?? []));
}
