import { useSQLQuery } from "@motherduck/react-sql-query";
import { useEffect, useMemo, useState } from "react";

const DATABASE_NAME = "databox";
const SCHEMA_NAME = "birding_agent";
const TABLE = (name: string) => `"${DATABASE_NAME}"."${SCHEMA_NAME}"."${name}"`;

type Row = Record<string, unknown>;

type QueryState = {
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
};

const colors = {
  ink: "#1f2933",
  muted: "#64748b",
  line: "#e2e8f0",
  bg: "#f8fafc",
  card: "#ffffff",
  blue: "#2563eb",
  green: "#15803d",
  amber: "#b45309",
  red: "#b91c1c",
  purple: "#7c3aed",
  teal: "#0f766e",
};

function s(value: unknown, fallback = "—"): string {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function n(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatNumber(value: unknown, digits = 0): string {
  const parsed = n(value);
  if (parsed === null) return "—";
  return parsed.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatDateTime(value: unknown): string {
  const raw = s(value, "");
  if (!raw) return "—";
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function parseJson<T>(value: unknown, fallback: T): T {
  if (typeof value !== "string" || value.trim() === "") return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function escapeSqlString(value: string): string {
  return value.replace(/'/g, "''");
}

function rows(data: unknown): Row[] {
  return Array.isArray(data) ? (data as Row[]) : [];
}

const planListSql = `
  SELECT
    trip_plan_id,
    COALESCE(normalized_location_name, requested_location) AS plan_label,
    window_start,
    window_end,
    duration_minutes,
    plan_status,
    created_at
  FROM ${TABLE("trip_plans")}
  ORDER BY created_at DESC, window_start DESC
  LIMIT 50
`;

const planDetailSql = (tripPlanId: string) => `
  SELECT
    trip_plan_id,
    requested_location,
    normalized_location_name,
    latitude,
    longitude,
    region_code,
    window_start,
    window_end,
    duration_minutes,
    skill_level,
    constraints_text,
    plan_status,
    field_plan_text,
    caveats_json,
    created_at,
    updated_at
  FROM ${TABLE("trip_plans")}
  WHERE trip_plan_id = '${escapeSqlString(tripPlanId)}'
  LIMIT 1
`;

const recommendationsSql = (tripPlanId: string) => `
  WITH recommendations AS (
    SELECT
      r.recommendation_id,
      r.trip_plan_id,
      r.species_code,
      r.common_name,
      r.scientific_name,
      r.recommendation_group,
      r.rank_order,
      r.confidence_label,
      r.rationale_text,
      r.caveats_json,
      COUNT(e.evidence_id) AS evidence_count,
      string_agg(DISTINCT e.source, ', ') AS evidence_sources
    FROM ${TABLE("trip_plan_recommendations")} r
    LEFT JOIN ${TABLE("trip_plan_evidence")} e
      ON e.recommendation_id = r.recommendation_id
    WHERE r.trip_plan_id = '${escapeSqlString(tripPlanId)}'
    GROUP BY ALL
  )
  SELECT *
  FROM recommendations
  ORDER BY
    CASE recommendation_group
      WHEN 'high_likelihood' THEN 1
      WHEN 'uncommon_plausible' THEN 2
      ELSE 3
    END,
    rank_order ASC
`;

const evidenceSql = (tripPlanId: string) => `
  SELECT
    e.evidence_id,
    e.trip_plan_id,
    e.recommendation_id,
    COALESCE(r.common_name, 'Trip-level') AS recommendation_label,
    e.source,
    e.source_table,
    e.source_record_id,
    e.evidence_type,
    e.status,
    e.latitude,
    e.longitude,
    e.window_start,
    e.window_end,
    e.retrieved_at,
    e.summary_json,
    e.payload_json,
    e.caveats_json
  FROM ${TABLE("trip_plan_evidence")} e
  LEFT JOIN ${TABLE("trip_plan_recommendations")} r
    ON r.recommendation_id = e.recommendation_id
  WHERE e.trip_plan_id = '${escapeSqlString(tripPlanId)}'
  ORDER BY
    CASE e.source
      WHEN 'open_meteo' THEN 1
      WHEN 'ebird' THEN 2
      WHEN 'gbif' THEN 3
      WHEN 'xeno_canto' THEN 4
      ELSE 5
    END,
    e.status DESC,
    e.retrieved_at DESC NULLS LAST
  LIMIT 200
`;

const weatherSql = (tripPlanId: string) => `
  SELECT
    evidence_id,
    status,
    latitude,
    longitude,
    retrieved_at,
    summary_json,
    payload_json,
    caveats_json
  FROM ${TABLE("trip_plan_evidence")}
  WHERE trip_plan_id = '${escapeSqlString(tripPlanId)}'
    AND source = 'open_meteo'
  ORDER BY retrieved_at DESC NULLS LAST
  LIMIT 1
`;

const mediaSql = (tripPlanId: string) => `
  SELECT
    e.evidence_id,
    COALESCE(r.common_name, json_extract_string(e.summary_json, '$.english_name'), 'Media example') AS species_label,
    e.status,
    e.summary_json,
    e.payload_json,
    e.caveats_json
  FROM ${TABLE("trip_plan_evidence")} e
  LEFT JOIN ${TABLE("trip_plan_recommendations")} r
    ON r.recommendation_id = e.recommendation_id
  WHERE e.trip_plan_id = '${escapeSqlString(tripPlanId)}'
    AND e.source = 'xeno_canto'
  ORDER BY species_label, e.status DESC
  LIMIT 20
`;

const tracesSql = (tripPlanId: string) => `
  SELECT
    tool_trace_id,
    step_order,
    tool_name,
    tool_status,
    started_at,
    completed_at,
    output_summary_json,
    caveats_json
  FROM ${TABLE("trip_plan_tool_traces")}
  WHERE trip_plan_id = '${escapeSqlString(tripPlanId)}'
  ORDER BY step_order ASC
`;

function Badge({ children, tone = "blue" }: { children: React.ReactNode; tone?: "blue" | "green" | "amber" | "red" | "purple" | "gray" }) {
  const palette = {
    blue: ["#eff6ff", colors.blue],
    green: ["#ecfdf5", colors.green],
    amber: ["#fffbeb", colors.amber],
    red: ["#fef2f2", colors.red],
    purple: ["#f5f3ff", colors.purple],
    gray: ["#f1f5f9", colors.muted],
  }[tone];
  return <span style={{ background: palette[0], color: palette[1], borderRadius: 999, padding: "3px 9px", fontSize: 12, fontWeight: 700 }}>{children}</span>;
}

function Card({ title, icon, children, right }: { title: string; icon?: React.ReactNode; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section style={{ background: colors.card, border: `1px solid ${colors.line}`, borderRadius: 18, padding: 22, boxShadow: "0 10px 30px rgba(15, 23, 42, 0.06)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        {icon}
        <h2 style={{ color: colors.ink, fontSize: 18, margin: 0 }}>{title}</h2>
        {right && <div style={{ marginLeft: "auto" }}>{right}</div>}
      </div>
      {children}
    </section>
  );
}

function QueryBoundary({ state, rows, empty, children }: { state: QueryState; rows?: Row[]; empty: string; children: React.ReactNode }) {
  if (state.isLoading) {
    return <div style={{ color: colors.muted, display: "flex", alignItems: "center", gap: 8 }}><span aria-hidden="true">⏳</span> Loading…</div>;
  }
  if (state.isError) {
    return <div style={{ color: colors.red, display: "flex", gap: 8 }}><span aria-hidden="true">⚠️</span> {state.error?.message ?? "Query failed"}</div>;
  }
  if (rows && rows.length === 0) {
    return <div style={{ color: colors.muted }}>{empty}</div>;
  }
  return <>{children}</>;
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{ border: `1px solid ${colors.line}`, borderRadius: 14, padding: 16, background: "#fff" }}>
      <div style={{ color: colors.ink, fontSize: 26, fontWeight: 800 }}>{value}</div>
      <div style={{ color: colors.muted, fontSize: 12, marginTop: 4 }}>{label}</div>
      {sub && <div style={{ color: colors.muted, fontSize: 11, marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function PlanSummary({ plan, recs, evidence, traces }: { plan: Row; recs: Row[]; evidence: Row[]; traces: Row[] }) {
  const caveats = parseJson<string[]>(plan.caveats_json, []);
  const high = recs.filter((row) => row.recommendation_group === "high_likelihood").length;
  const plausible = recs.filter((row) => row.recommendation_group === "uncommon_plausible").length;
  const sources = Array.from(new Set(evidence.map((row) => s(row.source, "")).filter(Boolean)));
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
        <Kpi label="High-likelihood species" value={String(high)} />
        <Kpi label="Uncommon plausible targets" value={String(plausible)} />
        <Kpi label="Evidence rows" value={String(evidence.length)} sub={sources.join(", ") || "no sources"} />
        <Kpi label="Tool steps" value={String(traces.length)} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, color: colors.muted, fontSize: 14 }}>
        <div><strong style={{ color: colors.ink }}>Location:</strong> {s(plan.normalized_location_name, s(plan.requested_location))}</div>
        <div><strong style={{ color: colors.ink }}>Window:</strong> {formatDateTime(plan.window_start)} – {formatDateTime(plan.window_end)}</div>
        <div><strong style={{ color: colors.ink }}>Duration:</strong> {formatNumber(plan.duration_minutes)} min</div>
        <div><strong style={{ color: colors.ink }}>Skill/constraints:</strong> {s(plan.skill_level, "unspecified")} · {s(plan.constraints_text, "no constraints")}</div>
      </div>
      {caveats.length > 0 && (
        <div style={{ background: "#fff7ed", border: "1px solid #fed7aa", borderRadius: 12, padding: 14, color: colors.amber }}>
          <strong>Caveats:</strong> {caveats.join(" · ")}
        </div>
      )}
    </div>
  );
}

function WeatherPanel({ weatherRows }: { weatherRows: Row[] }) {
  const weather = weatherRows[0];
  const summary = parseJson<Record<string, unknown>>(weather?.summary_json, {});
  const payload = parseJson<Record<string, unknown>>(weather?.payload_json, {});
  const forecast = (summary.forecast_summary ?? payload.forecast_summary ?? {}) as Record<string, unknown>;
  const caveats = parseJson<string[]>(weather?.caveats_json, []);
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12 }}>
        <Kpi label="Weather status" value={s(weather?.status, "unavailable")} />
        <Kpi label="Avg temp" value={`${formatNumber(forecast.temperature_2m_avg, 1)} °C`} />
        <Kpi label="Max precip chance" value={`${formatNumber(forecast.precipitation_probability_max)}%`} />
        <Kpi label="Max wind" value={`${formatNumber(forecast.wind_speed_10m_max, 1)} km/h`} />
        <Kpi label="Elevation" value={`${formatNumber(summary.elevation_m ?? payload.elevation_m, 0)} m`} />
      </div>
      {caveats.length > 0 && <p style={{ color: colors.amber, margin: 0 }}>Weather caveats: {caveats.join(" · ")}</p>}
    </div>
  );
}

function RecommendationTable({ recs }: { recs: Row[] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ color: colors.muted, textAlign: "left", borderBottom: `1px solid ${colors.line}` }}>
            <th style={{ padding: "10px 8px" }}>Rank</th>
            <th style={{ padding: "10px 8px" }}>Species</th>
            <th style={{ padding: "10px 8px" }}>Group</th>
            <th style={{ padding: "10px 8px" }}>Confidence</th>
            <th style={{ padding: "10px 8px" }}>Evidence</th>
            <th style={{ padding: "10px 8px" }}>Rationale</th>
          </tr>
        </thead>
        <tbody>
          {recs.map((rec) => {
            const group = s(rec.recommendation_group);
            return (
              <tr key={s(rec.recommendation_id)} style={{ borderBottom: `1px solid ${colors.line}` }}>
                <td style={{ padding: "12px 8px", color: colors.muted }}>{formatNumber(rec.rank_order)}</td>
                <td style={{ padding: "12px 8px" }}>
                  <div style={{ color: colors.ink, fontWeight: 800 }}>{s(rec.common_name, s(rec.scientific_name))}</div>
                  <div style={{ color: colors.muted, fontSize: 12, fontStyle: "italic" }}>{s(rec.scientific_name)}</div>
                </td>
                <td style={{ padding: "12px 8px" }}><Badge tone={group === "high_likelihood" ? "green" : "purple"}>{group.replace(/_/g, " ")}</Badge></td>
                <td style={{ padding: "12px 8px" }}>{s(rec.confidence_label)}</td>
                <td style={{ padding: "12px 8px" }}>{formatNumber(rec.evidence_count)} · {s(rec.evidence_sources, "no evidence")}</td>
                <td style={{ padding: "12px 8px", color: colors.muted, minWidth: 260 }}>{s(rec.rationale_text)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function EvidenceTable({ evidence }: { evidence: Row[] }) {
  return (
    <div style={{ overflowX: "auto", maxHeight: 460, overflowY: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ color: colors.muted, textAlign: "left", borderBottom: `1px solid ${colors.line}` }}>
            <th style={{ padding: "10px 8px" }}>Source</th>
            <th style={{ padding: "10px 8px" }}>Status</th>
            <th style={{ padding: "10px 8px" }}>Applies to</th>
            <th style={{ padding: "10px 8px" }}>Evidence</th>
            <th style={{ padding: "10px 8px" }}>Provenance</th>
          </tr>
        </thead>
        <tbody>
          {evidence.map((row) => {
            const summary = parseJson<Record<string, unknown>>(row.summary_json, {});
            const caveats = parseJson<string[]>(row.caveats_json, []);
            return (
              <tr key={s(row.evidence_id)} style={{ borderBottom: `1px solid ${colors.line}`, verticalAlign: "top" }}>
                <td style={{ padding: "12px 8px" }}><Badge tone={row.status === "available" ? "blue" : "amber"}>{s(row.source)}</Badge></td>
                <td style={{ padding: "12px 8px" }}>{s(row.status)}</td>
                <td style={{ padding: "12px 8px", color: colors.ink }}>{s(row.recommendation_label)}</td>
                <td style={{ padding: "12px 8px", color: colors.muted, minWidth: 260 }}>
                  {Object.entries(summary).slice(0, 5).map(([key, value]) => (
                    <div key={key}><strong>{key.replace(/_/g, " ")}:</strong> {s(value)}</div>
                  ))}
                  {caveats.length > 0 && <div style={{ color: colors.amber, marginTop: 6 }}>{caveats.join(" · ")}</div>}
                </td>
                <td style={{ padding: "12px 8px", color: colors.muted }}>
                  <div>{s(row.source_table)}</div>
                  <div>{s(row.source_record_id)}</div>
                  <div>{formatDateTime(row.retrieved_at)}</div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MediaPanel({ media }: { media: Row[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
      {media.map((row) => {
        const summary = parseJson<Record<string, unknown>>(row.summary_json, {});
        const payload = parseJson<Record<string, unknown>>(row.payload_json, {});
        const url = s(summary.recording_url ?? payload.recording_url, "");
        return (
          <div key={s(row.evidence_id)} style={{ border: `1px solid ${colors.line}`, borderRadius: 14, padding: 16 }}>
            <div style={{ color: colors.ink, fontWeight: 800 }}>{s(row.species_label)}</div>
            <div style={{ color: colors.muted, marginTop: 4 }}>{s(summary.recording_type, "recording")} · quality {s(summary.quality)}</div>
            <div style={{ color: colors.muted, marginTop: 4 }}>License: {s(summary.license ?? payload.license)}</div>
            {url && <a href={url} target="_blank" rel="noreferrer" style={{ color: colors.blue, display: "inline-block", marginTop: 8 }}>Open Xeno-canto recording</a>}
          </div>
        );
      })}
    </div>
  );
}

function TraceTimeline({ traces }: { traces: Row[] }) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {traces.map((trace) => {
        const summary = parseJson<Record<string, unknown>>(trace.output_summary_json, {});
        const caveats = parseJson<string[]>(trace.caveats_json, []);
        return (
          <div key={s(trace.tool_trace_id)} style={{ display: "grid", gridTemplateColumns: "42px 1fr auto", gap: 12, alignItems: "start", border: `1px solid ${colors.line}`, borderRadius: 14, padding: 12 }}>
            <div style={{ width: 30, height: 30, borderRadius: 999, background: "#eff6ff", color: colors.blue, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 900 }}>{formatNumber(trace.step_order)}</div>
            <div>
              <div style={{ color: colors.ink, fontWeight: 800 }}>{s(trace.tool_name).replace(/_/g, " ")}</div>
              <div style={{ color: colors.muted, fontSize: 12 }}>{Object.entries(summary).slice(0, 4).map(([key, value]) => `${key}: ${s(value)}`).join(" · ")}</div>
              {caveats.length > 0 && <div style={{ color: colors.amber, fontSize: 12, marginTop: 4 }}>{caveats.join(" · ")}</div>}
            </div>
            <Badge tone={trace.tool_status === "ok" ? "green" : "red"}>{s(trace.tool_status)}</Badge>
          </div>
        );
      })}
    </div>
  );
}

export default function BirdingTripPlanDive() {
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const planList = useSQLQuery(planListSql);
  const planRows = rows(planList.data);
  const activePlanId = selectedPlanId ?? s(planRows[0]?.trip_plan_id, "");

  useEffect(() => {
    if (!selectedPlanId && planRows[0]?.trip_plan_id) {
      setSelectedPlanId(s(planRows[0].trip_plan_id));
    }
  }, [planRows, selectedPlanId]);

  const detailQuery = useSQLQuery(activePlanId ? planDetailSql(activePlanId) : "SELECT NULL WHERE FALSE", { enabled: Boolean(activePlanId) });
  const recQuery = useSQLQuery(activePlanId ? recommendationsSql(activePlanId) : "SELECT NULL WHERE FALSE", { enabled: Boolean(activePlanId) });
  const evidenceQuery = useSQLQuery(activePlanId ? evidenceSql(activePlanId) : "SELECT NULL WHERE FALSE", { enabled: Boolean(activePlanId) });
  const weatherQuery = useSQLQuery(activePlanId ? weatherSql(activePlanId) : "SELECT NULL WHERE FALSE", { enabled: Boolean(activePlanId) });
  const mediaQuery = useSQLQuery(activePlanId ? mediaSql(activePlanId) : "SELECT NULL WHERE FALSE", { enabled: Boolean(activePlanId) });
  const tracesQuery = useSQLQuery(activePlanId ? tracesSql(activePlanId) : "SELECT NULL WHERE FALSE", { enabled: Boolean(activePlanId) });

  const plan = rows(detailQuery.data)[0];
  const recs = rows(recQuery.data);
  const evidence = rows(evidenceQuery.data);
  const weather = rows(weatherQuery.data);
  const media = rows(mediaQuery.data);
  const traces = rows(tracesQuery.data);
  const sourceBadges = useMemo(() => Array.from(new Set(evidence.map((row) => s(row.source, "")).filter(Boolean))), [evidence]);

  return (
    <main style={{ minHeight: "100vh", background: colors.bg, color: colors.ink, fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", padding: 28 }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", display: "grid", gap: 18 }}>
        <header style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 16, alignItems: "end" }}>
          <div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", color: colors.teal, fontWeight: 800, fontSize: 13, letterSpacing: 0.4, textTransform: "uppercase" }}>
              <span aria-hidden="true">🔭</span> Birding Trip Copilot
            </div>
            <h1 style={{ margin: "8px 0 6px", fontSize: 38, letterSpacing: -1 }}>Evidence-backed birding plan</h1>
            <p style={{ color: colors.muted, margin: 0, maxWidth: 760 }}>A MotherDuck Dive over persisted Python/Google ADK planner outputs. The Dive reads trip plans, recommendations, evidence, and tool traces from SQL only; it does not run the agent in-browser.</p>
          </div>
          <div style={{ minWidth: 260 }}>
            <label style={{ display: "block", color: colors.muted, fontSize: 12, marginBottom: 6 }}>Trip plan</label>
            <QueryBoundary state={planList} rows={planRows} empty="No trip plans found. Generate one with the Python planner first.">
              <select value={activePlanId} onChange={(event) => setSelectedPlanId(event.target.value)} style={{ width: "100%", border: `1px solid ${colors.line}`, borderRadius: 12, padding: "10px 12px", background: "#fff", color: colors.ink }}>
                {planRows.map((row) => <option key={s(row.trip_plan_id)} value={s(row.trip_plan_id)}>{s(row.plan_label)} · {formatDateTime(row.window_start)}</option>)}
              </select>
            </QueryBoundary>
          </div>
        </header>

        <QueryBoundary state={detailQuery} rows={plan ? [plan] : []} empty="Selected trip plan was not found.">
          {plan && (
            <>
              <Card title="Plan summary" icon={<span aria-hidden="true">📍</span>} right={<Badge tone={plan.plan_status === "complete" ? "green" : "amber"}>{s(plan.plan_status)}</Badge>}>
                <PlanSummary plan={plan} recs={recs} evidence={evidence} traces={traces} />
              </Card>

              <Card title="Field plan" icon={<span aria-hidden="true">🗺️</span>}>
                <p style={{ fontSize: 17, lineHeight: 1.7, color: colors.ink, margin: 0 }}>{s(plan.field_plan_text, "No field plan text persisted for this trip.")}</p>
              </Card>

              <Card title="Weather and elevation context" icon={<span aria-hidden="true">🌤️</span>}>
                <QueryBoundary state={weatherQuery} rows={weather} empty="No Open-Meteo evidence row is attached to this plan.">
                  <WeatherPanel weatherRows={weather} />
                </QueryBoundary>
              </Card>

              <Card title="Ranked species recommendations" icon={<span aria-hidden="true">🐦</span>} right={<div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>{sourceBadges.map((source) => <Badge key={source} tone="gray">{source}</Badge>)}</div>}>
                <QueryBoundary state={recQuery} rows={recs} empty="No species recommendations are attached to this plan.">
                  <RecommendationTable recs={recs} />
                </QueryBoundary>
              </Card>

              <Card title="Xeno-canto media and license context" icon={<span aria-hidden="true">🎧</span>}>
                <QueryBoundary state={mediaQuery} rows={media} empty="No Xeno-canto media evidence is attached to this plan.">
                  <MediaPanel media={media} />
                </QueryBoundary>
              </Card>

              <Card title="Evidence and provenance" icon={<span aria-hidden="true">🗄️</span>} right={<Badge tone="blue">{evidence.length} rows</Badge>}>
                <QueryBoundary state={evidenceQuery} rows={evidence} empty="No evidence rows are attached to this plan.">
                  <EvidenceTable evidence={evidence} />
                </QueryBoundary>
              </Card>

              <Card title="Agent tool trace" icon={<span aria-hidden="true">👣</span>} right={<Badge tone="green">{traces.length} steps</Badge>}>
                <QueryBoundary state={tracesQuery} rows={traces} empty="No tool traces are attached to this plan.">
                  <TraceTimeline traces={traces} />
                </QueryBoundary>
              </Card>
            </>
          )}
        </QueryBoundary>

        <footer style={{ color: colors.muted, fontSize: 12, display: "flex", gap: 8, alignItems: "center", paddingBottom: 20 }}>
          <span aria-hidden="true">✅</span> SQL-only Dive surface over {TABLE("trip_plans")}, recommendations, evidence, and traces. No browser-side API secrets.
        </footer>
      </div>
    </main>
  );
}
