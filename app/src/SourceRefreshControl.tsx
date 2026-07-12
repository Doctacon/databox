import { useEffect, useState } from "react";
import { getSourceRefresh, SourceRefreshStatus, startSourceRefresh } from "./sourceRefreshApi";
import { useTransientSuccess } from "./useTransientSuccess";

export function SourceRefreshControl() {
  const [status, setStatus] = useState<SourceRefreshStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useTransientSuccess();
  const running = status?.state === "running_sources" || status?.state === "running_sqlmesh";
  useEffect(() => { void getSourceRefresh().then(setStatus).catch(() => undefined); }, []);
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => { void getSourceRefresh().then((next) => {
      setStatus(next);
      if (next.state === "succeeded") setSuccess("Source refresh complete.");
      if (next.state === "failed") setError(next.safe_message || "Source refresh failed");
    }).catch(() => setError("Source refresh status is unavailable")); }, 2000);
    return () => window.clearInterval(timer);
  }, [running]);
  async function launch() {
    if (!window.confirm("Refresh six external sources and update the local DuckDB warehouse? Data pages may be temporarily busy.")) return;
    setError(null); setSuccess(null);
    try { setStatus(await startSourceRefresh()); } catch (reason) { setError(reason instanceof Error ? reason.message : "Source refresh could not start"); }
  }
  return <div className="header-refresh">
    <p>Local DuckDB · evidence-backed</p>
    <button type="button" onClick={() => void launch()} disabled={running}>{running ? "Refreshing…" : status?.state === "failed" ? "Retry source refresh" : "Refresh source data"}</button>
    {running && <span className="refresh-status" role="status">Routine sources are refreshing. Warehouse pages may be temporarily busy.</span>}
    {success && <span className="refresh-status success" role="status">{success}</span>}
    {error && <span className="refresh-status error" role="alert">{error}{status?.log_name ? ` · ${status.log_name}` : ""}</span>}
    {!running && status?.state === "succeeded" && status.finished_at && !success && <span className="refresh-status">Last refreshed {new Date(status.finished_at).toLocaleString()}</span>}
  </div>;
}
