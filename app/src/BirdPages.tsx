import { FormEvent, MouseEvent, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getBird, listBirds } from "./birdApi";
import { ProfileCollectionControls } from "./MyBirds";
import type { BirdCatalogSummary, BirdProfile, CatalogCall, CatalogPhoto } from "./types";

const BIRDS_PER_PAGE = 24;

type Navigate = (path: string) => void;

type CategoryFilter = "all" | "species" | "hybrid";

function link(event: MouseEvent<HTMLAnchorElement>, path: string, navigate: Navigate) {
  if (!event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
    event.preventDefault();
    navigate(path);
  }
}

function categoryLabel(category: string | null): string {
  if (!category) return "Taxonomic category unavailable";
  return category === "hybrid" ? "Hybrid" : category === "species" ? "Species" : category;
}

function formatDate(value: string | null): string {
  if (!value) return "Not available";
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) {
    return new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3])).toLocaleDateString();
  }
  return new Date(value).toLocaleDateString();
}

function fact(value: string | number | null, suffix = ""): string {
  return value === null ? "Not available" : `${typeof value === "number" ? value.toLocaleString() : value}${suffix}`;
}

function PageHeading({ children, id }: { children: ReactNode; id?: string }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => headingRef.current?.focus(), []);
  return <h1 ref={headingRef} id={id} tabIndex={-1}>{children}</h1>;
}

function DefinitionList({ rows, className = "" }: { rows: [string, string][]; className?: string }) {
  return <dl className={`details-list bird-facts ${className}`.trim()}>
    {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
  </dl>;
}

let stopActiveCatalogAudio: (() => void) | null = null;
const catalogAudioStops = new Set<() => void>();

function stopCatalogAudio() {
  stopActiveCatalogAudio?.();
  stopActiveCatalogAudio = null;
}

function stopAllCatalogAudio() {
  for (const stop of catalogAudioStops) stop();
  stopActiveCatalogAudio = null;
}

function RufousSilhouette({ label }: { label: string }) {
  return <div className="catalog-media-placeholder" role="img" aria-label={`No licensed photo available for ${label}`}>
    <svg viewBox="0 0 160 120" aria-hidden="true" focusable="false">
      <path d="M36 76c9-23 31-36 55-30 13 3 23 12 30 24l20 7-18 9c-5 17-22 28-43 27-24-2-43-16-44-37Z" />
      <circle cx="105" cy="61" r="3" />
      <path d="M59 62c12 5 22 15 27 30M54 105l-9 10m39-7 4 10" />
    </svg>
    <span>Photo unavailable</span>
  </div>;
}

function CatalogPhotoMedia({ photo, label, compact = false }: {
  photo: CatalogPhoto; label: string; compact?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [photo.display_url]);
  const available = photo.status === "available" && photo.display_url !== null;
  const attribution = photo.creator || photo.rights_holder;
  return <figure className={`catalog-photo ${compact ? "catalog-photo-compact" : "catalog-photo-profile"}`}>
    <div className="catalog-photo-frame">
      {available && !failed
        ? <img src={photo.display_url!} alt={label} loading="lazy" onError={() => setFailed(true)} />
        : <RufousSilhouette label={label} />}
    </div>
    <figcaption className="catalog-media-attribution">
      {failed && <span className="caveat" role="status">Photo could not be loaded.</span>}
      {available ? <>
        <span>Photo: {attribution}</span>
        {!compact && photo.publisher && <span>Publisher: {photo.publisher}</span>}
        {photo.source_url && <a href={photo.source_url} target="_blank" rel="noreferrer">GBIF source</a>}
        {photo.license_url && <a href={photo.license_url} target="_blank" rel="noreferrer">{photo.license_text}</a>}
        {!compact && photo.selection_reason && <span>{photo.selection_reason}</span>}
        {!compact && <span>Looked up: {formatDate(photo.lookup_at)}</span>}
      </> : <span>No validated catalog photo is available.</span>}
    </figcaption>
  </figure>;
}

function CatalogCallPlayer({ call, label, compact = false }: {
  call: CatalogCall; label: string; compact?: boolean;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const playingAudioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [failed, setFailed] = useState(false);
  const stop = useCallback(() => {
    const audio = playingAudioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
      playingAudioRef.current = null;
    }
    setPlaying(false);
  }, []);
  useEffect(() => {
    catalogAudioStops.add(stop);
    return () => {
      catalogAudioStops.delete(stop);
      stop();
      if (stopActiveCatalogAudio === stop) stopActiveCatalogAudio = null;
    };
  }, [stop]);
  const available = call.status === "available" && call.audio_url !== null;

  function toggle() {
    if (playing) {
      stopCatalogAudio();
      return;
    }
    stopCatalogAudio();
    setFailed(false);
    stopActiveCatalogAudio = stop;
    const audio = audioRef.current;
    if (!audio) return;
    playingAudioRef.current = audio;
    setPlaying(true);
    void Promise.resolve(audio.play()).catch(() => {
      if (stopActiveCatalogAudio === stop) stopActiveCatalogAudio = null;
      stop();
      setFailed(true);
    });
  }

  if (!available) return <div className="catalog-call catalog-call-unavailable"><span>No validated call is available.</span></div>;
  return <div className={`catalog-call ${compact ? "catalog-call-compact" : "catalog-call-profile"}`}>
    <audio ref={audioRef} src={call.audio_url!} preload="none" onEnded={() => {
      if (stopActiveCatalogAudio === stop) stopActiveCatalogAudio = null;
      playingAudioRef.current = null;
      setPlaying(false);
    }} onError={() => {
      if (stopActiveCatalogAudio === stop) stopActiveCatalogAudio = null;
      stop(); setFailed(true);
    }} />
    <button type="button" className="catalog-call-button" aria-pressed={playing} onClick={toggle}>
      {playing ? `Stop call for ${label}` : `Play call for ${label}`}
    </button>
    {failed && <span className="caveat" role="status">Call playback failed.</span>}
    <div className="catalog-media-attribution">
      <span>Call: {call.recordist}{call.geographic_scope ? ` · ${call.geographic_scope}` : ""}</span>
      {!compact && call.recording_type && <span>Type: {call.recording_type}{call.quality ? ` · quality ${call.quality}` : ""}</span>}
      {!compact && (call.locality || call.country) && <span>Location: {[call.locality, call.country].filter(Boolean).join(", ")}</span>}
      {call.source_url && <a href={call.source_url} target="_blank" rel="noreferrer">Xeno-canto source</a>}
      {call.license_url && <a href={call.license_url} target="_blank" rel="noreferrer">{call.license_text}</a>}
      {!compact && call.selection_reason && <span>{call.selection_reason}</span>}
      {!compact && <span>Looked up: {formatDate(call.lookup_at)}</span>}
    </div>
  </div>;
}

export function BirdCatalogPage({ navigate }: { navigate: Navigate }) {
  const [birds, setBirds] = useState<BirdCatalogSummary[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<CategoryFilter>("all");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    void listBirds().then((rows) => {
      if (current) setBirds(rows);
    }).catch((reason: unknown) => {
      if (current) setError(reason instanceof Error ? reason.message : "The local bird catalog is unavailable");
    }).finally(() => {
      if (current) setLoading(false);
    });
    return () => { current = false; };
  }, []);

  useEffect(() => setPage(0), [query, category]);
  useEffect(() => stopAllCatalogAudio(), [query, category, page]);
  useEffect(() => () => stopAllCatalogAudio(), []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return birds.filter((bird) => {
      const categoryMatches = category === "all" || bird.taxonomic_category === category;
      const textMatches = !needle || [bird.common_name, bird.scientific_name, bird.species_code]
        .some((value) => value?.toLocaleLowerCase().includes(needle));
      return categoryMatches && textMatches;
    });
  }, [birds, category, query]);
  const lastPage = Math.max(0, Math.ceil(filtered.length / BIRDS_PER_PAGE) - 1);
  const currentPage = Math.min(page, lastPage);
  const start = currentPage * BIRDS_PER_PAGE;
  const visible = filtered.slice(start, start + BIRDS_PER_PAGE);

  function reset(event: FormEvent) {
    event.preventDefault();
    setQuery("");
    setCategory("all");
  }

  return <main className="birds-main">
    <section className="catalog-heading" aria-labelledby="birds-heading">
      <p className="eyebrow">Read-only modeled catalog</p>
      <PageHeading id="birds-heading">Arizona Birds</PageHeading>
      <p>Current Arizona regional taxa from eBird, with exact modeled AVONET and public evidence where available.</p>
    </section>
    <section className="panel catalog-panel" aria-busy={loading}>
      <form className="catalog-controls" onSubmit={reset}>
        <div><label htmlFor="bird-search">Search birds</label><input id="bird-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Common name, scientific name, or species code" /></div>
        <div><label htmlFor="bird-category">Category</label><select id="bird-category" value={category} onChange={(event) => setCategory(event.target.value as CategoryFilter)}><option value="all">All taxa</option><option value="species">Species</option><option value="hybrid">Hybrids</option></select></div>
        <button type="submit">Reset catalog</button>
      </form>
      {error && <div className="error" role="alert"><strong>Could not load Arizona birds.</strong><span>{error}</span></div>}
      {loading && <p role="status">Loading the local Arizona catalog…</p>}
      {!loading && !error && <>
        <p className="catalog-count" aria-live="polite">Showing {filtered.length === 0 ? "0" : `${start + 1}–${start + visible.length}`} of {filtered.length} matching taxa · {birds.length} total</p>
        {visible.length === 0 ? <p className="empty">No Arizona taxa match this search and category.</p> : <ol className="bird-catalog-grid" start={start + 1}>
          {visible.map((bird) => {
            const label = bird.common_name || bird.scientific_name || bird.species_code;
            const mediaLabel = bird.common_name && bird.scientific_name
              ? `${bird.common_name} (${bird.scientific_name})` : label;
            return <li key={bird.species_code}>
              <article className="bird-catalog-card">
                <CatalogPhotoMedia photo={bird.photo} label={mediaLabel} compact />
                <div className="bird-card-identity"><span className="badge">{categoryLabel(bird.taxonomic_category)}</span><span className="bird-code">{bird.species_code}</span></div>
                <h2><a href={`/birds/${bird.species_code}`} onClick={(event) => link(event, `/birds/${bird.species_code}`, navigate)}>{label}</a></h2>
                {bird.common_name && bird.scientific_name && <p className="scientific">{bird.scientific_name}</p>}
                <p>{bird.family_common_name || bird.family_scientific_name || "Family unavailable"}</p>
                <CatalogCallPlayer call={bird.call} label={label} compact />
                <ul className="card-status"><li>AVONET traits: {bird.traits_status}</li><li>Recent public observations: {bird.recent_public_observation_count.toLocaleString()}</li></ul>
              </article>
            </li>;
          })}
        </ol>}
        {filtered.length > BIRDS_PER_PAGE && <nav className="pagination" aria-label="Arizona bird catalog pagination"><span>Page {currentPage + 1} of {lastPage + 1}</span><div><button type="button" disabled={currentPage === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>Previous</button><button type="button" disabled={currentPage === lastPage} onClick={() => setPage((value) => Math.min(lastPage, value + 1))}>Next</button></div></nav>}
      </>}
    </section>
  </main>;
}

const morphologyLabels: [keyof BirdProfile["traits"]["morphology"], string, string][] = [
  ["beak_length_culmen_mm", "Beak length (culmen)", " mm"],
  ["beak_length_nares_mm", "Beak length (nares)", " mm"],
  ["beak_width_mm", "Beak width", " mm"], ["beak_depth_mm", "Beak depth", " mm"],
  ["tarsus_length_mm", "Tarsus length", " mm"], ["wing_length_mm", "Wing length", " mm"],
  ["kipps_distance_mm", "Kipp's distance", " mm"], ["secondary_length_mm", "Secondary length", " mm"],
  ["hand_wing_index", "Hand-wing index", ""], ["tail_length_mm", "Tail length", " mm"],
  ["mass_g", "Body mass", " g"],
];

function BirdProfileView({ bird, navigate }: { bird: BirdProfile; navigate: Navigate }) {
  const morphology = morphologyLabels
    .filter(([key]) => bird.traits.morphology[key] !== null)
    .map(([key, label, unit]) => [label, fact(bird.traits.morphology[key], unit)] as [string, string]);
  const traitsAvailable = bird.traits.status === "available";
  const doiLink = bird.traits.provenance.dataset_doi === "10.6084/m9.figshare.16586228.v7";
  const avonetLicense = bird.traits.provenance.dataset_license === "CC BY 4.0";

  return <main className="bird-profile-main">
    <p><a href="/birds" onClick={(event) => link(event, "/birds", navigate)}>← Back to Arizona Birds</a></p>
    <header className="hero-card bird-profile-hero">
      <p className="eyebrow">{categoryLabel(bird.taxonomic_category)} · {bird.species_code}</p>
      <PageHeading>{bird.common_name || bird.scientific_name || bird.species_code}</PageHeading>
      {bird.common_name && bird.scientific_name && <p className="scientific">{bird.scientific_name}</p>}
    </header>

    <section className="panel catalog-profile-media" aria-labelledby="catalog-media-heading">
      <h2 id="catalog-media-heading">Photo and call</h2>
      <div className="catalog-profile-media-grid">
        <CatalogPhotoMedia photo={bird.photo} label={bird.common_name && bird.scientific_name ? `${bird.common_name} (${bird.scientific_name})` : bird.common_name || bird.scientific_name || bird.species_code} />
        <CatalogCallPlayer call={bird.call} label={bird.common_name || bird.scientific_name || bird.species_code} />
      </div>
    </section>

    <section className="panel target-profile-action"><h2>Plan for this bird</h2><p>Search current modeled public observations within a per-request Arizona travel radius.</p><a className="button-link" href={`/birds/${bird.species_code}/find`} onClick={(event) => link(event, `/birds/${bird.species_code}/find`, navigate)}>Find this bird</a></section>

    <ProfileCollectionControls key={bird.species_code} bird={bird} />

    <section className="panel"><h2>Identity and taxonomy</h2><DefinitionList rows={[
      ["Common name", fact(bird.common_name)], ["Scientific name", fact(bird.scientific_name)],
      ["eBird species code", bird.species_code], ["Category", categoryLabel(bird.taxonomic_category)],
      ["Order", fact(bird.order_name)], ["Family", fact(bird.family_common_name || bird.family_scientific_name)],
      ["Family scientific name", fact(bird.family_scientific_name)], ["Report as", fact(bird.taxonomy.report_as)],
    ]} />{bird.taxonomy.extinct && <p className="caveat">eBird taxonomy marks this taxon extinct{bird.taxonomy.extinct_year ? ` (${bird.taxonomy.extinct_year})` : ""}.</p>}</section>

    <section className="panel"><h2>Physical traits</h2>{traitsAvailable ? <>
      {morphology.length ? <DefinitionList rows={morphology} /> : <p className="empty">AVONET has an exact taxon match but no modeled measurements are available.</p>}
      <h3>Measurement sample</h3><DefinitionList rows={[
        ["Individuals", fact(bird.traits.sample.total_individuals)], ["Complete measurements", fact(bird.traits.sample.complete_measures)],
        ["Female", fact(bird.traits.sample.female_individuals)], ["Male", fact(bird.traits.sample.male_individuals)],
        ["Unknown sex", fact(bird.traits.sample.unknown_sex_individuals)], ["Mass source", fact(bird.traits.mass_source)],
        ["Mass reference detail", fact(bird.traits.mass_reference_other)],
      ]} />
      {bird.traits.inference === true
        ? <p className="caveat">AVONET marks modeled traits as inferred{bird.traits.traits_inferred ? `: ${bird.traits.traits_inferred}` : ""}{bird.traits.reference_species ? `. Reference species: ${bird.traits.reference_species}.` : "."}</p>
        : bird.traits.inference === false
          ? <p>AVONET does not mark these modeled traits as inferred.</p>
          : <p className="empty">AVONET inference status is unavailable.</p>}
    </> : <p className="empty">AVONET v7 has no exact scientific-name match for this current eBird taxon. Taxonomy and current Arizona evidence remain available.</p>}</section>

    <section className="panel"><h2>Ecology</h2>{traitsAvailable ? <DefinitionList rows={[
      ["Habitat", fact(bird.traits.ecology.habitat)],
      ["Habitat density", bird.traits.ecology.habitat_density_label ? `${bird.traits.ecology.habitat_density_label} (code ${fact(bird.traits.ecology.habitat_density_code)})` : fact(bird.traits.ecology.habitat_density_code)],
      ["Migration", bird.traits.ecology.migration_label ? `${bird.traits.ecology.migration_label} (code ${fact(bird.traits.ecology.migration_code)})` : fact(bird.traits.ecology.migration_code)],
      ["Trophic level", fact(bird.traits.ecology.trophic_level)], ["Trophic niche", fact(bird.traits.ecology.trophic_niche)],
      ["Primary lifestyle", fact(bird.traits.ecology.primary_lifestyle)],
    ]} /> : <p className="empty">No exact AVONET ecology match is available.</p>}<p className="source-status">AVONET ecology describes global species traits; it is not Arizona-specific. Global range metrics are not available in the governed model.</p></section>

    <section className="panel"><h2>Arizona activity</h2><DefinitionList rows={[
      ["Recent public observations", bird.arizona_activity.recent_public_observation_count.toLocaleString()],
      ["Latest public observation", formatDate(bird.arizona_activity.latest_public_observation_at)],
      ["Public locations", bird.arizona_activity.public_location_count.toLocaleString()],
      ["Recent notable observations", bird.arizona_activity.recent_public_notable_count.toLocaleString()],
    ]} />{bird.arizona_activity.top_public_locations.length ? <><h3>Top public locations</h3><ol className="location-list">{bird.arizona_activity.top_public_locations.map((location) => {
      const accessMayBeRestricted = /\(private\)/i.test(location.location_name || "");
      return <li key={location.location_id}><strong>{location.location_name || "Unnamed public location"}</strong><span>{location.observation_count.toLocaleString()} observations · latest {formatDate(location.latest_observation_at)}{location.notable_count ? ` · ${location.notable_count.toLocaleString()} notable` : ""}</span><span>{location.latitude.toFixed(4)}, {location.longitude.toFixed(4)}</span>{accessMayBeRestricted && <span className="caveat">This modeled observation location is public, but site access may be restricted. Verify access before visiting.</span>}</li>;
    })}</ol></> : <p className="empty">No recent valid, reviewed, non-private Arizona locations are available.</p>}</section>

    <section className="panel"><h2>Occurrence and sound context</h2><p className="source-status">These are modeled global source aggregates and are not Arizona occurrence or seasonality claims.</p><DefinitionList rows={[
      ["GBIF occurrences", bird.gbif.occurrence_count.toLocaleString()], ["Latest GBIF event date", formatDate(bird.gbif.latest_event_date)],
      ["Xeno-canto recordings", bird.xeno_canto.recording_count.toLocaleString()], ["Latest Xeno-canto recording", formatDate(bird.xeno_canto.latest_recording_date)],
      ["Representative recording ID", fact(bird.xeno_canto.representative_recording_id)], ["Recordist", fact(bird.xeno_canto.representative_recordist)],
      ["Recording type", fact(bird.xeno_canto.representative_recording_type)], ["Quality", fact(bird.xeno_canto.representative_recording_quality)],
      ["Recording license", fact(bird.xeno_canto.representative_recording_license)],
    ]} />{bird.gbif.occurrence_count === 0 && <p className="empty">No modeled GBIF occurrences are available.</p>}{bird.xeno_canto.recording_count === 0 && <p className="empty">No modeled Xeno-canto recordings are available.</p>}</section>

    <section className="panel"><h2>Evidence and provenance</h2><DefinitionList rows={[
      ["eBird status", bird.freshness.species_list_loaded_at && bird.freshness.taxonomy_loaded_at ? (bird.freshness.ebird_observations_loaded_at ? "Catalog and public observation snapshot loaded" : "Catalog loaded; no modeled public observation evidence") : "Catalog load status unavailable"],
      ["AVONET status", traitsAvailable ? "Exact trait match available" : "No exact trait match"],
      ["GBIF status", bird.gbif.occurrence_count > 0 ? "Modeled occurrence evidence available" : "No modeled occurrence evidence"],
      ["Xeno-canto status", bird.xeno_canto.recording_count > 0 ? "Modeled recording evidence available" : "No modeled recording evidence"],
      ["eBird regional list loaded", formatDate(bird.freshness.species_list_loaded_at)], ["eBird taxonomy loaded", formatDate(bird.freshness.taxonomy_loaded_at)],
      ["eBird observations loaded", formatDate(bird.freshness.ebird_observations_loaded_at)], ["GBIF loaded", formatDate(bird.freshness.gbif_loaded_at)],
      ["Xeno-canto loaded", formatDate(bird.freshness.xeno_canto_loaded_at)], ["Catalog freshness", formatDate(bird.freshness.catalog_freshness_at)],
      ["AVONET source name", fact(bird.traits.source_scientific_name)], ["AVONET / Avibase ID", fact(bird.traits.avibase_id)],
      ["AVONET family", fact(bird.traits.avonet_family)], ["AVONET order", fact(bird.traits.avonet_order_name)],
      ["AVONET version", fact(bird.traits.provenance.dataset_version)], ["AVONET source file", fact(bird.traits.provenance.source_file_id)],
      ["AVONET source file MD5", fact(bird.traits.provenance.source_file_md5)], ["AVONET loaded", formatDate(bird.traits.provenance.loaded_at)],
    ]} />
      <p>{doiLink ? <a href="https://doi.org/10.6084/m9.figshare.16586228.v7" target="_blank" rel="noreferrer">AVONET dataset DOI: {bird.traits.provenance.dataset_doi}</a> : <>AVONET dataset DOI: {fact(bird.traits.provenance.dataset_doi)}</>}</p>
      <p>AVONET license: {avonetLicense ? <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0</a> : fact(bird.traits.provenance.dataset_license)}</p>
      <p className="source-status">Only persisted modeled facts are shown. Missing source evidence remains unavailable rather than inferred. Arizona activity excludes private, invalid, and unreviewed observations.</p>
    </section>
  </main>;
}

export function BirdProfilePage({ speciesCode, navigate }: { speciesCode: string; navigate: Navigate }) {
  const [bird, setBird] = useState<BirdProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    setLoading(true); setError(null); setBird(null);
    void getBird(speciesCode).then((row) => { if (current) setBird(row); }).catch((reason: unknown) => {
      if (current) setError(reason instanceof Error ? reason.message : "The bird profile is unavailable");
    }).finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [speciesCode]);
  useEffect(() => {
    if (bird) document.title = `${bird.common_name || bird.scientific_name || bird.species_code} · Arizona Birds · Databox`;
    else if (error) document.title = "Bird Profile Unavailable · Arizona Birds · Databox";
  }, [bird, error]);
  if (loading) return <main className="bird-profile-main"><p role="status">Loading the modeled bird profile…</p></main>;
  if (error) return <main className="bird-profile-main"><PageHeading>Bird profile unavailable</PageHeading><div className="error" role="alert"><strong>Could not load this bird.</strong><span>{error}</span></div><p><a href="/birds" onClick={(event) => link(event, "/birds", navigate)}>Back to Arizona Birds</a></p></main>;
  return bird ? <BirdProfileView bird={bird} navigate={navigate} /> : null;
}
