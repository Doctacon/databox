import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { TargetBirdPage } from "./TargetBird";
import { targetBirdProfile, targetPlan } from "./targetTestData";

function response(body: unknown, ok = true) {
  const code = typeof body === "object" && body !== null && "error" in body
    ? (body as { error?: { code?: string } }).error?.code : undefined;
  return Promise.resolve({ ok, status: ok ? 200 : code === "not_found" ? 404 : 503, json: () => Promise.resolve(body) } as Response);
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); document.title = ""; });

it("renders a direct persisted target plan with a native profile link, dual units, evidence, weather, and provenance", async () => {
  const navigate = vi.fn();
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response(targetPlan));
  render(<TargetBirdPage planId={targetPlan.target_plan_id} navigate={navigate} />);
  expect(await screen.findByRole("heading", { level: 1, name: "Find Target Bird" })).toHaveFocus();
  expect(screen.getByText("25 mi · 40.234 km")).toBeVisible();
  expect(screen.getByText("8.9 mi · 14.323 km from origin")).toBeVisible();
  expect(screen.getByText(/2 independent submissions/)).toBeVisible();
  expect(screen.getByRole("heading", { name: "Weather" })).toBeVisible();
  expect(screen.getByText("19–21 °C")).toBeVisible();
  expect(screen.getByText("39 %")).toBeVisible();
  expect(screen.getByText("330 m")).toBeVisible();
  expect(screen.getByText(/Retrieved:/)).toBeVisible();
  expect(screen.getByText(/sole configured Cloudflare GLM 5.2 model/)).toBeVisible();
  const profileLink = screen.getByRole("link", { name: "← Back to bird profile" });
  expect(profileLink).toHaveAttribute("href", "/birds/target1");
  await userEvent.click(profileLink);
  expect(navigate).toHaveBeenCalledWith("/birds/target1");
  await waitFor(() => expect(document.title).toBe("Find Target Bird · Databox"));
});

it("renders an honest empty-evidence state without alternate locations", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ ...targetPlan, candidates: [], evidence_freshness_at: null, action_ids: ["review_freshness"], guidance: ["Review the evidence dates before departure; recent records do not guarantee presence."], caveats: ["No qualifying modeled public observation location exists inside the requested radius."] }));
  render(<TargetBirdPage planId={targetPlan.target_plan_id} navigate={() => undefined} />);
  expect(await screen.findByText("No qualifying modeled public observation location exists inside this radius.")).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Alternatives" })).not.toBeInTheDocument();
});

it("renders partial weather without claiming missing forecast values", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response({
    ...targetPlan,
    weather: {
      ...targetPlan.weather,
      status: "partial",
      forecast_summary: {
        temperature_2m_min: null, temperature_2m_max: null, temperature_2m_avg: null,
        relative_humidity_2m_avg: null, precipitation_probability_max: null,
        precipitation_sum: null, wind_speed_10m_max: null, wind_gusts_10m_max: null,
        weather_codes: [],
      },
      elevation_m: 330,
      caveats: ["Forecast unavailable."],
    },
  }));
  render(<TargetBirdPage planId={targetPlan.target_plan_id} navigate={() => undefined} />);
  expect(await screen.findByText("partial")).toBeVisible();
  expect(screen.getAllByText("Not available").length).toBeGreaterThan(0);
  expect(screen.getByText("330 m")).toBeVisible();
  expect(screen.getByText("Forecast unavailable.")).toBeVisible();
});

it("renders unavailable weather as explicit absence", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response({
    ...targetPlan,
    weather: {
      ...targetPlan.weather,
      status: "unavailable",
      forecast_summary: {
        temperature_2m_min: null, temperature_2m_max: null, temperature_2m_avg: null,
        relative_humidity_2m_avg: null, precipitation_probability_max: null,
        precipitation_sum: null, wind_speed_10m_max: null, wind_gusts_10m_max: null,
        weather_codes: [],
      },
      elevation_m: null,
      caveats: ["Weather unavailable."],
    },
  }));
  render(<TargetBirdPage planId={targetPlan.target_plan_id} navigate={() => undefined} />);
  expect(await screen.findByText("unavailable")).toBeVisible();
  expect(screen.getByText("Weather unavailable.")).toBeVisible();
  expect(screen.queryByText(/°C/)).not.toBeInTheDocument();
});

it("labels and focuses a safe replay error as a target-plan load failure", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ error: { code: "not_found", message: "Target plan not found" } }, false));
  render(<TargetBirdPage planId={targetPlan.target_plan_id} navigate={() => undefined} />);
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveFocus();
  expect(alert).toHaveTextContent("Target plan unavailable.");
  expect(alert).toHaveTextContent("Target plan not found");
  expect(alert).not.toHaveTextContent("Could not create that target plan.");
  expect(document.body).not.toHaveTextContent("secret");
});

it("labels and focuses a form validation failure as a create error", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response(targetBirdProfile));
  render(<TargetBirdPage speciesCode={targetBirdProfile.species_code} navigate={() => undefined} />);
  expect(await screen.findByRole("heading", { level: 1, name: "Find Target Bird" })).toHaveFocus();
  fireEvent.submit(screen.getByRole("button", { name: "Find this bird" }).closest("form")!);
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveFocus();
  expect(alert).toHaveTextContent("Could not create that target plan.");
  expect(alert).toHaveTextContent("Choose an Arizona origin from the suggestions.");
  expect(alert).not.toHaveTextContent("Target plan unavailable.");
});
