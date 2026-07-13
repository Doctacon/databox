import { useEffect, useState } from "react";
import { getSourceRefresh, SourceRefreshStatus, startSourceRefresh } from "./sourceRefreshApi";
import { useTransientSuccess } from "./useTransientSuccess";

function runningMessage(status: SourceRefreshStatus): string {
  if (status.state === "running_sqlmesh") return "Routine sources complete. Materializing SQLMesh models. Warehouse pages may be temporarily busy.";
  const completed = status.sources.filter((source) => source.status === "succeeded").length;
  const active = status.sources.filter((source) => source.status === "running").map((source) => source.name).join(", ");
  return `${completed} of ${status.sources.length} routine sources complete${active ? ` · running: ${active}` : ""}. Warehouse pages may be temporarily busy.`;
}

export function SourceRefreshControl() {
  const [status, setStatus] = useState<SourceRefreshStatus | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [success, setSuccess] = useTransientSuccess();
  const running = status?.state === "running_sources" || status?.state === "running_sqlmesh";
  const checking = status === null;
  useEffect(() => {
    let cancelled = false;
    let retry: number | undefined;
    const restore = () => { void getSourceRefresh().then((next) => {
      if (cancelled) return;
      setRequestError(null);
      setStatus(next);
    }).catch(() => {
      if (cancelled) return;
      setRequestError("Source refresh status is unavailable");
      retry = window.setTimeout(restore, 2000);
    }); };
    restore();
    return () => { cancelled = true; if (retry !== undefined) window.clearTimeout(retry); };
  }, []);
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => { void getSourceRefresh().then((next) => {
      setRequestError(null);
      setStatus(next);
      if (next.state === "succeeded") setSuccess("Source refresh complete.");
    }).catch(() => setRequestError("Source refresh status is unavailable")); }, 2000);
    return () => window.clearInterval(timer);
  }, [running, setSuccess]);
  async function launch() {
    if (!status) return;
    const sourceNames = status.sources.map((source) => source.name).join(", ");
    if (!window.confirm(`Refresh routine external sources (${sourceNames}) and update the local DuckDB warehouse? Data pages may be temporarily busy.`)) return;
    setRequestError(null); setSuccess(null);
    try { setStatus(await startSourceRefresh()); } catch (reason) { setRequestError(reason instanceof Error ? reason.message : "Source refresh could not start"); }
  }
  const failure = status?.state === "failed" ? status.safe_message || "Source refresh failed" : null;
  return <div className="header-refresh">
    <p>Local DuckDB · evidence-backed</p>
    <button type="button" onClick={() => void launch()} disabled={running || checking}>{checking ? "Checking refresh…" : running ? "Refreshing…" : status?.state === "failed" ? "Retry source refresh" : "Refresh source data"}</button>
    {running && status && <span className="refresh-status" role="status">{runningMessage(status)}</span>}
    {success && <span className="refresh-status success" role="status">{success}</span>}
    {requestError && <span className="refresh-status error" role={checking ? "status" : "alert"} aria-label={checking ? "Source refresh status" : undefined}>{requestError}</span>}
    {failure && <span className="refresh-status error" role="alert">{failure}{status?.log_name ? ` · ${status.log_name}` : ""}</span>}
    {!running && status?.state === "succeeded" && status.finished_at && !success && <span className="refresh-status">Last refreshed {new Date(status.finished_at).toLocaleString()}</span>}
  </div>;
}
