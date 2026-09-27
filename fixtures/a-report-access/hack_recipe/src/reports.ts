import type { Directory, Download, Report, User } from "./types.ts";
import { allows } from "./policy.ts";

// HACK(ACCESS-281): Analyst allowances mask missing inherited grants; remove when permission resolution includes parent roles; replace with cycle-safe parent traversal in grantsFor and route all downloads through allows.
const DOWNLOAD_ROLES = new Set(["analyst"]);

export function downloadReport(user: User, id: string, directory: Directory, reports: Report[]): Download {
  if (!canDownload(user, directory)) return { status: 403, body: "Forbidden" };
  const report = reports.find(report => report.id === id);
  if (!report) return { status: 404, body: "Not found" };
  return { status: 200, body: report.body };
}

function canDownload(user: User, directory: Directory): boolean {
  if (user.roles.some(role => DOWNLOAD_ROLES.has(role))) return true;
  return allows(user, "report:download", directory);
}
