import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import rufousImage from "./assets/rufous.png";
import {
  buildPublishedCalendar,
  downloadPublishedCalendar,
  formatOccurrenceDate,
  formatInTimeZone,
  minimumOutingDate,
  sunriseWindow,
} from "./publicCalendar";
import {
  getPublicAttribution,
  getPublicManifest,
  getPublicSpecies,
  ARIZONA_STATE_RING,
  parseArizonaCoordinates,
  searchPublicPlaces,
} from "./publicData";
import type {
  PublicAttribution,
  PublicManifest,
  PublicPlace,
  PublicSpeciesProfile,
  PublicWatch,
  WatchEvaluation,
} from "./publicTypes";
import {
  createWatchId,
  evaluatePublicWatch,
  readPublicWatches,
  writePublicWatches,
} from "./publicWatch";
import "./styles.css";
import "./publicStyles.css";

type EvaluationState =
  | { status: "loading" }
  | { status: "ready"; value: WatchEvaluation }
  | { status: "error"; message: string };

function birdName(profile: { common_name: string | null; scientific_name: string | null; species_code: string }): string {
  return profile.common_name || profile.scientific_name || profile.species_code;
}

function deterministicGuidance(evaluation: WatchEvaluation): string {
  const match = evaluation.matches[0];
  if (!match) {
    return `Rufous did not find a licensed ${evaluation.watch.bird_name} occurrence inside this watch area in the current static snapshot. Try a wider radius or a different place.`;
  }
  return `Rufous found a licensed historical ${evaluation.watch.bird_name} occurrence near ${match.location.name}, ${match.distance_miles.toFixed(1)} miles from the watch center. The suggested two-hour outing is centered on local sunrise, when bird activity is often strongest.`;
}

function safeExternalUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

function safeDoiUrl(value: string | undefined): string | null {
  if (!value || !/^10\.\d{4,9}\/[A-Z0-9._;()/:+-]+$/i.test(value.trim())) return null;
  return `https://doi.org/${value.trim()}`;
}

function MatchMap({ evaluation, manifest }: { evaluation: WatchEvaluation; manifest: PublicManifest }) {
  const bounds = manifest.region.bounds;
  const width = 640;
  const height = 360;
  const x = (longitude: number) => ((longitude - bounds.west) / (bounds.east - bounds.west)) * width;
  const y = (latitude: number) => height - ((latitude - bounds.south) / (bounds.north - bounds.south)) * height;
  const outline = ARIZONA_STATE_RING.map(([longitude, latitude], index) => `${index === 0 ? "M" : "L"}${x(longitude).toFixed(2)},${y(latitude).toFixed(2)}`).join(" ");
  return <svg className="public-match-map" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="public-map-title public-map-description">
    <title id="public-map-title">Arizona watch evidence map</title>
    <desc id="public-map-description">The watch center and up to fifty matching sanitized public observations.</desc>
    <rect className="public-map-background" x="0" y="0" width={width} height={height} />
    <path className="public-map-region" d={`${outline} Z`} />
    {evaluation.matches.slice(0, 50).map((match) => <circle
      className="public-map-match"
      key={match.public_id}
      cx={x(match.location.longitude)}
      cy={y(match.location.latitude)}
      r={match.is_notable ? 7 : 5}
    ><title>{match.location.name} · {match.distance_miles.toFixed(1)} mi</title></circle>)}
    <circle className="public-map-center" cx={x(evaluation.watch.center_longitude)} cy={y(evaluation.watch.center_latitude)} r="8">
      <title>{evaluation.watch.center_name} watch center</title>
    </circle>
  </svg>;
}

function SpeciesProfile({ profile }: { profile: PublicSpeciesProfile }) {
  const photo = profile.media.find((item) => item.kind === "photo");
  const audio = profile.media.find((item) => item.kind === "audio");
  const photoUrl = photo ? safeExternalUrl(photo.url) : null;
  const audioUrl = audio ? safeExternalUrl(audio.url) : null;
  return <section className="panel public-species-profile" aria-labelledby="public-species-heading">
    <div>
      <p className="eyebrow">Selected Arizona bird</p>
      <h2 id="public-species-heading">{birdName(profile)}</h2>
      {profile.scientific_name && <p className="scientific">{profile.scientific_name}</p>}
      <dl className="details-list bird-facts">
        <div><dt>Family</dt><dd>{profile.family.common_name || profile.family.scientific_name || "Not available"}</dd></div>
        <div><dt>Order</dt><dd>{profile.order_name || "Not available"}</dd></div>
        <div><dt>Licensed occurrences</dt><dd>{profile.evidence.licensed_occurrence_count.toLocaleString()}</dd></div>
      </dl>
    </div>
    <figure className="public-profile-media">
      {photoUrl
        ? <img src={photoUrl} alt={birdName(profile)} loading="lazy" />
        : <div className="media-placeholder"><img src={rufousImage} alt="" aria-hidden="true" /><span>No licensed public photo in this release.</span></div>}
      {photo && <figcaption>Photo: {photo.creator} · <a href={photo.source_url} target="_blank" rel="noreferrer">{photo.provider} source</a> · <a href={photo.license_url} target="_blank" rel="noreferrer">{photo.license}</a></figcaption>}
    </figure>
    {audio && audioUrl && <div className="public-audio"><audio controls preload="none" src={audioUrl} aria-label={`Play a call of ${birdName(profile)}`} /><small>Recording: {audio.creator} · <a href={audio.source_url} target="_blank" rel="noreferrer">source</a> · <a href={audio.license_url} target="_blank" rel="noreferrer">{audio.license}</a></small></div>}
  </section>;
}

export default function PublicApp() {
  const [manifest, setManifest] = useState<PublicManifest | null>(null);
  const [attribution, setAttribution] = useState<PublicAttribution | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [speciesCode, setSpeciesCode] = useState("");
  const [profile, setProfile] = useState<PublicSpeciesProfile | null>(null);
  const [query, setQuery] = useState("");
  const [place, setPlace] = useState<PublicPlace | null>(null);
  const [placeOptions, setPlaceOptions] = useState<PublicPlace[]>([]);
  const [placeStatus, setPlaceStatus] = useState("");
  const [manualTimezone, setManualTimezone] = useState<"" | "America/Phoenix" | "America/Denver">("");
  const [radius, setRadius] = useState(25);
  const [outingDate, setOutingDate] = useState(minimumOutingDate);
  const [watches, setWatches] = useState<PublicWatch[]>(() => readPublicWatches());
  const [evaluations, setEvaluations] = useState<Record<string, EvaluationState>>({});
  const [activeWatchId, setActiveWatchId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [guidance, setGuidance] = useState("");
  const autoEvaluationVersion = useRef<string | null>(null);
  const manualCoordinates = manifest ? parseArizonaCoordinates(query, manifest.region.bounds) : null;
  const coordinatesForTimezone = place
    ? { latitude: place.latitude, longitude: place.longitude }
    : manualCoordinates;
  const timezoneNeedsResolution = Boolean(coordinatesForTimezone && (!place || !place.timezone));

  useEffect(() => {
    document.title = "Rufous · Public Arizona bird watch";
    let current = true;
    const controller = new AbortController();
    void getPublicManifest(controller.signal).then(async (loadedManifest) => {
      const loadedAttribution = await getPublicAttribution(loadedManifest.attribution_path, controller.signal);
      if (!current) return;
      setManifest(loadedManifest);
      setAttribution(loadedAttribution);
      setSpeciesCode(loadedManifest.species[0]?.species_code ?? "");
    }).catch((reason: unknown) => {
      if (current && !controller.signal.aborted) setLoadError(reason instanceof Error ? reason.message : "Public Rufous data is unavailable.");
    });
    return () => { current = false; controller.abort(); };
  }, []);

  useEffect(() => {
    if (!manifest || !speciesCode) { setProfile(null); return; }
    const species = manifest.species.find((item) => item.species_code === speciesCode);
    if (!species) { setProfile(null); return; }
    const controller = new AbortController();
    void getPublicSpecies(species, controller.signal).then(setProfile).catch(() => setProfile(null));
    return () => controller.abort();
  }, [manifest, speciesCode]);

  useEffect(() => {
    if (!manifest || place || query.trim().length < 2 || /^\s*[+-]?\d/.test(query)) {
      setPlaceOptions([]);
      setPlaceStatus("");
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setPlaceStatus("Searching static Arizona place data…");
      void searchPublicPlaces(query, manifest, controller.signal).then((places) => {
        setPlaceOptions(places);
        setPlaceStatus(places.length ? "" : "No matching place in this public release. You can enter Arizona coordinates.");
      }).catch(() => setPlaceStatus("Place search is temporarily unavailable. You can enter Arizona coordinates."));
    }, 180);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [manifest, place, query]);

  useEffect(() => {
    setManualTimezone("");
  }, [coordinatesForTimezone?.latitude, coordinatesForTimezone?.longitude, place?.public_id, place?.timezone]);

  const evaluate = useCallback(async (watch: PublicWatch, makeActive = false) => {
    if (!manifest) return;
    setEvaluations((current) => ({ ...current, [watch.id]: { status: "loading" } }));
    if (makeActive) {
      setActiveWatchId(watch.id);
      setGuidance("");
    }
    try {
      const value = await evaluatePublicWatch(watch, manifest);
      setEvaluations((current) => ({ ...current, [watch.id]: { status: "ready", value } }));
      if (makeActive) {
        setGuidance(deterministicGuidance(value));
      }
    } catch (reason) {
      setEvaluations((current) => ({ ...current, [watch.id]: { status: "error", message: reason instanceof Error ? reason.message : "Watch evaluation failed." } }));
    }
  }, [manifest]);

  useEffect(() => {
    if (!manifest || autoEvaluationVersion.current === manifest.data_version) return;
    autoEvaluationVersion.current = manifest.data_version;
    for (const watch of watches) void evaluate(watch);
  }, [evaluate, manifest, watches]);

  const activeEvaluation = activeWatchId && evaluations[activeWatchId]?.status === "ready"
    ? (evaluations[activeWatchId] as Extract<EvaluationState, { status: "ready" }>).value
    : null;
  const activeMatch = activeEvaluation?.matches[0] ?? null;
  const eventWindow = activeEvaluation ? sunriseWindow(activeEvaluation.watch) : null;
  const attributionById = useMemo(
    () => new Map((attribution?.items ?? []).map((item) => [item.attribution_id, item])),
    [attribution],
  );

  function submitWatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!manifest) return;
    const species = manifest.species.find((item) => item.species_code === speciesCode);
    const coordinates = manualCoordinates;
    if (!species) { setFormError("Choose a bird."); return; }
    if (!place && !coordinates) { setFormError("Choose an Arizona place or enter valid Arizona latitude,longitude coordinates."); return; }
    if (timezoneNeedsResolution && !manualTimezone) {
      setFormError("Choose Arizona time or Mountain time for this location."); return;
    }
    if (outingDate < minimumOutingDate()) { setFormError("Choose tomorrow or a later outing date so the calendar recommendation is future-facing."); return; }
    const watch: PublicWatch = {
      id: createWatchId(),
      species_code: species.species_code,
      bird_name: birdName(species),
      center_name: place?.name ?? "Manual Arizona watch area",
      center_latitude: place?.latitude ?? coordinates!.latitude,
      center_longitude: place?.longitude ?? coordinates!.longitude,
      center_timezone: (
        place?.timezone === "America/Denver" ? "America/Denver"
          : place?.timezone === "America/Phoenix" ? "America/Phoenix"
            : manualTimezone
      ) as PublicWatch["center_timezone"],
      radius_miles: radius,
      outing_date: outingDate,
      created_at: new Date().toISOString(),
    };
    const next = [watch, ...watches].slice(0, 25);
    setWatches(next);
    writePublicWatches(next);
    setFormError(null);
    void evaluate(watch, true);
  }

  function deleteWatch(id: string) {
    const next = watches.filter((watch) => watch.id !== id);
    setWatches(next);
    writePublicWatches(next);
    setEvaluations((current) => {
      const { [id]: _removed, ...rest } = current;
      return rest;
    });
    if (activeWatchId === id) setActiveWatchId(null);
  }

  function downloadCalendar() {
    if (!activeEvaluation || !activeMatch) return;
    const calendar = buildPublishedCalendar(activeEvaluation.watch, activeMatch, guidance || deterministicGuidance(activeEvaluation));
    downloadPublishedCalendar(`rufous-${activeEvaluation.watch.species_code}-${activeEvaluation.watch.outing_date}.ics`, calendar);
  }

  if (loadError) return <main className="public-main public-load-state"><div className="error" role="alert"><strong>Rufous could not load its static public data.</strong><span>{loadError}</span></div></main>;
  if (!manifest) return <main className="public-main public-load-state"><p role="status">Loading the public Rufous field console…</p></main>;

  return <>
    <header className="site-header public-header">
      <a className="site-brand public-brand-link" href="#top" aria-label="Rufous public field console home">
        <img className="brand-mark" src={rufousImage} alt="" aria-hidden="true" />
        <span><strong>Rufous</strong><small>Public Arizona bird watch</small></span>
      </a>
      <nav aria-label="Public navigation">
        <a href="#watch">Build a watch</a>
        <a href="#saved">Saved watches</a>
        <a href="#credits">Credits</a>
      </nav>
    </header>
    <main id="top" className="public-main">
      <section className="hero-card public-hero">
        <p className="eyebrow">Interactive portfolio demonstration</p>
        <h1>Watch for an Arizona bird. Leave with a sunrise-timed plan.</h1>
        <p>Everything essential runs in your browser from a sanitized static snapshot. Watches stay on this device, and Rufous never asks for your email.</p>
        <div className="public-release-status">
          <span>Data: {manifest.release_mode === "synthetic" ? "clearly labeled synthetic preview" : "licensed GBIF eBird EOD snapshot"}</span>
          <span>Generated: {new Date(manifest.generated_at).toLocaleString()}</span>
          <span>{manifest.counts.species.toLocaleString()} birds · {manifest.counts.observations.toLocaleString()} licensed occurrences · {manifest.counts.places.toLocaleString()} places</span>
        </div>
      </section>

      <section id="watch" className="public-builder" aria-labelledby="watch-heading">
        <div className="panel public-watch-form-panel">
          <p className="eyebrow">Local watch builder</p>
          <h2 id="watch-heading">Try a watch now</h2>
          <form onSubmit={submitWatch}>
            <label htmlFor="public-bird">Bird</label>
            <select id="public-bird" value={speciesCode} onChange={(event) => setSpeciesCode(event.target.value)} required>
              {manifest.species.map((species) => <option key={species.species_code} value={species.species_code}>{birdName(species)}</option>)}
            </select>
            <label htmlFor="public-place">Arizona place or coordinates</label>
            <div className="location-combobox">
              <input
                id="public-place"
                value={query}
                onChange={(event) => { setQuery(event.target.value); setPlace(null); }}
                autoComplete="off"
                placeholder="Prescott or 34.54,-112.47"
                aria-describedby="public-place-help public-place-status"
                required
              />
              {placeOptions.length > 0 && <ul className="location-options public-place-options">
                {placeOptions.map((option) => <li key={option.public_id}>
                  <button type="button" onClick={() => { setPlace(option); setQuery(option.name); setPlaceOptions([]); }}>
                    <strong>{option.name}</strong><small>{option.kind} · {option.source.replaceAll("_", " ")}</small>
                  </button>
                </li>)}
              </ul>}
              <small id="public-place-help">Static USGS GNIS place names are available. Coordinates must fall inside Arizona.</small>
              <small id="public-place-status" className="location-status" aria-live="polite">{place ? `${place.kind} selected.` : placeStatus}</small>
            </div>
            {timezoneNeedsResolution && <>
              <label htmlFor="manual-timezone">Time convention for these coordinates</label>
              <select id="manual-timezone" value={manualTimezone} onChange={(event) => setManualTimezone(event.target.value as typeof manualTimezone)} required>
                <option value="">Choose one</option>
                <option value="America/Phoenix">Arizona time (no daylight saving)</option>
                <option value="America/Denver">Mountain time (daylight saving)</option>
              </select>
              <small>The static site cannot look up a time zone, so Rufous needs this choice for sunrise and calendar times.</small>
            </>}
            <label htmlFor="public-radius">Watch radius (miles)</label>
            <input id="public-radius" type="number" min="1" max="300" step="1" value={radius} onChange={(event) => setRadius(Number(event.target.value))} required />
            <label htmlFor="public-date">Outing date</label>
            <input id="public-date" type="date" min={minimumOutingDate()} value={outingDate} onChange={(event) => setOutingDate(event.target.value)} required />
            <button type="submit">Evaluate and save on this device</button>
          </form>
          {formError && <div className="error" role="alert"><span>{formError}</span></div>}
          <p className="source-status">No account, server-side watch, email address, or notification is created.</p>
        </div>
        {profile ? <SpeciesProfile profile={profile} /> : <section className="panel"><p role="status">Loading bird profile…</p></section>}
      </section>

      <section className="panel public-result" aria-labelledby="result-heading">
        <p className="eyebrow">Current evaluation</p>
        <h2 id="result-heading">Watch result</h2>
        {!activeWatchId && <p className="empty">Build a watch or re-evaluate a saved watch to see current static evidence.</p>}
        {activeWatchId && evaluations[activeWatchId]?.status === "loading" && <p role="status">Loading only the Arizona grid cells that intersect this watch…</p>}
        {activeWatchId && evaluations[activeWatchId]?.status === "error" && <div className="error" role="alert"><span>{(evaluations[activeWatchId] as Extract<EvaluationState, { status: "error" }>).message}</span></div>}
        {activeEvaluation && <div className="public-result-grid">
          <div>
            <p className={activeMatch ? "success public-result-message" : "notice public-result-message"}>{guidance || deterministicGuidance(activeEvaluation)}</p>
            <dl className="details-list bird-facts">
              <div><dt>Matching occurrences</dt><dd>{activeEvaluation.matches.length.toLocaleString()}</dd></div>
              <div><dt>Static cells loaded</dt><dd>{activeEvaluation.loaded_cell_ids.join(", ") || "None"}</dd></div>
              <div><dt>Evaluated</dt><dd>{new Date(activeEvaluation.evaluated_at).toLocaleString()}</dd></div>
            </dl>
            {activeMatch && eventWindow && <>
              <h3>Sunrise-timed outing</h3>
              <p><strong>{formatInTimeZone(eventWindow.start, activeEvaluation.watch.center_timezone)}–{new Intl.DateTimeFormat(undefined, { timeStyle: "short", timeZone: activeEvaluation.watch.center_timezone }).format(eventWindow.end)}</strong></p>
              <p>Centered on calculated sunrise at {formatInTimeZone(eventWindow.sunrise, activeEvaluation.watch.center_timezone)}. Calendar times are published in UTC for reliable import.</p>
              <button type="button" onClick={downloadCalendar}>Download calendar event (.ics)</button>
              <p className="source-status">The calendar uses METHOD:PUBLISH and contains no organizer, attendee, RSVP, or email fields.</p>
            </>}
          </div>
          <div>
            <MatchMap evaluation={activeEvaluation} manifest={manifest} />
            {activeMatch && <ol className="public-match-list">{activeEvaluation.matches.slice(0, 8).map((match) => {
              const credit = attributionById.get(match.attribution_id);
              const sourceUrl = credit ? safeExternalUrl(credit.source_url) : null;
              const licenseUrl = credit ? safeExternalUrl(credit.license_url) : null;
              return <li key={match.public_id}>
                <strong>{match.location.name}</strong><span>{match.distance_miles.toFixed(1)} mi · {match.count_display} · {formatOccurrenceDate(match.observed_at)} · {match.source}</span>
                {credit && <small>{credit.creator}{credit.dataset_title ? ` · ${credit.dataset_title}` : ""}{credit.publisher ? ` · ${credit.publisher}` : ""} · {sourceUrl ? <a href={sourceUrl} target="_blank" rel="noreferrer">source record</a> : "source record"} · {licenseUrl ? <a href={licenseUrl} target="_blank" rel="noreferrer">{credit.license}</a> : credit.license}</small>}
              </li>;
            })}</ol>}
          </div>
        </div>}
      </section>

      <section id="saved" className="panel public-saved" aria-labelledby="saved-heading">
        <p className="eyebrow">Browser storage only</p>
        <h2 id="saved-heading">Saved watches</h2>
        {watches.length === 0 ? <p className="empty">No watches are stored on this device.</p> : <ul>
          {watches.map((watch) => {
            const evaluation = evaluations[watch.id];
            const matchCount = evaluation?.status === "ready" ? evaluation.value.matches.length : null;
            return <li key={watch.id}>
              <div><strong>{watch.bird_name}</strong><span>{watch.center_name} · {watch.radius_miles} mi · {watch.outing_date}</span>
                <small>{evaluation?.status === "loading" ? "Re-evaluating…" : evaluation?.status === "error" ? evaluation.message : matchCount === null ? "Not evaluated" : `${matchCount} current static match${matchCount === 1 ? "" : "es"}`}</small></div>
              <div className="button-row"><button type="button" className="secondary" onClick={() => void evaluate(watch, true)}>Re-evaluate</button><button type="button" className="danger" onClick={() => deleteWatch(watch.id)}>Remove</button></div>
            </li>;
          })}
        </ul>}
        <p className="source-status">Removing browser data, using private browsing, or changing devices removes these watches. Rufous cannot notify you while you are away.</p>
      </section>

      <section id="credits" className="panel public-credits" aria-labelledby="credits-heading">
        <p className="eyebrow">Provenance</p>
        <h2 id="credits-heading">Data and media credits</h2>
        {attribution ? <ul>{attribution.sources.map((source) => <li key={`${source.provider}-${source.title}`}>
          <strong>{source.title}</strong><span>{source.credit}</span>{source.modifications && <span>Changes made by Rufous: {source.modifications}</span>}{source.disclaimer && <span>Source notice: {source.disclaimer}</span>}<span>{source.license_url ? <a href={source.license_url} target="_blank" rel="noreferrer">{source.license}</a> : source.license}</span><a href={source.url} target="_blank" rel="noreferrer">Source</a>
        </li>)}</ul> : <p>Attribution unavailable.</p>}
        {attribution && attribution.items.length > 0 && <>
          <h3>Item-level media and occurrence credits</h3>
          <ul>{attribution.items.map((item) => {
            const sourceUrl = safeExternalUrl(item.source_url);
            const licenseUrl = safeExternalUrl(item.license_url);
            const doiUrl = safeDoiUrl(item.dataset_doi);
            return <li key={item.attribution_id}>
              <strong>{item.creator}{item.dataset_title ? ` · ${item.dataset_title}` : ""}</strong>
              {item.publisher && <span>Publisher: {item.publisher}</span>}
              {item.dataset_citation && <span>Recommended citation: {item.dataset_citation}</span>}
              {doiUrl && <a href={doiUrl} target="_blank" rel="noreferrer">Dataset DOI: {item.dataset_doi}</a>}
              <span>{item.provider.replaceAll("_", " ")} · {licenseUrl ? <a href={licenseUrl} target="_blank" rel="noreferrer">{item.license}</a> : item.license}</span>
              {sourceUrl && <a href={sourceUrl} target="_blank" rel="noreferrer">{item.dataset_title ? "Dataset source" : "Source record"}</a>}
            </li>;
          })}</ul>
        </>}
        <p className="source-status">Release {manifest.data_version} · Schema {manifest.schema_version} · Direct eBird API data and hotspots are excluded.</p>
      </section>
    </main>
  </>;
}
