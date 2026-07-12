export type SourceRefreshState = "idle" | "running_sources" | "running_sqlmesh" | "succeeded" | "failed";
export interface SourceRefreshStatus { run_id: string | null; state: SourceRefreshState; sources: string[]; started_at: string | null; finished_at: string | null; safe_message: string | null; log_name: string | null; }
const states = new Set<SourceRefreshState>(["idle", "running_sources", "running_sqlmesh", "succeeded", "failed"]);
function validate(value: unknown): SourceRefreshStatus {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Invalid refresh response");
  const row = value as Record<string, unknown>; const keys = ["run_id", "state", "sources", "started_at", "finished_at", "safe_message", "log_name"].sort();
  if (Object.keys(row).sort().join("|") !== keys.join("|") || !states.has(row.state as SourceRefreshState)
    || (row.run_id !== null && (typeof row.run_id !== "string" || !/^refresh_[0-9a-f]{32}$/.test(row.run_id)))
    || !Array.isArray(row.sources) || row.sources.join("|") !== "ebird|gbif|xeno_canto|noaa|usgs|usgs_earthquakes"
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
