import { FormEvent, MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPlan, getPlan, listPlans } from "./api";
import rufousImage from "./assets/rufous.png";
import { BirdCatalogPage, BirdProfilePage } from "./BirdPages";
import LocationCombobox from "./LocationCombobox";
import { MyBirdsPage } from "./MyBirds";
import { TripCalendarControls } from "./TripCalendarControls";
import { TargetBirdPage } from "./TargetBird";
import type {
  CreatePlanInput,
  Evidence,
  LocationSuggestion,
  PlanSummary,
  Recommendation,
  TripPlanDetail,
} from "./types";
import { presentWeather } from "./weather";
import "./styles.css";

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

type UnknownRecord = Record<string, unknown>;

function record(value: unknown): UnknownRecord | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as UnknownRecord
    : null;
}

function safeCaveats(value: unknown): { valid: boolean; values: string[] } {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    return { valid: false, values: [] };
  }
  return { valid: true, values: value.map((item) => item.trim()).filter(Boolean) };
}

function normalizeSpecies(value: unknown): string | null {
  const words = text(value)?.split(/\s+/);
  if (!words || words.length < 2 || !/^[A-Za-z]+$/.test(words[0]) || !/^[A-Za-z-]+$/.test(words[1])) {
    return null;
  }
  return `${words[0][0].toUpperCase()}${words[0].slice(1).toLowerCase()} ${words[1].toLowerCase()}`;
}

function mediaSpeciesMatches(row: Recommendation, value: unknown): boolean {
  const owningScientific = normalizeSpecies(row.scientific_name);
  if (owningScientific) return normalizeSpecies(value) === owningScientific;
  const owningCommon = text(row.common_name);
  const mediaName = text(value);
  return Boolean(owningCommon && mediaName && owningCommon === mediaName);
}

const creativeCommonsHosts = new Set(["creativecommons.org", "www.creativecommons.org"]);
const creativeCommonsSlugs = new Set(["by", "by-sa", "by-nc", "by-nc-sa"]);
const creativeCommonsAudioNdSlugs = new Set(["by-nd", "by-nc-nd"]);
const creativeCommonsVersions = new Set(["1.0", "2.0", "2.5", "3.0", "4.0"]);

function canonicalRecordingId(value: unknown): string | null {
  return typeof value === "string" && /^(?:0|[1-9]\d*)$/.test(value) ? value : null;
}

function canonicalSourceRecordingId(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const match = /^(?:XC)?(0|[1-9]\d*)$/i.exec(value);
  return match ? match[1] : null;
}

function safeXenoCantoUrl(
  value: unknown,
  kind: "source" | "audio",
): { href: string; recordingId: string } | null {
  if (typeof value !== "string") return null;
  const grammar = kind === "source"
    ? /^https:\/\/(?:xeno-canto\.org|www\.xeno-canto\.org)\/(\d+)\/?$/
    : /^https:\/\/(?:xeno-canto\.org|www\.xeno-canto\.org)\/(\d+)\/download\/?$/;
  const match = grammar.exec(value);
  return match && match[0] === value ? { href: value, recordingId: match[1] } : null;
}

function safeLicense(
  urlValue: unknown,
  labelValue: unknown,
  allowAudioNd = false,
): { href: string; code: string } | null {
  const rawUrl = text(urlValue);
  const label = text(labelValue)?.replace(/\s+/g, " ").toUpperCase();
  if (!rawUrl || !label) return null;
  try {
    const url = new URL(rawUrl);
    if (
      url.href !== rawUrl
      || url.protocol !== "https:"
      || !creativeCommonsHosts.has(url.hostname)
      || url.username
      || url.password
      || url.port
      || url.search
      || url.hash
    ) return null;
    const standard = /^\/licenses\/([a-z0-9-]+)\/([0-9]+(?:\.[0-9]+)?)\/?$/.exec(url.pathname);
    let code: string | null = null;
    if (standard) {
      const allowedSlug = creativeCommonsSlugs.has(standard[1])
        || (allowAudioNd && creativeCommonsAudioNdSlugs.has(standard[1]));
      if (allowedSlug && creativeCommonsVersions.has(standard[2])) {
        code = `CC ${standard[1].toUpperCase()} ${standard[2]}`;
      }
    } else if (/^\/publicdomain\/zero\/1\.0\/?$/.test(url.pathname)) {
      code = "CC0 1.0";
    }
    return code && label === code ? { href: url.href, code } : null;
  } catch {
    return null;
  }
}

function safeGbifPhotoUrl(value: unknown, occurrenceId: string | null): string | null {
  const raw = text(value);
  if (!raw || !occurrenceId || !/^[1-9]\d*$/.test(occurrenceId)) return null;
  const grammar = /^https:\/\/api\.gbif\.org\/v1\/image\/cache\/500x500\/occurrence\/([1-9]\d*)\/media\/([0-9a-f]{32})$/;
  const match = grammar.exec(raw);
  return match && match[0] === raw && match[1] === occurrenceId ? raw : null;
}

function safeGbifSourceUrl(value: unknown, occurrenceId: string | null): string | null {
  const raw = text(value);
  if (!raw || !occurrenceId || !/^[1-9]\d*$/.test(occurrenceId)) return null;
  const match = /^https:\/\/(?:gbif\.org|www\.gbif\.org)\/occurrence\/([1-9]\d*)\/?$/.exec(raw);
  return match && match[0] === raw && match[1] === occurrenceId ? raw : null;
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

function birdName(row: Recommendation): string {
  return row.common_name || row.scientific_name || row.species_code || "Unknown species";
}

function PhotoArea({ row }: { row: Recommendation }) {
  const [loadFailed, setLoadFailed] = useState(false);
  const photo = record(row.photo);
  const caveats = safeCaveats(photo?.caveats);
  const status = text(photo?.status);
  const occurrenceId = text(photo?.source_record_id);
  const identityMatches = mediaSpeciesMatches(row, photo?.species_name);
  const displayUrl = safeGbifPhotoUrl(photo?.display_url, occurrenceId);
  const sourceUrl = identityMatches ? safeGbifSourceUrl(photo?.source_url, occurrenceId) : null;
  const creator = text(photo?.creator);
  const rightsHolder = text(photo?.rights_holder);
  const publisher = text(photo?.publisher);
  const licenseText = text(photo?.license_text);
  const license = safeLicense(photo?.license_url, licenseText);
  const metadataTrusted = Boolean(photo && identityMatches);
  const available = Boolean(
    metadataTrusted && caveats.valid && status === "available"
    && displayUrl && sourceUrl && license && (creator || rightsHolder),
  );
  const name = birdName(row);
  const alt = row.common_name && row.scientific_name
    ? `${row.common_name} (${row.scientific_name})`
    : name;

  return <figure className="recommendation-photo">
    <div className="photo-frame">
      {available && !loadFailed
        ? <img className="responsive-bird-photo" src={displayUrl!} alt={alt} loading="lazy" onError={() => setLoadFailed(true)} />
        : <div className="media-placeholder">{loadFailed ? "Photo could not be loaded." : "No licensed photo is available."}</div>}
    </div>
    <figcaption className="media-metadata">
      {metadataTrusted ? <>
        {creator && <span>Creator: {creator}</span>}
        {rightsHolder && <span>Rights holder: {rightsHolder}</span>}
        {publisher && <span>Publisher: {publisher}</span>}
        {license
          ? <span>License: <a href={license.href} target="_blank" rel="noreferrer">{license.code}</a></span>
          : (licenseText || status === "available") && <span>License: unavailable</span>}
        {sourceUrl
          ? <a href={sourceUrl} target="_blank" rel="noreferrer">View photo source on GBIF</a>
          : status === "available" && <span className="empty">GBIF photo source page unavailable.</span>}
        {caveats.values.map((caveat) => <span className="caveat" key={caveat}>{caveat}</span>)}
      </> : photo && <span className="caveat">Photo metadata did not match this recommendation.</span>}
    </figcaption>
  </figure>;
}

function CallArea({ row }: { row: Recommendation }) {
  const [playbackFailed, setPlaybackFailed] = useState(false);
  const call = record(row.call);
  const caveats = safeCaveats(call?.caveats);
  const status = text(call?.status);
  const recordingId = canonicalRecordingId(call?.recording_id);
  const sourceRecordId = canonicalSourceRecordingId(call?.source_record_id);
  const source = safeXenoCantoUrl(call?.source_url, "source");
  const audio = safeXenoCantoUrl(call?.audio_url, "audio");
  const sourceMatches = Boolean(
    recordingId && sourceRecordId === recordingId && source?.recordingId === recordingId,
  );
  const audioMatches = Boolean(
    recordingId && sourceRecordId === recordingId && audio?.recordingId === recordingId,
  );
  const idsConsistent = Boolean(
    recordingId && sourceRecordId === recordingId
    && (!source || source.recordingId === recordingId)
    && (!audio || audio.recordingId === recordingId),
  );
  const idsMatch = sourceMatches && audioMatches;
  const identityMatches = mediaSpeciesMatches(row, call?.species_name);
  const metadataTrusted = Boolean(call && identityMatches && idsConsistent);
  const sourceUrl = sourceMatches && metadataTrusted ? source!.href : null;
  const audioUrl = audioMatches && metadataTrusted ? audio!.href : null;
  const licenseText = text(call?.license_text);
  const license = safeLicense(call?.license_url, licenseText, true);
  const scopeValue = text(call?.geographic_scope);
  const scope = scopeValue === "Arizona"
    ? "Arizona recording"
    : scopeValue === "Global example" ? "Global example" : null;
  const recordingType = text(call?.recording_type);
  const quality = text(call?.quality);
  const recordist = text(call?.recordist);
  const available = Boolean(
    metadataTrusted && caveats.valid && status === "available"
    && idsMatch && audioUrl && sourceUrl && license && recordist && scope,
  );
  const context = [birdName(row), recordingType, quality ? `Quality ${quality}` : null]
    .filter(Boolean).join(" · ");

  return <div className="recommendation-call">
    <h4>Call example</h4>
    {available && !playbackFailed
      ? <audio aria-label={`Play ${context}`} controls preload="none" src={audioUrl!} onError={() => setPlaybackFailed(true)} />
      : <p className="media-placeholder">{playbackFailed ? "Call playback failed." : "No licensed call example is available."}</p>}
    <div className="media-metadata">
      {metadataTrusted ? <>
        {scope && <span>{scope}</span>}
        {recordingType && <span>Type: {recordingType}</span>}
        {quality && <span>Quality: {quality}</span>}
        {recordist && <span>Recordist: {recordist}</span>}
        {license
          ? <span>License: <a href={license.href} target="_blank" rel="noreferrer">{license.code}</a></span>
          : (licenseText || status === "available") && <span>License: unavailable</span>}
        {sourceUrl
          ? <a href={sourceUrl} target="_blank" rel="noreferrer">View call source on Xeno-canto</a>
          : status === "available" && <span className="empty">Xeno-canto source page unavailable.</span>}
        {caveats.values.map((caveat) => <span className="caveat" key={caveat}>{caveat}</span>)}
      </> : call && <span className="caveat">Call metadata did not match this recommendation.</span>}
    </div>
  </div>;
}

const RECOMMENDATIONS_PER_PAGE = 4;
const EVIDENCE_PAGE_SIZES = [20, 50, 100] as const;

function PaginationControls({
  label, start, end, total, previousDisabled, nextDisabled, onPrevious, onNext,
}: {
  label: string;
  start: number;
  end: number;
  total: number;
  previousDisabled: boolean;
  nextDisabled: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return <nav className="pagination" aria-label={`${label} pagination`}>
    <span>Showing {total === 0 ? "0" : `${start}–${end}`} of {total}</span>
    <div>
      <button type="button" aria-label={`Previous ${label} page`} disabled={previousDisabled} onClick={onPrevious}>Previous</button>
      <button type="button" aria-label={`Next ${label} page`} disabled={nextDisabled} onClick={onNext}>Next</button>
    </div>
  </nav>;
}

function RecommendationGroup({
  title, rows, planId,
}: {
  title: string;
  rows: Recommendation[];
  planId: string;
}) {
  const [page, setPage] = useState(0);
  const lastPage = Math.max(0, Math.ceil(rows.length / RECOMMENDATIONS_PER_PAGE) - 1);
  const currentPage = Math.min(page, lastPage);
  const startIndex = currentPage * RECOMMENDATIONS_PER_PAGE;
  const visible = rows.slice(startIndex, startIndex + RECOMMENDATIONS_PER_PAGE);

  useEffect(() => setPage(0), [planId]);
  useEffect(() => {
    if (page > lastPage) setPage(lastPage);
  }, [lastPage, page]);

  return (
    <section className="panel recommendation-group" aria-labelledby={`group-${title.replaceAll(" ", "-")}`}>
      <h2 id={`group-${title.replaceAll(" ", "-")}`}>{title}</h2>
      {rows.length === 0 ? (
        <p className="empty">No supported targets in this group.</p>
      ) : <>
        <ol className="species-grid">
          {visible.map((row) => (
            <li key={row.recommendation_id} className="species-card" data-recommendation-id={row.recommendation_id}>
              <PhotoArea row={row} />
              <div className="species-rank">#{row.rank_order}</div>
              <h3>{birdName(row)}</h3>
              {row.common_name && row.scientific_name && <p className="scientific">{row.scientific_name}</p>}
              <span className="badge">{row.confidence_label || "evidence-backed"}</span>
              {row.rationale_text && <p>{row.rationale_text}</p>}
              {row.caveats.map((caveat) => <p className="caveat" key={caveat}>{caveat}</p>)}
              <CallArea row={row} />
            </li>
          ))}
        </ol>
        {rows.length > RECOMMENDATIONS_PER_PAGE && <PaginationControls
          label={title}
          start={startIndex + 1}
          end={startIndex + visible.length}
          total={rows.length}
          previousDisabled={currentPage === 0}
          nextDisabled={currentPage === lastPage}
          onPrevious={() => setPage((value) => Math.max(0, value - 1))}
          onNext={() => setPage((value) => Math.min(lastPage, value + 1))}
        />}
      </>}
    </section>
  );
}

function PlanView({ detail, onCalendarChange }: { detail: TripPlanDetail; onCalendarChange: (invite: TripPlanDetail["calendar_invite"]) => void }) {
  const high = detail.recommendations
    .filter((row) => row.recommendation_group === "high_likelihood")
    .sort((left, right) => left.rank_order - right.rank_order);
  const uncommon = detail.recommendations
    .filter((row) => row.recommendation_group === "uncommon_plausible")
    .sort((left, right) => left.rank_order - right.rank_order);
  const weather = presentWeather(detail.weather?.payload || {}, detail.weather?.summary || {});
  const [evidencePage, setEvidencePage] = useState(0);
  const [evidencePageSize, setEvidencePageSize] = useState<number>(20);
  const lastEvidencePage = Math.max(0, Math.ceil(detail.evidence.length / evidencePageSize) - 1);
  const currentEvidencePage = Math.min(evidencePage, lastEvidencePage);
  const evidenceStart = currentEvidencePage * evidencePageSize;
  const visibleEvidence = detail.evidence.slice(evidenceStart, evidenceStart + evidencePageSize);

  useEffect(() => setEvidencePage(0), [detail.plan.trip_plan_id]);

  return (
    <div className="plan" aria-live="polite">
      <section className="hero-card">
        <p className="eyebrow">Persisted trip plan</p>
        <h1>{detail.plan.normalized_location_name || detail.plan.requested_location}</h1>
        <div className="summary-grid">
          <div><strong>{new Date(detail.plan.window_start).toLocaleString()}</strong><span>Start</span></div>
          <div><strong>{detail.plan.duration_minutes} min</strong><span>Duration</span></div>
          <div><strong>{weather.elevation}</strong><span>Elevation</span></div>
          <div><strong>{weather.condition}</strong><span>Forecast conditions</span></div>
        </div>
      </section>

      <TripCalendarControls planId={detail.plan.trip_plan_id} invite={detail.calendar_invite} onChange={onCalendarChange} />

      {detail.plan.caveats.length > 0 && (
        <section className="notice" aria-labelledby="plan-caveats">
          <h2 id="plan-caveats">Plan caveats</h2>
          <ul>{detail.plan.caveats.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      )}

      <section className="panel" aria-labelledby="field-plan">
        <h2 id="field-plan">Field Plan</h2>
        <p className="field-plan">{detail.plan.field_plan_text || "No field plan was persisted."}</p>
      </section>

      <section className="panel" aria-labelledby="weather-context">
        <h2 id="weather-context">Weather and Elevation</h2>
        {detail.weather ? <>
          <dl className="details-list weather-details">
            {weather.metrics.map((metric) => <div key={metric.label}>
              <dt>{metric.label}</dt><dd>{metric.value}</dd>
            </div>)}
          </dl>
          {detail.weather.caveats.length > 0 && (
            <ul className="weather-caveats">
              {detail.weather.caveats.map((item) => <li key={item}>{item}</li>)}
            </ul>
          )}
          <p className="source-status">Open-Meteo source status: {detail.weather.status}</p>
        </> : <p className="empty">Open-Meteo context was not persisted.</p>}
      </section>

      <RecommendationGroup title="High-likelihood Species" rows={high} planId={detail.plan.trip_plan_id} />
      <RecommendationGroup title="Uncommon but Plausible Targets" rows={uncommon} planId={detail.plan.trip_plan_id} />

      <details className="panel table-panel evidence-disclosure">
        <summary><h2>Evidence and Provenance</h2></summary>
        <div className="evidence-content">
          <div className="page-size-control">
            <label htmlFor={`evidence-page-size-${detail.plan.trip_plan_id}`}>Evidence rows per page</label>
            <select
              id={`evidence-page-size-${detail.plan.trip_plan_id}`}
              value={evidencePageSize}
              onChange={(event) => {
                setEvidencePageSize(Number(event.target.value));
                setEvidencePage(0);
              }}
            >
              {EVIDENCE_PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </div>
          {detail.evidence.length === 0 ? <p className="empty">No evidence was persisted.</p> : (
            <div className="table-scroll"><table>
              <thead><tr><th>Source</th><th>Status</th><th>Type</th><th>Summary</th><th>Record</th></tr></thead>
              <tbody>{visibleEvidence.map((row) => <tr key={row.evidence_id}>
                <td>{row.source}</td><td>{row.status}</td><td>{row.evidence_type.replaceAll("_", " ")}</td>
                <td>{evidenceSummary(row)}</td><td>{row.source_record_id || "—"}</td>
              </tr>)}</tbody>
            </table></div>
          )}
          <PaginationControls
            label="evidence"
            start={evidenceStart + 1}
            end={evidenceStart + visibleEvidence.length}
            total={detail.evidence.length}
            previousDisabled={currentEvidencePage === 0}
            nextDisabled={currentEvidencePage === lastEvidencePage}
            onPrevious={() => setEvidencePage((value) => Math.max(0, value - 1))}
            onNext={() => setEvidencePage((value) => Math.min(lastEvidencePage, value + 1))}
          />
          <details className="workflow-disclosure">
            <summary>Agent Workflow</summary>
            <ol className="timeline">{detail.tool_traces.map((trace) => <li key={trace.tool_trace_id}>
              <span className={`status-dot ${trace.tool_status}`} aria-hidden="true" />
              <div><strong>{trace.step_order}. {trace.tool_name.replaceAll("_", " ")}</strong>
              <span>{trace.tool_status}</span>
              {trace.caveats.map((item) => <p className="caveat" key={item}>{item}</p>)}</div>
            </li>)}</ol>
          </details>
        </div>
      </details>
    </div>
  );
}

function PlannerPage() {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [detail, setDetail] = useState<TripPlanDetail | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [location, setLocation] = useState("");
  const [locationSelection, setLocationSelection] = useState<LocationSuggestion | null>(null);

  const selectedId = detail?.plan.trip_plan_id || "";
  const heading = useMemo(() => detail ? "Plan details" : "Plan your next local birding outing", [detail]);

  async function refreshPlans(selectLatest = false) {
    const rows = await listPlans();
    setPlans(rows);
    if (selectLatest && rows[0]) setDetail(await getPlan(rows[0].trip_plan_id));
  }

  useEffect(() => {
    headingRef.current?.focus();
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
      location,
      location_selection: locationSelection || undefined,
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

  return <main>
      <aside className="planner-sidebar" aria-labelledby="planner-heading">
        <p className="eyebrow">Trip planner</p><h1 ref={headingRef} id="planner-heading" tabIndex={-1}>{heading}</h1>
        <form onSubmit={submit}>
          <label htmlFor="location">Location</label>
          <LocationCombobox
            value={location}
            selected={locationSelection}
            disabled={loadingPlan}
            onChange={(value) => {
              setLocation(value);
              setLocationSelection(null);
            }}
            onSelect={(selected) => {
              setLocation(selected.display_name);
              setLocationSelection(selected);
            }}
          />
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
        {!loadingPlan && detail && <PlanView key={detail.plan.trip_plan_id} detail={detail} onCalendarChange={(calendar_invite) => setDetail((current) => current && current.plan.trip_plan_id === detail.plan.trip_plan_id ? { ...current, calendar_invite } : current)} />}
        {!loadingPlan && !detail && !error && <div className="welcome"><span aria-hidden="true">⌁</span><h2>No trip selected</h2><p>Create a plan or choose a saved plan to see recommendations, evidence, and the agent workflow.</p></div>}
      </section>
    </main>;
}

type Route = { page: "planner" } | { page: "birds" } | { page: "bird"; speciesCode: string } | { page: "target-find"; speciesCode: string } | { page: "target-plan"; planId: string } | { page: "my-birds" };

function currentRoute(): Route {
  if (window.location.pathname === "/my-birds") return { page: "my-birds" };
  if (window.location.pathname === "/birds") return { page: "birds" };
  const targetPlan = /^\/target-plans\/(target_[0-9a-f]{32})$/.exec(window.location.pathname);
  if (targetPlan) return { page: "target-plan", planId: targetPlan[1] };
  const find = /^\/birds\/([^/]+)\/find$/.exec(window.location.pathname);
  if (find) {
    try { return { page: "target-find", speciesCode: decodeURIComponent(find[1]) }; }
    catch { return { page: "target-find", speciesCode: "invalid-species-code" }; }
  }
  const match = /^\/birds\/([^/]+)$/.exec(window.location.pathname);
  if (match) {
    try { return { page: "bird", speciesCode: decodeURIComponent(match[1]) }; }
    catch { return { page: "bird", speciesCode: "invalid-species-code" }; }
  }
  return { page: "planner" };
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => currentRoute());

  useEffect(() => {
    const handlePopState = () => setRoute(currentRoute());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    document.title = route.page === "planner"
      ? "Trip Planner · Rufous"
      : route.page === "birds"
        ? "Arizona Birds · Rufous"
        : route.page === "my-birds"
          ? "My Birds · Rufous"
          : route.page === "target-find" || route.page === "target-plan"
            ? "Find This Bird · Rufous"
            : "Bird Profile · Arizona Birds · Rufous";
  }, [route]);

  function navigate(path: string) {
    if (window.location.pathname !== path) window.history.pushState(null, "", path);
    setRoute(currentRoute());
  }

  function navClick(event: MouseEvent<HTMLAnchorElement>, path: string) {
    if (!event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault();
      navigate(path);
    }
  }

  const birdsActive = route.page === "birds" || route.page === "bird" || route.page === "target-find" || route.page === "target-plan";
  return <>
    <header className="site-header">
      <div className="site-brand">
        <img className="brand-mark" src={rufousImage} alt="" aria-hidden="true" />
        <span><strong>Rufous</strong><small>Arizona field console</small></span>
      </div>
      <nav aria-label="Primary navigation">
        <a href="/" aria-current={route.page === "planner" ? "page" : undefined} onClick={(event) => navClick(event, "/")}>Trip Planner</a>
        <a href="/birds" aria-current={birdsActive ? "page" : undefined} onClick={(event) => navClick(event, "/birds")}>Arizona Birds</a>
        <a href="/my-birds" aria-current={route.page === "my-birds" ? "page" : undefined} onClick={(event) => navClick(event, "/my-birds")}>My Birds</a>
      </nav>
      <p>Local DuckDB · evidence-backed</p>
    </header>
    {route.page === "planner" && <PlannerPage />}
    {route.page === "birds" && <BirdCatalogPage navigate={navigate} />}
    {route.page === "bird" && <BirdProfilePage speciesCode={route.speciesCode} navigate={navigate} />}
    {route.page === "target-find" && <TargetBirdPage speciesCode={route.speciesCode} navigate={navigate} />}
    {route.page === "target-plan" && <TargetBirdPage planId={route.planId} navigate={navigate} />}
    {route.page === "my-birds" && <MyBirdsPage navigate={navigate} />}
  </>;
}
