import { FormEvent, useEffect, useMemo, useState } from "react";
import { createPlan, getPlan, listPlans } from "./api";
import type {
  CreatePlanInput,
  Evidence,
  PlanSummary,
  Recommendation,
  TripPlanDetail,
} from "./types";
import "./styles.css";

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function numberText(value: unknown, suffix = ""): string | null {
  return typeof value === "number" ? `${value.toLocaleString()}${suffix}` : null;
}

function mediaUrl(row: Evidence): string | null {
  const raw = text(row.summary.recording_url) || text(row.payload.recording_url) || text(row.payload.url);
  if (!raw) return null;
  try {
    const url = new URL(raw);
    const isXenoCanto = url.hostname === "xeno-canto.org" || url.hostname.endsWith(".xeno-canto.org");
    return url.protocol === "https:" && isXenoCanto ? url.href : null;
  } catch {
    return null;
  }
}

function evidenceSummary(row: Evidence): string {
  const values = [
    text(row.summary.common_name),
    text(row.summary.english_name),
    text(row.summary.recording_type),
    text(row.summary.quality),
    text(row.summary.location_name),
  ].filter(Boolean);
  return values.join(" · ") || row.evidence_type.replaceAll("_", " ");
}

function RecommendationGroup({ title, rows }: { title: string; rows: Recommendation[] }) {
  return (
    <section className="panel" aria-labelledby={`group-${title.replaceAll(" ", "-")}`}>
      <h2 id={`group-${title.replaceAll(" ", "-")}`}>{title}</h2>
      {rows.length === 0 ? (
        <p className="empty">No supported targets in this group.</p>
      ) : (
        <ol className="species-grid">
          {rows.map((row) => (
            <li key={row.recommendation_id} className="species-card">
              <div className="species-rank">#{row.rank_order}</div>
              <h3>{row.common_name || row.scientific_name || row.species_code || "Unknown species"}</h3>
              {row.common_name && row.scientific_name && <p className="scientific">{row.scientific_name}</p>}
              <span className="badge">{row.confidence_label || "evidence-backed"}</span>
              {row.rationale_text && <p>{row.rationale_text}</p>}
              {row.caveats.map((caveat) => <p className="caveat" key={caveat}>{caveat}</p>)}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function PlanView({ detail }: { detail: TripPlanDetail }) {
  const high = detail.recommendations.filter((row) => row.recommendation_group === "high_likelihood");
  const uncommon = detail.recommendations.filter((row) => row.recommendation_group === "uncommon_plausible");
  const media = detail.media.filter((row) => row.status === "available");
  const weather = detail.weather?.payload || detail.weather?.summary || {};
  const elevation = numberText(weather.elevation_m, " m");
  const weatherStatus = detail.weather?.status || "unavailable";

  return (
    <div className="plan" aria-live="polite">
      <section className="hero-card">
        <p className="eyebrow">Persisted trip plan</p>
        <h1>{detail.plan.normalized_location_name || detail.plan.requested_location}</h1>
        <div className="summary-grid">
          <div><strong>{new Date(detail.plan.window_start).toLocaleString()}</strong><span>Start</span></div>
          <div><strong>{detail.plan.duration_minutes} min</strong><span>Duration</span></div>
          <div><strong>{elevation || "Not available"}</strong><span>Elevation</span></div>
          <div><strong>{weatherStatus}</strong><span>Weather context</span></div>
        </div>
      </section>

      {detail.plan.caveats.length > 0 && (
        <section className="notice" aria-labelledby="plan-caveats">
          <h2 id="plan-caveats">Plan caveats</h2>
          <ul>{detail.plan.caveats.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      )}

      <section className="panel" aria-labelledby="field-plan">
        <h2 id="field-plan">Field plan</h2>
        <p className="field-plan">{detail.plan.field_plan_text || "No field plan was persisted."}</p>
      </section>

      <RecommendationGroup title="High-likelihood species" rows={high} />
      <RecommendationGroup title="Uncommon but plausible targets" rows={uncommon} />

      <section className="panel" aria-labelledby="weather-context">
        <h2 id="weather-context">Weather and elevation</h2>
        {detail.weather ? (
          <dl className="details-list">
            <div><dt>Status</dt><dd>{detail.weather.status}</dd></div>
            <div><dt>Elevation</dt><dd>{elevation || "Not reported"}</dd></div>
            <div><dt>Source</dt><dd>Open-Meteo</dd></div>
          </dl>
        ) : <p className="empty">Open-Meteo context was not persisted.</p>}
      </section>

      <section className="panel" aria-labelledby="media-examples">
        <h2 id="media-examples">Call and media examples</h2>
        {media.length === 0 ? <p className="empty">No Xeno-canto media examples were available.</p> : (
          <ul className="link-list">
            {media.map((row) => {
              const url = mediaUrl(row);
              const recordist = text(row.summary.recordist) || text(row.payload.recordist) || "Recordist not reported";
              const license = text(row.summary.license) || text(row.payload.license) || "License not reported";
              return <li key={row.evidence_id}>
                {url ? <a href={url} target="_blank" rel="noreferrer">{evidenceSummary(row)}</a> : <span>{evidenceSummary(row)}</span>}
                <small>Source: Xeno-canto · Recordist: {recordist} · License: {license}</small>
              </li>;
            })}
          </ul>
        )}
      </section>

      <section className="panel table-panel" aria-labelledby="evidence-heading">
        <h2 id="evidence-heading">Evidence and provenance</h2>
        {detail.evidence.length === 0 ? <p className="empty">No evidence was persisted.</p> : (
          <div className="table-scroll"><table>
            <thead><tr><th>Source</th><th>Status</th><th>Type</th><th>Summary</th><th>Record</th></tr></thead>
            <tbody>{detail.evidence.map((row) => <tr key={row.evidence_id}>
              <td>{row.source}</td><td>{row.status}</td><td>{row.evidence_type.replaceAll("_", " ")}</td>
              <td>{evidenceSummary(row)}</td><td>{row.source_record_id || "—"}</td>
            </tr>)}</tbody>
          </table></div>
        )}
      </section>

      <section className="panel" aria-labelledby="workflow-heading">
        <h2 id="workflow-heading">Agent workflow</h2>
        <ol className="timeline">{detail.tool_traces.map((trace) => <li key={trace.tool_trace_id}>
          <span className={`status-dot ${trace.tool_status}`} aria-hidden="true" />
          <div><strong>{trace.step_order}. {trace.tool_name.replaceAll("_", " ")}</strong>
          <span>{trace.tool_status}</span>
          {trace.caveats.map((item) => <p className="caveat" key={item}>{item}</p>)}</div>
        </li>)}</ol>
      </section>
    </div>
  );
}

export default function App() {
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [detail, setDetail] = useState<TripPlanDetail | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedId = detail?.plan.trip_plan_id || "";
  const heading = useMemo(() => detail ? "Plan details" : "Plan your next local birding outing", [detail]);

  async function refreshPlans(selectLatest = false) {
    const rows = await listPlans();
    setPlans(rows);
    if (selectLatest && rows[0]) setDetail(await getPlan(rows[0].trip_plan_id));
  }

  useEffect(() => {
    refreshPlans(true).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load plans"))
      .finally(() => setLoadingHistory(false));
  }, []);

  async function choosePlan(id: string) {
    if (!id) { setDetail(null); return; }
    setLoadingPlan(true); setError(null);
    try { setDetail(await getPlan(id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load the plan"); }
    finally { setLoadingPlan(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const input: CreatePlanInput = {
      location: String(data.get("location") || ""),
      start_at: String(data.get("start_at") || ""),
      duration_minutes: Number(data.get("duration_minutes")),
      skill_level: String(data.get("skill_level") || "") || undefined,
      constraints: String(data.get("constraints") || "") || undefined,
    };
    setLoadingPlan(true); setError(null);
    try {
      const created = await createPlan(input);
      setDetail(created);
      await refreshPlans(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The planner could not complete the request");
    } finally { setLoadingPlan(false); }
  }

  return <>
    <header className="site-header">
      <div><span className="brand-mark" aria-hidden="true">◉</span><strong>Birding Trip Copilot</strong></div>
      <p>Local DuckDB · evidence-backed · Cloudflare GLM</p>
    </header>
    <main>
      <aside className="planner-sidebar" aria-labelledby="planner-heading">
        <p className="eyebrow">Trip planner</p><h1 id="planner-heading">{heading}</h1>
        <form onSubmit={submit}>
          <label htmlFor="location">Location</label>
          <input id="location" name="location" required maxLength={300} placeholder="Thumb Butte or 34.54,-112.47" />
          <label htmlFor="start_at">Start date and time</label>
          <input id="start_at" name="start_at" type="datetime-local" required />
          <label htmlFor="duration_minutes">Duration</label>
          <select id="duration_minutes" name="duration_minutes" defaultValue="90">
            <option value="30">30 minutes</option><option value="60">60 minutes</option>
            <option value="90">90 minutes</option><option value="120">2 hours</option>
            <option value="180">3 hours</option>
          </select>
          <label htmlFor="skill_level">Skill level <span>(optional)</span></label>
          <select id="skill_level" name="skill_level" defaultValue="">
            <option value="">Not specified</option><option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option><option value="advanced">Advanced</option>
          </select>
          <label htmlFor="constraints">Constraints or focus <span>(optional)</span></label>
          <textarea id="constraints" name="constraints" maxLength={1000} rows={3} placeholder="Accessible walk, focus on calls…" />
          <button type="submit" disabled={loadingPlan}>{loadingPlan ? "Planning…" : "Create trip plan"}</button>
        </form>
        <hr />
        <label htmlFor="plan-history">Previous plans</label>
        <select id="plan-history" value={selectedId} onChange={(event) => void choosePlan(event.target.value)} disabled={loadingHistory || loadingPlan}>
          <option value="">{loadingHistory ? "Loading plans…" : "Select a saved plan"}</option>
          {plans.map((plan) => <option key={plan.trip_plan_id} value={plan.trip_plan_id}>{plan.normalized_location_name || plan.requested_location} · {new Date(plan.window_start).toLocaleDateString()}</option>)}
        </select>
      </aside>
      <section className="content" aria-busy={loadingPlan}>
        {error && <div className="error" role="alert"><strong>Could not complete that request.</strong><span>{error}</span></div>}
        {loadingPlan && <div className="loading" role="status">Gathering local evidence and building your field plan…</div>}
        {!loadingPlan && detail && <PlanView detail={detail} />}
        {!loadingPlan && !detail && !error && <div className="welcome"><span aria-hidden="true">⌁</span><h2>No trip selected</h2><p>Create a plan or choose a saved plan to see recommendations, evidence, and the agent workflow.</p></div>}
      </section>
    </main>
  </>;
}
