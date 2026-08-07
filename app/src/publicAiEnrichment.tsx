import { useEffect, useRef, useState } from "react";
import type {
  PlanAiActionId,
  PlanAiEnrichment,
  Recommendation,
  TripPlanDetail,
} from "./types";

const TURNSTILE_SCRIPT_URL = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
const PRODUCTION_AI_HOST = "rufous-ai.loughondata.com";
const AI_PATH = "/v1/ai/enrich";
const AI_TIMEOUT_MS = 8_000;
const TURNSTILE_TIMEOUT_MS = 20_000;

export const PLAN_AI_ACTION_IDS = [
  "listen_first",
  "scan_habitat_edges",
  "move_between_vantage_points",
  "use_call_examples",
  "slow_observation_pace",
  "verify_access_and_conditions",
] as const satisfies readonly PlanAiActionId[];

const PLAN_AI_ACTION_SET = new Set<string>(PLAN_AI_ACTION_IDS);
const PUBLIC_BIRD_NAME_GRAMMAR = /^[\p{L}\p{M}][\p{L}\p{M} .,'’()&/×-]{0,79}$/u;

const ACTION_TEXT: Readonly<Record<PlanAiActionId, string>> = {
  listen_first: "Listen quietly from one spot before moving so nearby calls can set the direction of the outing.",
  scan_habitat_edges: "Scan transitions between habitat types, where several of the suggested birds may be easier to notice.",
  move_between_vantage_points: "Move deliberately between a few public vantage points instead of covering ground continuously.",
  use_call_examples: "Review the licensed call examples before starting, then use them only as recognition aids in the field.",
  slow_observation_pace: "Leave extra time at each stop for patient observation and repeat listening.",
  verify_access_and_conditions: "Verify current access, closures, and field conditions before leaving home.",
};

export type PublicAiFact = { id: string; value: string };

export interface PublicAiConfiguration {
  endpoint: string;
  turnstileSiteKey: string;
}

type TurnstileWidgetId = string | number;

interface TurnstileApi {
  render(
    container: HTMLElement,
    options: {
      sitekey: string;
      action: string;
      execution: "execute";
      appearance: "interaction-only";
      callback: (token: string) => void;
      "error-callback": () => void;
      "expired-callback": () => void;
      "timeout-callback": () => void;
    },
  ): TurnstileWidgetId;
  execute(widgetId: TurnstileWidgetId): void;
  remove(widgetId: TurnstileWidgetId): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let turnstileScriptPromise: Promise<TurnstileApi> | null = null;

function exactObject(value: unknown, keys: readonly string[]): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const row = value as Record<string, unknown>;
  return Object.keys(row).sort().join("|") === [...keys].sort().join("|") ? row : null;
}

function canonicalAiEndpoint(raw: unknown): string | null {
  if (typeof raw !== "string" || !raw) return null;
  try {
    const url = new URL(raw);
    if (
      url.protocol !== "https:"
      || url.hostname !== PRODUCTION_AI_HOST
      || url.username
      || url.password
      || url.port
      || url.search
      || url.hash
      || (url.pathname !== "/" && url.pathname !== AI_PATH)
    ) return null;
    url.pathname = AI_PATH;
    return url.href;
  } catch {
    return null;
  }
}

export function publicAiConfiguration(): PublicAiConfiguration | null {
  const endpoint = canonicalAiEndpoint(import.meta.env.VITE_RUFOUS_AI_URL);
  const turnstileSiteKey = import.meta.env.VITE_RUFOUS_TURNSTILE_SITE_KEY;
  if (!endpoint || typeof turnstileSiteKey !== "string" || !/^[A-Za-z0-9_-]{10,128}$/.test(turnstileSiteKey)) {
    return null;
  }
  return { endpoint, turnstileSiteKey };
}

function safeBirdName(recommendation: Recommendation): string | null {
  const raw = recommendation.common_name || recommendation.scientific_name;
  if (!raw) return null;
  const normalized = raw.normalize("NFC").replace(/\s+/g, " ").trim();
  return PUBLIC_BIRD_NAME_GRAMMAR.test(normalized)
    ? normalized
    : null;
}

function timeOfDay(detail: TripPlanDetail): "dawn" | "morning" | "midday" | "afternoon" | "evening" | "night" {
  let hour: number;
  try {
    hour = Number(new Intl.DateTimeFormat("en-US", {
      timeZone: detail.plan.timezone || "America/Phoenix",
      hour: "2-digit",
      hourCycle: "h23",
    }).format(new Date(detail.plan.window_start)));
  } catch {
    hour = new Date(detail.plan.window_start).getUTCHours();
  }
  if (hour >= 5 && hour <= 7) return "dawn";
  if (hour >= 8 && hour <= 11) return "morning";
  if (hour >= 12 && hour <= 13) return "midday";
  if (hour >= 14 && hour <= 17) return "afternoon";
  if (hour >= 18 && hour <= 20) return "evening";
  return "night";
}

function occurrenceBand(count: number): "none" | "one" | "2-5" | "6-20" | "21+" {
  if (count <= 0) return "none";
  if (count === 1) return "one";
  if (count <= 5) return "2-5";
  if (count <= 20) return "6-20";
  return "21+";
}

function distanceBand(distanceKm: number | null): "unknown" | "under 5 miles" | "5-15 miles" | "15-30 miles" | "30-50 miles" {
  if (distanceKm === null) return "unknown";
  const miles = distanceKm / 1.609344;
  if (miles < 5) return "under 5 miles";
  if (miles < 15) return "5-15 miles";
  if (miles < 30) return "15-30 miles";
  return "30-50 miles";
}

/** Build the entire outbound fact set. It intentionally excludes coordinates,
 * dates, IDs, free-form constraints, and private collection data. */
export function buildPublicAiFacts(detail: TripPlanDetail): PublicAiFact[] {
  const duration = Number.isSafeInteger(detail.plan.duration_minutes)
    ? Math.max(1, Math.min(1_440, detail.plan.duration_minutes))
    : 90;
  const skill = detail.plan.skill_level === "beginner"
    || detail.plan.skill_level === "intermediate"
    || detail.plan.skill_level === "advanced"
    ? detail.plan.skill_level
    : "unspecified";
  const facts: PublicAiFact[] = [
    { id: "location_region", value: "Arizona" },
    { id: "time_of_day", value: timeOfDay(detail) },
    { id: "duration_minutes", value: String(duration) },
    { id: "skill_level", value: skill },
  ];
  const recommendations = [...detail.recommendations]
    .sort((left, right) => left.rank_order - right.rank_order)
    .slice(0, 5);
  for (const recommendation of recommendations) {
    const name = safeBirdName(recommendation);
    if (!name) continue;
    const occurrences = detail.evidence.filter((item) => (
      item.recommendation_id === recommendation.recommendation_id
      && item.evidence_type === "occurrence_context"
    ));
    const distances = occurrences.map((item) => item.summary.distance_km)
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1000);
    const nearest = distances.length ? Math.min(...distances) : null;
    const index = facts.length - 3;
    facts.push({
      id: `target_${index}`,
      value: `${name} | occurrences: ${occurrenceBand(occurrences.length)} | nearest: ${distanceBand(nearest)} | call: ${recommendation.call.status === "available" ? "available" : "unavailable"}`,
    });
  }
  return facts;
}

/** This exact UTF-8 string is hashed by both the browser and Worker. */
export function requestedPublicAiActions(detail: TripPlanDetail): PlanAiActionId[] {
  const hasPublishedCall = buildPublicAiFacts(detail)
    .some((fact) => fact.id.startsWith("target_") && fact.value.endsWith("call: available"));
  return PLAN_AI_ACTION_IDS.filter((actionId) => actionId !== "use_call_examples" || hasPublishedCall);
}

export function canonicalPublicAiPayload(
  facts: PublicAiFact[],
  actionIds: readonly PlanAiActionId[],
): string {
  return JSON.stringify({
    version: 1,
    facts: [...facts].sort((left, right) => left.id.localeCompare(right.id))
      .map(({ id, value }) => ({ id, value })),
    actionIds: [...actionIds].sort(),
  });
}

export async function computePublicAiFactHash(
  facts: PublicAiFact[],
  actionIds: readonly PlanAiActionId[],
): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new Error("AI enhancement is unavailable in this browser.");
  const bytes = new TextEncoder().encode(canonicalPublicAiPayload(facts, actionIds));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function validatedActionIds(
  value: unknown,
  allowed: ReadonlySet<string> = PLAN_AI_ACTION_SET,
): PlanAiActionId[] | null {
  if (!Array.isArray(value) || value.length < 1 || value.length > 3) return null;
  if (value.some((item) => typeof item !== "string" || !allowed.has(item))) return null;
  return new Set(value).size === value.length ? value as PlanAiActionId[] : null;
}

export async function requestPublicAiEnrichment(
  detail: TripPlanDetail,
  turnstileToken: string,
  configuration: PublicAiConfiguration,
  signal?: AbortSignal,
): Promise<PlanAiEnrichment> {
  if (!/^[A-Za-z0-9._~-]{10,2048}$/.test(turnstileToken)) {
    throw new Error("The free AI check could not be completed.");
  }
  const facts = buildPublicAiFacts(detail);
  if (!facts.some((fact) => fact.id === "target_1")) {
    throw new Error("Free AI has no published bird target to enhance.");
  }
  const requestedActions = requestedPublicAiActions(detail);
  const expectedHash = await computePublicAiFactHash(facts, requestedActions);
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timeout = window.setTimeout(() => controller.abort(), AI_TIMEOUT_MS);
  try {
    const response = await fetch(configuration.endpoint, {
      method: "POST",
      credentials: "omit",
      referrerPolicy: "no-referrer",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        turnstileToken,
        factHash: expectedHash,
        facts,
        actionIds: requestedActions,
      }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("Free AI is unavailable right now.");
    const raw = await response.text();
    if (raw.length > 8_192) throw new Error("Free AI returned an invalid response.");
    let value: unknown;
    try { value = JSON.parse(raw); }
    catch { throw new Error("Free AI returned an invalid response."); }
    const row = exactObject(value, ["status", "factHash", "actionIds"]);
    const actions = validatedActionIds(row?.actionIds, new Set(requestedActions));
    if (row?.status !== "ok" || row.factHash !== expectedHash || !actions) {
      throw new Error("Free AI returned an invalid response.");
    }
    return {
      schema_version: 1,
      fact_hash: expectedHash,
      action_ids: actions,
      created_at: new Date().toISOString(),
    };
  } catch (reason) {
    if (reason instanceof Error && reason.message === "Free AI returned an invalid response.") throw reason;
    throw new Error("Free AI is unavailable right now. Your complete browser-generated plan is unchanged.");
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}

export function aiActionText(actionId: PlanAiActionId): string {
  return ACTION_TEXT[actionId];
}

export function applyAiEnrichmentToPlan(
  detail: TripPlanDetail,
  enrichment: PlanAiEnrichment,
): TripPlanDetail {
  if (detail.ai_enrichment) return detail;
  const actions = validatedActionIds(enrichment.action_ids);
  const createdAt = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(enrichment.created_at)
    && !Number.isNaN(Date.parse(enrichment.created_at));
  if (enrichment.schema_version !== 1 || !/^[0-9a-f]{64}$/.test(enrichment.fact_hash) || !actions || !createdAt) {
    throw new Error("Free AI returned an invalid response.");
  }
  const strategy = actions.map(aiActionText).join(" ");
  const prior = detail.plan.field_plan_text?.trim() || "Use the licensed historical evidence as context, not a guarantee of current presence.";
  const now = enrichment.created_at;
  return {
    ...detail,
    plan: {
      ...detail.plan,
      field_plan_text: `${prior}\n\nFree AI field strategy: ${strategy}`,
      caveats: [
        ...detail.plan.caveats.filter((item) => item !== "Live weather and AI prose are optional enhancements and were not used."),
        "Free Workers AI selected from a fixed action list; Rufous rendered the wording locally and did not accept model-authored facts.",
        "Live weather remains optional and was not used for this plan.",
      ],
      updated_at: now,
    },
    tool_traces: [
      ...detail.tool_traces,
      {
        tool_trace_id: `trace_free_ai_${enrichment.fact_hash.slice(0, 12)}`,
        step_order: Math.max(0, ...detail.tool_traces.map((trace) => trace.step_order)) + 1,
        tool_name: "select_free_ai_field_actions",
        tool_status: "ok",
        started_at: now,
        completed_at: now,
        input: { fact_hash: enrichment.fact_hash },
        output_summary: { model_calls: 1, action_count: actions.length },
        caveats: ["The model selected only allowlisted action IDs; all displayed wording was rendered deterministically in this browser."],
      },
    ],
    ai_enrichment: { ...enrichment, action_ids: actions },
  };
}

async function loadTurnstile(signal?: AbortSignal): Promise<TurnstileApi> {
  if (window.turnstile) return window.turnstile;
  if (!turnstileScriptPromise) {
    turnstileScriptPromise = new Promise<TurnstileApi>((resolve, reject) => {
      const existing = document.querySelector<HTMLScriptElement>(`script[src="${TURNSTILE_SCRIPT_URL}"]`);
      const script = existing || document.createElement("script");
      const loaded = () => window.turnstile ? resolve(window.turnstile) : reject(new Error("Turnstile did not load."));
      const failed = () => reject(new Error("Turnstile did not load."));
      script.addEventListener("load", loaded, { once: true });
      script.addEventListener("error", failed, { once: true });
      if (!existing) {
        script.src = TURNSTILE_SCRIPT_URL;
        script.async = true;
        script.defer = true;
        script.referrerPolicy = "no-referrer";
        document.head.append(script);
      }
    }).catch((reason) => {
      turnstileScriptPromise = null;
      throw reason;
    });
  }
  let timeout = 0;
  let aborted: (() => void) | null = null;
  const stopped = new Promise<never>((_, reject) => {
    timeout = window.setTimeout(() => reject(new Error("Turnstile did not load.")), TURNSTILE_TIMEOUT_MS);
    if (signal) {
      aborted = () => reject(new DOMException("Aborted", "AbortError"));
      signal.addEventListener("abort", aborted, { once: true });
    }
  });
  try {
    return await Promise.race([turnstileScriptPromise, stopped]);
  } finally {
    window.clearTimeout(timeout);
    if (signal && aborted) signal.removeEventListener("abort", aborted);
  }
}

async function obtainTurnstileToken(
  container: HTMLElement,
  siteKey: string,
  signal?: AbortSignal,
): Promise<string> {
  const turnstile = await loadTurnstile(signal);
  return new Promise<string>((resolve, reject) => {
    let widgetId: TurnstileWidgetId | null = null;
    let settled = false;
    const finish = (token?: string) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      signal?.removeEventListener("abort", aborted);
      if (widgetId !== null) turnstile.remove(widgetId);
      container.replaceChildren();
      if (token && /^[A-Za-z0-9._~-]{10,2048}$/.test(token)) resolve(token);
      else reject(new Error("The free AI check could not be completed."));
    };
    const aborted = () => finish();
    const timeout = window.setTimeout(() => finish(), TURNSTILE_TIMEOUT_MS);
    signal?.addEventListener("abort", aborted, { once: true });
    try {
      widgetId = turnstile.render(container, {
        sitekey: siteKey,
        action: "trip_plan_enrich",
        execution: "execute",
        appearance: "interaction-only",
        callback: (token) => finish(token),
        "error-callback": () => finish(),
        "expired-callback": () => finish(),
        "timeout-callback": () => finish(),
      });
      turnstile.execute(widgetId);
    } catch {
      finish();
    }
  });
}

export function PublicAiEnrichment({
  detail,
  onEnriched,
}: {
  detail: TripPlanDetail;
  onEnriched: (enrichment: PlanAiEnrichment) => Promise<void>;
}) {
  const configuration = publicAiConfiguration();
  const widgetRef = useRef<HTMLDivElement>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => () => activeRequest.current?.abort(), []);
  useEffect(() => {
    setMessage(null);
    setBusy(false);
    activeRequest.current?.abort();
  }, [detail.plan.trip_plan_id]);

  if (detail.ai_enrichment) {
    return <div className="ai-enrichment ai-enrichment-complete">
      <span className="badge">Workers AI Free</span>
      <p>Free AI selected this fixed field strategy once. It is saved on this device, so reopening this plan makes no AI request.</p>
      <ul>{detail.ai_enrichment.action_ids.map((actionId) => <li key={actionId}>{aiActionText(actionId)}</li>)}</ul>
    </div>;
  }

  if (!configuration) {
    return <p className="source-status" role="status">Free AI enhancement is not configured. Your complete browser-generated plan remains available.</p>;
  }

  if (!buildPublicAiFacts(detail).some((fact) => fact.id === "target_1")) {
    return <p className="source-status" role="status">This plan has no published bird target for free AI to enhance. The browser-generated plan remains complete.</p>;
  }

  async function enhance() {
    if (busy || activeRequest.current || !widgetRef.current) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(true);
    setMessage(null);
    try {
      const token = await obtainTurnstileToken(widgetRef.current, configuration!.turnstileSiteKey, controller.signal);
      const enrichment = await requestPublicAiEnrichment(detail, token, configuration!, controller.signal);
      await onEnriched(enrichment);
    } catch {
      if (!controller.signal.aborted) {
        setMessage("Free AI is unavailable right now. Your complete browser-generated plan, maps, audio, and calendar download are unchanged.");
      }
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return <div className="ai-enrichment">
    <p><strong>Optional free AI:</strong> let Workers AI choose a few field actions from bounded public facts. No coordinates, plan IDs, observation IDs, personal observations, or typed constraints are sent.</p>
    <button type="button" disabled={busy} onClick={() => void enhance()}>{busy ? "Checking the free AI allowance…" : "Enhance with free AI"}</button>
    <div ref={widgetRef} className="turnstile-slot" aria-live="polite" />
    {message && <p className="source-status" role="status">{message}</p>}
  </div>;
}

export function resetPublicAiRuntimeForTests(): void {
  turnstileScriptPromise = null;
}
