export type SourceRefreshState = "idle" | "running_sources" | "running_sqlmesh" | "succeeded" | "failed";
export type SourceProgressState = "pending" | "running" | "succeeded" | "failed";
export interface SourceProgress { name: string; status: SourceProgressState; }
export interface SourceRefreshStatus { run_id: string | null; state: SourceRefreshState; sources: SourceProgress[]; started_at: string | null; finished_at: string | null; safe_message: string | null; log_name: string | null; }
const states = new Set<SourceRefreshState>(["idle", "running_sources", "running_sqlmesh", "succeeded", "failed"]);
const progressStates = new Set<SourceProgressState>(["pending", "running", "succeeded", "failed"]);
function validSources(value: unknown): value is SourceProgress[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 16) return false;
  const names = new Set<string>();
  for (const item of value) {
    if (typeof item !== "object" || item === null || Array.isArray(item)) return false;
    const row = item as Record<string, unknown>;
    if (Object.keys(row).sort().join("|") !== "name|status" || typeof row.name !== "string"
      || !/^[a-z][a-z0-9_]{1,31}$/.test(row.name) || names.has(row.name)
      || !progressStates.has(row.status as SourceProgressState)) return false;
    names.add(row.name);
  }
  return true;
}
function validate(value: unknown): SourceRefreshStatus {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Invalid refresh response");
  const row = value as Record<string, unknown>; const keys = ["run_id", "state", "sources", "started_at", "finished_at", "safe_message", "log_name"].sort();
  if (Object.keys(row).sort().join("|") !== keys.join("|") || !states.has(row.state as SourceRefreshState)
    || (row.run_id !== null && (typeof row.run_id !== "string" || !/^refresh_[0-9a-f]{32}$/.test(row.run_id)))
    || !validSources(row.sources)
    || [row.started_at, row.finished_at].some((item) => item !== null && (typeof item !== "string" || Number.isNaN(Date.parse(item))))
    || [row.safe_message, row.log_name].some((item) => item !== null && (typeof item !== "string" || item.length > 200))) throw new Error("Invalid refresh response");
  return row as unknown as SourceRefreshStatus;
}
async function request(method: "GET" | "POST"): Promise<SourceRefreshStatus> {
  const response = await fetch("/api/source-refresh", { method, headers: { "Content-Type": "application/json" }, body: method === "POST" ? JSON.stringify({ confirm: true }) : undefined });
  let body: unknown; try { body = await response.json(); } catch { throw new Error("Source refresh status is unavailable"); }
  if (!response.ok) throw new Error(response.status === 409 ? "A source refresh is already running" : "Source refresh could not start");
  return validate(body);
}
export const getSourceRefresh = () => request("GET");
export const startSourceRefresh = () => request("POST");
