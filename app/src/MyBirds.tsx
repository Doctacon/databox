import { FormEvent, MouseEvent, type Ref, useEffect, useMemo, useRef, useState } from "react";
import LocationCombobox from "./LocationCombobox";
import { listAlertDeliveries, markAlertDelivered, markAlertNotDelivered, retryAlertDelivery } from "./alertDeliveryApi";
import { startCollectionMutation, useCollectionMutationBusy, useCollectionRevision } from "./collectionMutation";
import { listBirds } from "./birdApi";
import {
  createObservation,
  deleteObservation,
  deleteWatch,
  getCollectionState,
  listLifeList,
  listObservations,
  listWatches,
  saveWatch,
  setWatchActive,
  updateObservation,
} from "./collectionApi";
import { compareVisibleLabels } from "./visibleLabel";
import type {
  AlertDelivery,
  BirdCatalogSummary,
  BirdProfile,
  BirdWatch,
  CollectionState,
  LifeListEntry,
  LocationSuggestion,
  PersonalObservation,
} from "./types";

type Navigate = (path: string) => void;
type Tab = "life" | "observations" | "watches" | "alerts";

function clickLink(event: MouseEvent<HTMLAnchorElement>, path: string, navigate: Navigate) {
  if (!event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
    event.preventDefault(); navigate(path);
  }
}
function dateLabel(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])).toLocaleDateString() : "Not available";
}
function birdLabel(speciesCode: string, identity?: { common_name: string | null; scientific_name: string | null }) {
  return identity?.common_name || identity?.scientific_name || speciesCode;
}
function birdOption(bird: BirdCatalogSummary) {
  return `${bird.common_name || bird.scientific_name || bird.species_code}${bird.taxonomic_category === "hybrid" ? " · Hybrid" : ""} · ${bird.species_code}`;
}
function ErrorBox({ error, errorRef }: { error: string | null; errorRef?: Ref<HTMLDivElement> }) {
  return error ? <div ref={errorRef} className="error" role="alert" tabIndex={-1}><strong>Could not update My Birds.</strong><span>{error}</span></div> : null;
}
function Stale({ status }: { status: "current" | "stale" }) {
  return status === "stale" ? <span className="badge warning">No longer in the current Arizona catalog</span> : null;
}
function ConfirmDialog({ title, children, busy, confirmLabel, onCancel, onConfirm }: { title: string; children: string; busy: boolean; confirmLabel: string; onCancel: () => void; onConfirm: () => void }) {
  const headingId = `confirm-${confirmLabel.toLowerCase().replaceAll(" ", "-")}`;
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    cancelRef.current?.focus();
    return () => previous?.focus();
  }, []);
  return <div className="modal-backdrop" onKeyDown={(event) => {
    if (event.key === "Escape" && !busy) onCancel();
    if (event.key === "Tab" && !event.shiftKey && event.target === confirmRef.current) { event.preventDefault(); cancelRef.current?.focus(); }
    if (event.key === "Tab" && event.shiftKey && event.target === cancelRef.current) { event.preventDefault(); confirmRef.current?.focus(); }
  }}><div role="dialog" aria-modal="true" aria-labelledby={headingId} className="confirm-dialog"><h2 id={headingId}>{title}</h2><p>{children}</p><div className="button-row"><button ref={cancelRef} type="button" className="secondary" onClick={onCancel}>Cancel</button><button ref={confirmRef} type="button" className="danger" disabled={busy} onClick={onConfirm}>{confirmLabel}</button></div></div></div>;
}

interface ObservationFormProps {
  birds: BirdCatalogSummary[];
  initial?: PersonalObservation | null;
  fixedSpeciesCode?: string;
  busy: boolean;
  onCancel?: () => void;
  onSave: (input: { species_code: string; observation_date: string; location: string | null; notes: string | null }) => Promise<boolean>;
}
function ObservationForm({ birds, initial = null, fixedSpeciesCode, busy, onCancel, onSave }: ObservationFormProps) {
  const [speciesCode, setSpeciesCode] = useState(fixedSpeciesCode || initial?.species_code || birds[0]?.species_code || "");
  const [observationDate, setObservationDate] = useState(initial?.observation_date || "");
  const [location, setLocation] = useState(initial?.location || "");
  const [notes, setNotes] = useState(initial?.notes || "");
  useEffect(() => { if (fixedSpeciesCode) setSpeciesCode(fixedSpeciesCode); }, [fixedSpeciesCode]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    const saved = await onSave({ species_code: speciesCode, observation_date: observationDate, location: location.trim() || null, notes: notes.trim() || null });
    if (saved && !initial) { setObservationDate(""); setLocation(""); setNotes(""); }
  }
  return <form className="collection-form" onSubmit={(event) => void submit(event)}>
    {!fixedSpeciesCode && <div><label htmlFor={`observation-species-${initial?.observation_id || "new"}`}>Bird</label><select id={`observation-species-${initial?.observation_id || "new"}`} required value={speciesCode} onChange={(event) => setSpeciesCode(event.target.value)}>{birds.map((bird) => <option key={bird.species_code} value={bird.species_code}>{birdOption(bird)}</option>)}</select></div>}
    <div><label htmlFor={`observation-date-${initial?.observation_id || fixedSpeciesCode || "new"}`}>Observation date</label><input id={`observation-date-${initial?.observation_id || fixedSpeciesCode || "new"}`} type="date" required value={observationDate} onChange={(event) => setObservationDate(event.target.value)} /></div>
    <div><label htmlFor={`observation-location-${initial?.observation_id || fixedSpeciesCode || "new"}`}>Location <span>(optional personal note)</span></label><input id={`observation-location-${initial?.observation_id || fixedSpeciesCode || "new"}`} maxLength={300} value={location} onChange={(event) => setLocation(event.target.value)} /></div>
    <div><label htmlFor={`observation-notes-${initial?.observation_id || fixedSpeciesCode || "new"}`}>Notes <span>(optional)</span></label><textarea id={`observation-notes-${initial?.observation_id || fixedSpeciesCode || "new"}`} maxLength={2000} rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} /></div>
    <div className="button-row"><button type="submit" disabled={busy || !speciesCode || !observationDate}>{busy ? "Saving…" : initial ? "Save changes" : "Record observation"}</button>{onCancel && <button type="button" className="secondary" onClick={onCancel}>Cancel edit</button>}</div>
  </form>;
}

interface WatchFormProps {
  speciesCode: string;
  initial?: BirdWatch | null;
  busy: boolean;
  onCancel?: () => void;
  onSave: (center: LocationSuggestion, radius: number) => Promise<boolean>;
}
function WatchForm({ speciesCode, initial = null, busy, onCancel, onSave }: WatchFormProps) {
  const initialCenter: LocationSuggestion | null = initial ? {
    display_name: initial.center_name, latitude: initial.center_latitude, longitude: initial.center_longitude,
    timezone: initial.center_timezone, region_code: "US-AZ",
  } : null;
  const [location, setLocation] = useState(initial?.center_name || "");
  const [selected, setSelected] = useState<LocationSuggestion | null>(initialCenter);
  const [radius, setRadius] = useState(String(initial?.radius_miles || 25));
  async function submit(event: FormEvent) {
    event.preventDefault();
    const parsed = Number(radius);
    if (selected && parsed >= 1 && parsed <= 300) await onSave(selected, parsed);
  }
  return <form className="collection-form" onSubmit={(event) => void submit(event)}>
    <label htmlFor={`watch-location-${speciesCode}`}>Watch center</label>
    <LocationCombobox inputId={`watch-location-${speciesCode}`} value={location} selected={selected} disabled={busy} onChange={(value) => { setLocation(value); setSelected(null); }} onSelect={(center) => { setLocation(center.display_name); setSelected(center); }} />
    <div><label htmlFor={`watch-radius-${speciesCode}`}>Travel radius (miles)</label><input id={`watch-radius-${speciesCode}`} type="number" min="1" max="300" step="0.1" required value={radius} onChange={(event) => setRadius(event.target.value)} /></div>
    <p className="source-status">This center belongs only to this watch. Rufous does not save a global home location.</p>
    <div className="button-row"><button type="submit" disabled={busy || !selected}>{busy ? "Saving…" : initial ? "Save watch" : "Start watching"}</button>{onCancel && <button type="button" className="secondary" onClick={onCancel}>Cancel</button>}</div>
  </form>;
}

export function MyBirdsPage({ navigate }: { navigate: Navigate }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [tab, setTab] = useState<Tab>("life");
  const [birds, setBirds] = useState<BirdCatalogSummary[]>([]);
  const [observations, setObservations] = useState<PersonalObservation[]>([]);
  const [life, setLife] = useState<LifeListEntry[]>([]);
  const [watches, setWatches] = useState<BirdWatch[]>([]);
  const [deliveries, setDeliveries] = useState<AlertDelivery[]>([]);
  const [collectionLoaded, setCollectionLoaded] = useState(false);
  const [alertLoaded, setAlertLoaded] = useState(false);
  const [alertBusy, setAlertBusy] = useState(false);
  const [alertLoading, setAlertLoading] = useState(false);
  const [deliveryRevision, setDeliveryRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const busy = useCollectionMutationBusy();
  const collectionRevision = useCollectionRevision();
  const loadGeneration = useRef(0);
  const errorRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [editingObservation, setEditingObservation] = useState<PersonalObservation | null>(null);
  const [editingWatch, setEditingWatch] = useState<BirdWatch | null>(null);
  const [deletingObservation, setDeletingObservation] = useState<PersonalObservation | null>(null);
  const [deletingWatch, setDeletingWatch] = useState<BirdWatch | null>(null);
  const [newWatchSpecies, setNewWatchSpecies] = useState("");

  useEffect(() => {
    let current = true;
    const generation = ++loadGeneration.current;
    void Promise.all([listBirds(), listObservations(), listLifeList(), listWatches()]).then(([catalog, obs, lifeRows, watchRows]) => {
      if (!current || generation !== loadGeneration.current) return;
      setBirds(catalog); setObservations(obs); setLife(lifeRows); setWatches(watchRows); setCollectionLoaded(true);
    }).catch((reason: unknown) => {
      if (current && generation === loadGeneration.current) setError(reason instanceof Error ? reason.message : "My Birds is unavailable.");
    }).finally(() => {
      if (current && generation === loadGeneration.current) setLoading(false);
    });
    return () => { current = false; };
  }, [collectionRevision]);
  useEffect(() => {
    if (tab !== "alerts") return;
    let current = true; setAlertLoading(true);
    void listAlertDeliveries().then((rows) => { if (current) { setDeliveries(rows); setAlertLoaded(true); } })
      .catch((reason: unknown) => { if (current) setError(reason instanceof Error ? reason.message : "Alert delivery status is unavailable."); })
      .finally(() => { if (current) setAlertLoading(false); });
    return () => { current = false; };
  }, [tab, deliveryRevision]);
  useEffect(() => headingRef.current?.focus(), []);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);

  async function mutate(action: () => Promise<void>, success: string): Promise<boolean> {
    const mutation = startCollectionMutation(action);
    if (!mutation.started) return false;
    setError(null); setStatus(null);
    try { await mutation.result; setStatus(success); return true; }
    catch (reason) { setError(reason instanceof Error ? reason.message : "My Birds is unavailable."); return false; }
  }
  async function mutateAlert(action: () => Promise<string>, success: string) {
    if (alertBusy) return;
    setAlertBusy(true); setError(null); setStatus(null);
    try { await action(); setStatus(success); setDeliveryRevision((value) => value + 1); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Alert delivery status is unavailable."); }
    finally { setAlertBusy(false); }
  }
  const orderedBirds = useMemo(() => [...birds].sort((left, right) => compareVisibleLabels(
    birdLabel(left.species_code, left), birdLabel(right.species_code, right), left.species_code, right.species_code,
  )), [birds]);
  const availableWatchBirds = useMemo(() => orderedBirds.filter((bird) => !watches.some((watch) => watch.species_code === bird.species_code)), [orderedBirds, watches]);
  useEffect(() => { if (!availableWatchBirds.some((bird) => bird.species_code === newWatchSpecies)) setNewWatchSpecies(availableWatchBirds[0]?.species_code || ""); }, [availableWatchBirds, newWatchSpecies]);

  return <main className="my-birds-main">
    <header className="catalog-heading"><p className="eyebrow">Private local collection</p><h1 ref={headingRef} tabIndex={-1}>My Birds</h1><p>Observations, life list, and watched birds remain in your local DuckDB until you remove them.</p></header>
    <nav className="collection-tabs" aria-label="My Birds sections">{(["life", "observations", "watches", "alerts"] as Tab[]).map((value) => <button key={value} type="button" aria-pressed={tab === value} onClick={() => setTab(value)}>{value === "life" ? "Life List" : value === "alerts" ? "Alert Delivery" : value[0].toUpperCase() + value.slice(1)}</button>)}</nav>
    <ErrorBox error={error} errorRef={errorRef} />{status && <p className="success" role="status">{status}</p>}{loading && <p role="status">Loading your local collection…</p>}
    {!loading && collectionLoaded && tab === "life" && <section className="panel" aria-labelledby="life-list-heading"><h2 id="life-list-heading">Life List</h2>{life.length ? <ul className="collection-list">{life.map((entry) => <li key={entry.species_code}><div><a href={`/birds/${entry.species_code}`} onClick={(event) => clickLink(event, `/birds/${entry.species_code}`, navigate)}><strong>{birdLabel(entry.species_code, entry.identity)}</strong></a><Stale status={entry.identity.catalog_status} /></div><span>{entry.observation_count} observation{entry.observation_count === 1 ? "" : "s"} · first {dateLabel(entry.first_observed_date)} · latest {dateLabel(entry.latest_observed_date)}</span></li>)}</ul> : <p className="empty">Your life list is empty. Record an observation to add a bird.</p>}</section>}
    {!loading && collectionLoaded && tab === "observations" && <section className="panel" aria-labelledby="observations-heading"><h2 id="observations-heading">Observations</h2><details open={!observations.length}><summary>Record a new observation</summary><ObservationForm birds={orderedBirds} busy={busy} onSave={(input) => mutate(() => createObservation(input).then(() => undefined), "Observation recorded.")} /></details>{editingObservation && <div className="nested-panel"><h3>Edit {birdLabel(editingObservation.species_code, editingObservation.identity)}</h3><ObservationForm key={editingObservation.observation_id} birds={orderedBirds} initial={editingObservation} busy={busy} onCancel={() => setEditingObservation(null)} onSave={async (input) => { const saved = await mutate(() => updateObservation(editingObservation.observation_id, input).then(() => undefined), "Observation updated."); if (saved) setEditingObservation(null); return saved; }} /></div>}{observations.length ? <ul className="collection-list">{observations.map((entry) => <li key={entry.observation_id}><div><a href={`/birds/${entry.species_code}`} onClick={(event) => clickLink(event, `/birds/${entry.species_code}`, navigate)}><strong>{birdLabel(entry.species_code, entry.identity)}</strong></a><Stale status={entry.identity.catalog_status} /></div><span>{dateLabel(entry.observation_date)}{entry.location ? ` · ${entry.location}` : ""}</span>{entry.notes && <p>{entry.notes}</p>}<div className="button-row"><button type="button" className="secondary" disabled={busy} onClick={() => setEditingObservation(entry)}>Edit</button><button type="button" className="danger" disabled={busy} onClick={() => setDeletingObservation(entry)}>Delete permanently</button></div></li>)}</ul> : <p className="empty">No observations recorded yet.</p>}</section>}
    {!loading && tab === "alerts" && <section className="panel" aria-labelledby="alerts-heading" aria-busy={alertLoading || alertBusy}><h2 id="alerts-heading">Alert Delivery</h2><p className="source-status">Safe local status only. SMTP configuration, addresses, certificate details, and message bodies are never shown. Delivery acceptance means accepted by the local Bridge, not confirmed inbox or calendar rendering.</p>{alertBusy && <p role="status" aria-live="polite">Updating alert delivery status…</p>}{alertLoading ? <p role="status">Loading alert delivery status…</p> : !alertLoaded ? null : deliveries.length ? <ul className="collection-list">{deliveries.map((delivery) => <li key={delivery.outbox_id}><div><strong>{delivery.species_code}</strong><span className={`badge ${delivery.state === "delivery_unknown" || delivery.state === "failed" ? "warning" : ""}`}>{delivery.state.replaceAll("_", " ")}</span></div><span>{delivery.method} · sequence {delivery.sequence} · {delivery.attempt_count} attempt{delivery.attempt_count === 1 ? "" : "s"} · updated {new Date(delivery.updated_at).toLocaleString()}</span>{delivery.safe_terminal_reason && <p>Reason: {delivery.safe_terminal_reason.replaceAll("_", " ")}</p>}<details><summary>Attempt history</summary>{delivery.attempts.length ? <ol>{delivery.attempts.map((attempt, index) => <li key={`${attempt.occurred_at}-${index}`}>{attempt.phase.replaceAll("_", " ")} · {new Date(attempt.occurred_at).toLocaleString()}</li>)}</ol> : <p>No send attempt has started.</p>}</details><div className="button-row">{delivery.allowed_actions.includes("mark_delivered") && <button type="button" disabled={alertBusy} onClick={() => { if (window.confirm("Mark this ambiguous alert as delivered? This does not verify inbox receipt.")) void mutateAlert(() => markAlertDelivered(delivery.outbox_id), "Alert marked delivered."); }}>Mark delivered</button>}{delivery.allowed_actions.includes("mark_not_delivered") && <button type="button" disabled={alertBusy} onClick={() => { if (window.confirm("Mark this inactive alert as not delivered without retrying it?")) void mutateAlert(() => markAlertNotDelivered(delivery.outbox_id), "Alert marked not delivered."); }}>Mark not delivered</button>}{delivery.allowed_actions.includes("mark_not_delivered_and_retry") && <button type="button" disabled={alertBusy} onClick={() => { if (window.confirm("Mark this alert as not delivered and enqueue one new-sequence retry?")) void mutateAlert(() => retryAlertDelivery(delivery.outbox_id), "Alert retry enqueued."); }}>Mark not delivered and retry</button>}{delivery.allowed_actions.includes("retry_failed") && <button type="button" disabled={alertBusy} onClick={() => { if (window.confirm("Enqueue one new-sequence retry for this failed alert?")) void mutateAlert(() => retryAlertDelivery(delivery.outbox_id), "Alert retry enqueued."); }}>Retry failed delivery</button>}</div></li>)}</ul> : <p className="empty">No alert delivery history is available.</p>}</section>}
    {!loading && collectionLoaded && tab === "watches" && <section className="panel" aria-labelledby="watches-heading"><h2 id="watches-heading">Watches</h2>{availableWatchBirds.length > 0 && <details open={!watches.length}><summary>Create a watch</summary><label htmlFor="new-watch-species">Bird</label><select id="new-watch-species" value={newWatchSpecies} onChange={(event) => setNewWatchSpecies(event.target.value)}>{availableWatchBirds.map((bird) => <option key={bird.species_code} value={bird.species_code}>{birdOption(bird)}</option>)}</select>{newWatchSpecies && <WatchForm speciesCode={newWatchSpecies} busy={busy} onSave={(center, radius) => mutate(() => saveWatch(newWatchSpecies, { center, radius_miles: radius }).then(() => undefined), "Watch created.")} />}</details>}{editingWatch && <div className="nested-panel"><h3>Edit watch for {birdLabel(editingWatch.species_code, editingWatch.identity)}</h3><WatchForm key={editingWatch.species_code} speciesCode={editingWatch.species_code} initial={editingWatch} busy={busy} onCancel={() => setEditingWatch(null)} onSave={async (center, radius) => { const saved = await mutate(() => saveWatch(editingWatch.species_code, { center, radius_miles: radius }).then(() => undefined), "Watch updated."); if (saved) setEditingWatch(null); return saved; }} /></div>}{watches.length ? <ul className="collection-list">{watches.map((entry) => <li key={entry.species_code}><div><a href={`/birds/${entry.species_code}`} onClick={(event) => clickLink(event, `/birds/${entry.species_code}`, navigate)}><strong>{birdLabel(entry.species_code, entry.identity)}</strong></a><span className={`badge ${entry.active ? "" : "warning"}`}>{entry.active ? "Active" : "Paused"}</span><Stale status={entry.identity.catalog_status} /></div><span>{entry.center_name} · {entry.radius_miles.toLocaleString()} miles</span><p className="source-status">This per-watch center does not save a global home location and causes no lookup or delivery until a successful refresh evaluates it.</p><div className="button-row"><button type="button" className="secondary" disabled={busy} onClick={() => setEditingWatch(entry)}>Edit center or radius</button><button type="button" disabled={busy || (entry.identity.catalog_status === "stale" && !entry.active)} onClick={() => void mutate(() => setWatchActive(entry.species_code, !entry.active).then(() => undefined), entry.active ? "Watch paused." : "Watch resumed.")}>{entry.active ? "Pause" : "Resume"}</button><button type="button" className="danger" disabled={busy} onClick={() => setDeletingWatch(entry)}>Delete watch</button></div></li>)}</ul> : <p className="empty">You are not watching any birds.</p>}</section>}
    {deletingObservation && <ConfirmDialog title="Permanently delete this observation?" busy={busy} confirmLabel="Delete permanently" onCancel={() => setDeletingObservation(null)} onConfirm={() => void mutate(() => deleteObservation(deletingObservation.observation_id), "Observation permanently deleted.").then((saved) => { if (saved) setDeletingObservation(null); })}>This cannot be undone. If it is the last observation for this bird, the bird leaves your life list.</ConfirmDialog>}
    {deletingWatch && <ConfirmDialog title="Delete this watch?" busy={busy} confirmLabel="Delete watch" onCancel={() => setDeletingWatch(null)} onConfirm={() => void mutate(() => deleteWatch(deletingWatch.species_code), "Watch deleted.").then((saved) => { if (saved) setDeletingWatch(null); })}>The watch definition is removed. A downstream alert worker may later cancel an accepted active calendar event.</ConfirmDialog>}
  </main>;
}

export function ProfileCollectionControls({ bird }: { bird: BirdProfile }) {
  const [state, setState] = useState<CollectionState | null>(null);
  const busy = useCollectionMutationBusy();
  const collectionRevision = useCollectionRevision();
  const loadGeneration = useRef(0);
  const errorRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    const generation = ++loadGeneration.current;
    void getCollectionState(bird.species_code).then((nextState) => {
      if (current && generation === loadGeneration.current) setState(nextState);
    }).catch((reason: unknown) => {
      if (current && generation === loadGeneration.current) setError(reason instanceof Error ? reason.message : "Collection controls are unavailable.");
    });
    return () => { current = false; };
  }, [bird.species_code, collectionRevision]);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  async function mutate(action: () => Promise<void>, message: string): Promise<boolean> {
    const mutation = startCollectionMutation(action);
    if (!mutation.started) return false;
    setError(null); setStatus(null);
    try { await mutation.result; setStatus(message); return true; }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Collection controls are unavailable."); return false; }
  }
  return <section className="panel collection-profile-controls"><h2>Your collection</h2><p className="source-status">These explicit actions update only your private local collection. They do not run matching, weather, a model, calendar, or email.</p><ErrorBox error={error} errorRef={errorRef} />{status && <p className="success" role="status">{status}</p>}{!state && !error && <p role="status">Loading collection state…</p>}{state && <><ul className="card-status"><li>Observed: {state.observed ? `Yes · ${state.observation_count}` : "No"}</li><li>Watch: {state.watched ? state.watch_active ? "Active" : "Paused" : "None"}</li></ul><details><summary>Record an observation</summary><ObservationForm birds={[bird]} fixedSpeciesCode={bird.species_code} busy={busy} onSave={(input) => mutate(() => createObservation(input).then(() => undefined), "Observation recorded.")} /></details><div className="button-row">{state.watched && <button type="button" disabled={busy || (state.catalog_status === "stale" && !state.watch_active)} onClick={() => void mutate(() => setWatchActive(bird.species_code, !state.watch_active).then(() => undefined), state.watch_active ? "Watch paused." : "Watch resumed.")}>{state.watch_active ? "Pause watch" : "Resume watch"}</button>}{state.watched && <button type="button" className="danger" disabled={busy} onClick={() => { if (window.confirm("Delete this watch?")) void mutate(() => deleteWatch(bird.species_code), "Watch deleted."); }}>Delete watch</button>}</div>{state.watched ? <p><a href="/my-birds">Edit this watch's private center and radius in My Birds.</a></p> : <details><summary>Create a watch</summary><WatchForm speciesCode={bird.species_code} busy={busy} onSave={(center, radius) => mutate(() => saveWatch(bird.species_code, { center, radius_miles: radius }).then(() => undefined), "Watch created.")} /></details>}</>}</section>;
}
