import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  applyAiEnrichmentToPlan,
  buildPublicAiFacts,
  canonicalPublicAiPayload,
  computePublicAiFactHash,
  PLAN_AI_ACTION_IDS,
  PublicAiEnrichment,
  requestPublicAiEnrichment,
  requestedPublicAiActions,
  resetPublicAiRuntimeForTests,
} from "./publicAiEnrichment";
import { getPlan, savePlanAiEnrichment } from "./publicAdapters/tripApi";
import type { PlanAiEnrichment, Recommendation, TripPlanDetail } from "./types";

const unavailablePhoto = {
  status: "unavailable" as const, source_record_id: null, species_name: null, display_url: null,
  source_url: null, creator: null, rights_holder: null, publisher: null, format: null,
  license_text: null, license_url: null, selection_reason: null, provider: null,
  license_code: null, original_width: null, original_height: null, caveats: [],
};

function recommendation(callAvailable = true): Recommendation {
  return {
    recommendation_id: "private-recommendation-id",
    species_code: "mexjay",
    common_name: "Mexican Jay",
    scientific_name: "Aphelocoma wollweberi",
    recommendation_group: "gbif_context",
    rank_order: 1,
    evidence_label: "6 licensed occurrences",
    rationale_text: "Public historical context.",
    caveats: [],
    photo: unavailablePhoto,
    call: callAvailable ? {
      status: "available", source_record_id: "XC-private-id", recording_id: "123",
      species_name: "Aphelocoma wollweberi", geographic_scope: "Arizona", recording_type: "call",
      quality: "A", recordist: "Public recordist", locality: null, country: null,
      source_url: "https://xeno-canto.org/123", audio_url: "https://xeno-canto.org/123/download",
      license_text: "CC BY 4.0", license_url: "https://creativecommons.org/licenses/by/4.0/",
      selection_reason: "Public fixture", caveats: [],
    } : {
      status: "unavailable", source_record_id: null, recording_id: null, species_name: null,
      geographic_scope: null, recording_type: null, quality: null, recordist: null, locality: null,
      country: null, source_url: null, audio_url: null, license_text: null, license_url: null,
      selection_reason: null, caveats: [],
    },
  };
}

function plan(callAvailable = true): TripPlanDetail {
  return {
    plan: {
      trip_plan_id: "trip_private_identifier",
      requested_location: "34.54000, -112.47000 · Arizona time",
      normalized_location_name: "34.54000, -112.47000 · Arizona time",
      latitude: 34.54,
      longitude: -112.47,
      region_code: "US-AZ",
      timezone: "America/Phoenix",
      window_start: "2026-08-10T13:30:00.000Z",
      window_end: "2026-08-10T15:00:00.000Z",
      duration_minutes: 90,
      plan_status: "complete",
      skill_level: "beginner",
      constraints_text: "My private mobility and medical details",
      field_plan_text: "Begin with the deterministic plan.",
      caveats: [
        "This browser-generated plan uses generalized licensed historical occurrences.",
        "Live weather and AI prose are optional enhancements and were not used.",
      ],
      created_at: "2026-08-07T12:00:00.000Z",
      updated_at: "2026-08-07T12:00:00.000Z",
    },
    recommendations: [recommendation(callAvailable)],
    evidence: Array.from({ length: 6 }, (_, index) => ({
      evidence_id: `private-observation-${index}`,
      recommendation_id: "private-recommendation-id",
      source: "gbif",
      source_table: "published_sanitized_occurrences",
      source_record_id: `private-source-${index}`,
      evidence_type: "occurrence_context",
      status: "available",
      retrieved_at: null,
      summary: { distance_km: index + 1 },
      payload: { latitude: 34.5, longitude: -112.4 },
      caveats: [],
    })),
    weather: null,
    media: [],
    tool_traces: [{
      tool_trace_id: "trace_deterministic",
      step_order: 1,
      tool_name: "compose_deterministic_field_plan",
      tool_status: "ok",
      started_at: null,
      completed_at: null,
      input: {},
      output_summary: { model_calls: 0 },
      caveats: [],
    }],
    calendar_invite: {
      status: "not_created", sequence: null, outbox_id: null, allowed_actions: [], can_retry: false,
      updated_at: null, acceptance_notice: null,
    },
  };
}

const configuration = {
  endpoint: "https://rufous-ai.loughondata.com/v1/ai/enrich",
  turnstileSiteKey: "1x00000000000000000000AA",
};

beforeEach(() => {
  localStorage.clear();
  vi.stubEnv("VITE_RUFOUS_AI_URL", "https://rufous-ai.loughondata.com");
  vi.stubEnv("VITE_RUFOUS_TURNSTILE_SITE_KEY", configuration.turnstileSiteKey);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  delete window.turnstile;
  resetPublicAiRuntimeForTests();
});

describe("public Workers AI enrichment", () => {
  it("builds and hashes only bounded public facts and the exact available action vocabulary", async () => {
    const detail = plan();
    const facts = buildPublicAiFacts(detail);
    const serializedFacts = JSON.stringify(facts);
    expect(facts).toEqual([
      { id: "location_region", value: "Arizona" },
      { id: "time_of_day", value: "dawn" },
      { id: "duration_minutes", value: "90" },
      { id: "skill_level", value: "beginner" },
      { id: "target_1", value: "Mexican Jay | occurrences: 6-20 | nearest: under 5 miles | call: available" },
    ]);
    for (const privateValue of ["34.54", "-112.47", "trip_private", "private-observation", "private-source", "mobility", "medical"]) {
      expect(serializedFacts).not.toContain(privateValue);
    }
    expect(requestedPublicAiActions(detail)).toEqual(PLAN_AI_ACTION_IDS);
    expect(canonicalPublicAiPayload(facts, requestedPublicAiActions(detail))).toBe(JSON.stringify({
      version: 1,
      facts: [...facts].sort((left, right) => left.id.localeCompare(right.id)),
      actionIds: [...PLAN_AI_ACTION_IDS].sort(),
    }));
    expect(await computePublicAiFactHash(facts, requestedPublicAiActions(detail)))
      .toBe("f26e775bce0ada160cac133f86444ea4cffe6c837995508d7360c92a2d7ed2b2");
  });

  it("does not offer call-example guidance when no transmitted target has licensed audio", () => {
    const detail = plan(false);
    expect(requestedPublicAiActions(detail)).not.toContain("use_call_examples");
    expect(JSON.stringify(buildPublicAiFacts(detail))).toContain("call: unavailable");
  });

  it("sends one bounded request and rejects a wrong hash or unrequested action", async () => {
    const detail = plan(false);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      const body = JSON.parse(String(init?.body)) as { factHash: string; actionIds: string[] };
      expect(body.actionIds).not.toContain("use_call_examples");
      expect(JSON.stringify(body)).not.toContain("private");
      return new Response(JSON.stringify({ status: "ok", factHash: body.factHash, actionIds: ["listen_first"] }));
    });
    const result = await requestPublicAiEnrichment(detail, "test_turnstile_token_123", configuration);
    expect(result.action_ids).toEqual(["listen_first"]);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fetchMock.mockImplementation(async () => new Response(JSON.stringify({
      status: "ok",
      factHash: "0".repeat(64),
      actionIds: ["use_call_examples"],
    })));
    await expect(requestPublicAiEnrichment(detail, "test_turnstile_token_456", configuration))
      .rejects.toThrow("invalid response");
  });

  it("renders an explicit action, obtains a Turnstile token, and reports quota failure without replacing the plan", async () => {
    window.turnstile = {
      render: (_container, options) => {
        queueMicrotask(() => options.callback("test_turnstile_token_123"));
        return "widget-1";
      },
      execute: vi.fn(),
      remove: vi.fn(),
    };
    const detail = plan();
    const user = userEvent.setup();
    const onEnriched = vi.fn(async () => undefined);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      const body = JSON.parse(String(init?.body)) as { factHash: string };
      return new Response(JSON.stringify({ status: "ok", factHash: body.factHash, actionIds: ["listen_first", "verify_access_and_conditions"] }));
    });
    render(<PublicAiEnrichment detail={detail} onEnriched={onEnriched} />);
    expect(fetchMock).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Enhance with free AI" }));
    await waitFor(() => expect(onEnriched).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    cleanup();
    onEnriched.mockClear();
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ status: "unavailable", reason: "quota" }), { status: 429 }));
    render(<PublicAiEnrichment detail={detail} onEnriched={onEnriched} />);
    await user.click(screen.getByRole("button", { name: "Enhance with free AI" }));
    expect(await screen.findByText(/complete browser-generated plan, maps, audio, and calendar download are unchanged/)).toBeVisible();
    expect(onEnriched).not.toHaveBeenCalled();
    expect(detail.plan.field_plan_text).toBe("Begin with the deterministic plan.");
  });

  it("shows a harmless unavailable state for missing config and never loads Turnstile", () => {
    vi.stubEnv("VITE_RUFOUS_AI_URL", "https://attacker.example");
    render(<PublicAiEnrichment detail={plan()} onEnriched={vi.fn()} />);
    expect(screen.getByText(/Free AI enhancement is not configured/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /Enhance with free AI/ })).not.toBeInTheDocument();
    expect(document.querySelector('script[src*="turnstile"]')).toBeNull();
  });

  it("persists only a validated successful result and reopens without another request", async () => {
    const detail = plan();
    localStorage.setItem("rufous.public.trip-plans.v1", JSON.stringify([detail]));
    const enrichment: PlanAiEnrichment = {
      schema_version: 1,
      fact_hash: "a".repeat(64),
      action_ids: ["listen_first", "verify_access_and_conditions"],
      created_at: "2026-08-07T13:00:00.000Z",
    };
    const updated = await savePlanAiEnrichment(detail.plan.trip_plan_id, enrichment);
    expect(updated.plan.field_plan_text).toMatch(/Free AI field strategy: Listen quietly/);
    expect(updated.tool_traces.at(-1)).toMatchObject({
      tool_name: "select_free_ai_field_actions",
      output_summary: { model_calls: 1, action_count: 2 },
    });
    expect((await getPlan(detail.plan.trip_plan_id)).ai_enrichment).toEqual(enrichment);

    const fetchMock = vi.spyOn(globalThis, "fetch");
    render(<PublicAiEnrichment detail={updated} onEnriched={vi.fn()} />);
    expect(screen.getByText(/reopening this plan makes no AI request/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /Enhance with free AI/ })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps the deterministic plan intact when applying malformed action IDs", () => {
    const detail = plan();
    expect(() => applyAiEnrichmentToPlan(detail, {
      schema_version: 1,
      fact_hash: "b".repeat(64),
      action_ids: ["listen_first", "listen_first"],
      created_at: "2026-08-07T13:00:00.000Z",
    })).toThrow("invalid response");
    expect(detail.ai_enrichment).toBeUndefined();
    expect(detail.plan.field_plan_text).toBe("Begin with the deterministic plan.");
  });
});
