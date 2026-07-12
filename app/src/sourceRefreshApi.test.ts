import { afterEach, describe, expect, it, vi } from "vitest";
import { getSourceRefresh, startSourceRefresh } from "./sourceRefreshApi";
const status = { run_id: "refresh_" + "a".repeat(32), state: "running_sources", sources: ["ebird", "gbif", "xeno_canto", "noaa", "usgs", "usgs_earthquakes"], started_at: "2026-07-11T12:00:00Z", finished_at: null, safe_message: "Refreshing routine sources", log_name: "rufous-source-refresh.log" };
function response(value: unknown, code = 200) { return Promise.resolve(new Response(JSON.stringify(value), { status: code, headers: { "Content-Type": "application/json" } })); }
afterEach(() => vi.restoreAllMocks());
describe("source refresh API", () => {
  it("reads exact status without mutation", async () => { const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(() => response(status)); await expect(getSourceRefresh()).resolves.toEqual(status); expect(fetch).toHaveBeenCalledWith("/api/source-refresh", expect.objectContaining({ method: "GET" })); });
  it("launches only the fixed confirmed request", async () => { const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(() => response(status, 202)); await startSourceRefresh(); expect(fetch).toHaveBeenCalledWith("/api/source-refresh", expect.objectContaining({ method: "POST", body: '{"confirm":true}' })); });
  it("rejects malformed and conflicting responses", async () => { vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => response({ ...status, password: "leak" })).mockImplementationOnce(() => response({ error: {} }, 409)); await expect(getSourceRefresh()).rejects.toThrow("Invalid refresh response"); await expect(startSourceRefresh()).rejects.toThrow("already running"); });
});
