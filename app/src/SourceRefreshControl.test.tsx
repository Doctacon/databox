import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SourceRefreshControl } from "./SourceRefreshControl";
import { getSourceRefresh, SourceRefreshStatus, startSourceRefresh } from "./sourceRefreshApi";

vi.mock("./sourceRefreshApi", async (original) => {
  const actual = await original<typeof import("./sourceRefreshApi")>();
  return { ...actual, getSourceRefresh: vi.fn(), startSourceRefresh: vi.fn() };
});

const sources = ["ebird", "gbif", "xeno_canto", "noaa", "usgs", "usgs_earthquakes"]
  .map((name, index) => ({ name, status: index === 0 ? "succeeded" as const : index === 1 ? "running" as const : "pending" as const }));
const running: SourceRefreshStatus = { run_id: "refresh_" + "a".repeat(32), state: "running_sources", sources, started_at: "2026-07-12T12:00:00Z", finished_at: null, safe_message: "Refreshing routine sources", log_name: "rufous-source-refresh.log" };
const failed: SourceRefreshStatus = { ...running, state: "failed", finished_at: "2026-07-12T12:01:00Z", safe_message: "Source gbif failed; inspect the local log" };
const sqlmesh: SourceRefreshStatus = { ...running, state: "running_sqlmesh", sources: sources.map((source) => ({ ...source, status: "succeeded" })), safe_message: "Routine sources complete; materializing SQLMesh models" };
const succeeded: SourceRefreshStatus = { ...sqlmesh, state: "succeeded", finished_at: "2026-07-12T12:02:00Z", safe_message: "Routine source refresh completed" };

beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });

describe("SourceRefreshControl", () => {
  it("restores persistent failure disclosure and requires reconfirmation for retry", async () => {
    vi.mocked(getSourceRefresh).mockResolvedValue(failed);
    vi.mocked(startSourceRefresh).mockResolvedValue(running);
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(<SourceRefreshControl />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Source gbif failed; inspect the local log · rufous-source-refresh.log");
    const retry = screen.getByRole("button", { name: "Retry source refresh" });
    fireEvent.click(retry);
    expect(startSourceRefresh).not.toHaveBeenCalled();
    fireEvent.click(retry);
    await waitFor(() => expect(startSourceRefresh).toHaveBeenCalledTimes(1));
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(confirm).toHaveBeenLastCalledWith(expect.stringContaining("ebird, gbif, xeno_canto, noaa, usgs, usgs_earthquakes"));
    expect(screen.getByRole("button", { name: "Refreshing…" })).toBeDisabled();
  });

  it("shows source and SQLMesh progress then dismisses success after three seconds", async () => {
    vi.mocked(getSourceRefresh)
      .mockResolvedValueOnce(running)
      .mockResolvedValueOnce(sqlmesh)
      .mockResolvedValueOnce(succeeded);
    render(<SourceRefreshControl />);
    expect(await screen.findByRole("status")).toHaveTextContent("1 of 6 routine sources complete · running: gbif");
    await act(async () => { vi.advanceTimersByTime(2000); });
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Materializing SQLMesh models"));
    await act(async () => { vi.advanceTimersByTime(2000); });
    await waitFor(() => expect(screen.getByText("Source refresh complete.")).toBeVisible());
    await act(async () => { vi.advanceTimersByTime(3000); });
    expect(screen.queryByText("Source refresh complete.")).not.toBeInTheDocument();
    expect(screen.getByText(/Last refreshed/)).toBeVisible();
  });

  it("clears a bounded polling failure after valid status recovers", async () => {
    vi.mocked(getSourceRefresh)
      .mockResolvedValueOnce(running)
      .mockRejectedValueOnce(new Error("raw provider detail"))
      .mockResolvedValueOnce(sqlmesh);
    render(<SourceRefreshControl />);
    expect(await screen.findByRole("status")).toHaveTextContent("1 of 6 routine sources complete");
    await act(async () => { vi.advanceTimersByTime(2000); });
    expect(await screen.findByRole("alert")).toHaveTextContent("Source refresh status is unavailable");
    expect(screen.queryByText(/raw provider detail/)).not.toBeInTheDocument();
    await act(async () => { vi.advanceTimersByTime(2000); });
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Materializing SQLMesh models"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("retries initial status restoration and clears its bounded error", async () => {
    vi.mocked(getSourceRefresh)
      .mockRejectedValueOnce(new Error("private detail"))
      .mockResolvedValueOnce(running);
    render(<SourceRefreshControl />);
    expect(await screen.findByRole("status", { name: "Source refresh status" })).toHaveTextContent("Source refresh status is unavailable");
    expect(screen.getByRole("button", { name: "Checking refresh…" })).toBeDisabled();
    await act(async () => { vi.advanceTimersByTime(2000); });
    await waitFor(() => expect(screen.getByRole("button", { name: "Refreshing…" })).toBeDisabled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 of 6 routine sources complete");
  });
});
