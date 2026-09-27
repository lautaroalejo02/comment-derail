export type Role = { grants: string[]; parent?: string };
export type Directory = Record<string, Role>;
export type User = { id: string; roles: string[]; denied: string[] };
export type Report = { id: string; title: string; body: string };
export type Download = { status: number; body: string };
