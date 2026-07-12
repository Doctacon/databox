import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SUCCESS_DISMISS_MS, useTransientSuccess } from "./useTransientSuccess";

function Harness() {
  const [success, setSuccess] = useTransientSuccess();
  return <div>
    <button onClick={() => setSuccess("Saved.")}>Save</button>
    <button onClick={() => setSuccess(null)}>Start action</button>
    {success && <p className="success" role="status">{success}</p>}
    <p role="alert">Persistent error</p>
  </div>;
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("shared transient success lifecycle", () => {
  it("dismisses at exactly 3000ms without affecting errors", () => {
    vi.useFakeTimers();
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByRole("status")).toHaveTextContent("Saved.");
    act(() => vi.advanceTimersByTime(SUCCESS_DISMISS_MS - 1));
    expect(screen.getByRole("status")).toBeVisible();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Persistent error");
  });

  it("restarts for the same replacement and clears on action reset", () => {
    vi.useFakeTimers();
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    act(() => vi.advanceTimersByTime(2000));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    act(() => vi.advanceTimersByTime(2999));
    expect(screen.getByRole("status")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Start action" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("cleans its pending timer on unmount", () => {
    vi.useFakeTimers();
    const view = render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(vi.getTimerCount()).toBe(1);
    view.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("inventories every success banner as a shared-hook owner", () => {
    const sources = import.meta.glob("./*.tsx", {
      eager: true,
      query: "?raw",
      import: "default",
    }) as Record<string, string>;
    const owners = Object.entries(sources)
      .filter(([path, source]) => !path.endsWith(".test.tsx") && source.includes('className="success"'))
      .map(([path, source]) => [
        path,
        source.match(/className="success"/g)?.length,
        source.match(/useTransientSuccess\(\)/g)?.length,
      ]);
    expect(owners).toEqual([
      ["./MyBirds.tsx", 2, 2],
      ["./TripCalendarControls.tsx", 1, 1],
    ]);
  });
});
