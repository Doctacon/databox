import { MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";
import type { FeatureCollection, GeoJsonProperties, Point } from "geojson";
import boundariesRaw from "./assets/arizona-boundaries.geojson?raw";
import { getMapSnapshot } from "./mapApi";
import type { MapEncounter, MapSnapshot } from "./types";
import { compareVisibleLabels } from "./visibleLabel";
import "maplibre-gl/dist/maplibre-gl.css";

type Navigate = (path: string) => void;
type Recency = "all" | "48h" | "7d" | "30d";

const boundaries = JSON.parse(boundariesRaw) as FeatureCollection;
const ARIZONA_BOUNDS: [[number, number], [number, number]] = [[-114.82, 31.3], [-109, 37.1]];
const windows: Record<Exclude<Recency, "all">, number> = {
  "48h": 48 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
  "30d": 30 * 24 * 60 * 60 * 1000,
};

const localStyle: StyleSpecification = {
  version: 8 as const,
  sources: {
    boundaries: { type: "geojson" as const, data: boundaries },
    encounters: {
      type: "geojson" as const,
      data: { type: "FeatureCollection", features: [] } as FeatureCollection,
      cluster: true,
      clusterMaxZoom: 10,
      clusterRadius: 45,
    },
  },
  layers: [
    { id: "background", type: "background" as const, paint: { "background-color": "#f3ead7" } },
    { id: "state-fill", type: "fill" as const, source: "boundaries", filter: ["==", ["get", "kind"], "state"], paint: { "fill-color": "#d8e6dd", "fill-opacity": 0.65 } },
    { id: "county-lines", type: "line" as const, source: "boundaries", filter: ["==", ["get", "kind"], "county"], paint: { "line-color": "#376a67", "line-width": 1.2, "line-opacity": 0.8 } },
    { id: "clusters", type: "circle" as const, source: "encounters", filter: ["has", "point_count"], paint: { "circle-color": "#8f3524", "circle-radius": ["step", ["get", "point_count"], 18, 25, 23, 100, 29], "circle-stroke-color": "#201d19", "circle-stroke-width": 2 } },
    { id: "encounter-points", type: "circle" as const, source: "encounters", filter: ["!", ["has", "point_count"]], paint: { "circle-color": "#f0b429", "circle-radius": 7, "circle-stroke-color": "#201d19", "circle-stroke-width": 2 } },
  ],
};

function label(row: MapEncounter): string {
  return row.common_name || row.scientific_name || row.species_code;
}

function family(row: MapEncounter): string {
  return row.family_common_name || row.family_scientific_name || "Family unavailable";
}

function points(rows: MapEncounter[]): FeatureCollection<Point, GeoJsonProperties> {
  return {
    type: "FeatureCollection",
    features: rows.map((row) => ({
      type: "Feature",
      id: row.source_observation_id,
      geometry: { type: "Point", coordinates: [row.longitude, row.latitude] },
      properties: { source_observation_id: row.source_observation_id },
    })),
  };
}

function dateTime(value: string | null): string {
  if (!value) return "Unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString();
}

function reducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

export function FieldMapPage({ navigate }: { navigate: Navigate }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<Marker[]>([]);
  const encounterRef = useRef<Map<string, MapEncounter>>(new Map());
  const [snapshot, setSnapshot] = useState<MapSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [species, setSpecies] = useState("all");
  const [selectedFamily, setSelectedFamily] = useState("all");
  const [recency, setRecency] = useState<Recency>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => { headingRef.current?.focus(); }, []);
  useEffect(() => {
    let current = true;
    void getMapSnapshot().then((value) => { if (current) setSnapshot(value); })
      .catch((reason: unknown) => { if (current) setError(reason instanceof Error ? reason.message : "The local Field Map is unavailable"); });
    return () => { current = false; };
  }, []);

  const speciesOptions = useMemo(() => {
    if (!snapshot) return [];
    const unique = new Map<string, string>();
    for (const row of snapshot.encounters) unique.set(row.species_code, label(row));
    return [...unique].map(([value, optionLabel]) => ({ value, label: optionLabel }))
      .sort((left, right) => compareVisibleLabels(left.label, right.label, left.value, right.value));
  }, [snapshot]);
  const familyOptions = useMemo(() => {
    if (!snapshot) return [];
    const values = new Set(snapshot.encounters.map(family));
    return [...values].sort(compareVisibleLabels);
  }, [snapshot]);
  const filtered = useMemo(() => {
    if (!snapshot) return [];
    const cutoff = recency === "all" ? null : Date.now() - windows[recency];
    return snapshot.encounters.filter((row) => species === "all" || row.species_code === species)
      .filter((row) => selectedFamily === "all" || family(row) === selectedFamily)
      .filter((row) => cutoff === null || new Date(row.observation_at).getTime() >= cutoff);
  }, [recency, selectedFamily, snapshot, species]);
  const selected = selectedId ? filtered.find((row) => row.source_observation_id === selectedId) ?? null : null;

  useEffect(() => {
    encounterRef.current = new Map(filtered.map((row) => [row.source_observation_id, row]));
    if (selectedId && !encounterRef.current.has(selectedId)) setSelectedId(null);
  }, [filtered, selectedId]);

  useEffect(() => {
    if (!snapshot || !mapContainer.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: localStyle,
      bounds: ARIZONA_BOUNDS,
      fitBoundsOptions: { padding: 20, duration: 0 },
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const expandCluster = (feature: { properties: GeoJsonProperties; geometry: { type: string; coordinates?: unknown } }) => {
      const clusterId = feature.properties?.cluster_id;
      const coordinates = feature.geometry.type === "Point" ? feature.geometry.coordinates : null;
      const source = map.getSource("encounters") as GeoJSONSource | undefined;
      if (typeof clusterId !== "number" || !Array.isArray(coordinates) || !source) return;
      void source.getClusterExpansionZoom(clusterId).then((zoom) => map.easeTo({
        center: coordinates as [number, number], zoom, duration: reducedMotion() ? 0 : 350,
      }));
    };
    const refreshClusterMarkers = () => {
      for (const marker of markerRef.current) marker.remove();
      markerRef.current = [];
      const seen = new Set<number>();
      for (const feature of map.querySourceFeatures("encounters")) {
        const clusterId = feature.properties?.cluster_id;
        const count = feature.properties?.point_count;
        if (typeof clusterId !== "number" || typeof count !== "number" || seen.has(clusterId)
          || feature.geometry.type !== "Point") continue;
        seen.add(clusterId);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "map-cluster-count";
        button.textContent = count.toLocaleString();
        button.setAttribute("aria-label", `Zoom to cluster containing ${count.toLocaleString()} eligible encounters`);
        button.addEventListener("click", () => expandCluster(feature));
        markerRef.current.push(new maplibregl.Marker({ element: button })
          .setLngLat(feature.geometry.coordinates as [number, number]).addTo(map));
      }
    };
    map.on("data", refreshClusterMarkers);
    map.on("moveend", refreshClusterMarkers);
    map.on("click", "clusters", (event) => { const feature = event.features?.[0]; if (feature) expandCluster(feature); });
    map.on("click", "encounter-points", (event) => {
      const id = event.features?.[0]?.properties?.source_observation_id;
      if (typeof id === "string" && encounterRef.current.has(id)) setSelectedId(id);
    });
    return () => {
      for (const marker of markerRef.current) marker.remove();
      markerRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, [snapshot]);

  useEffect(() => {
    const source = mapRef.current?.getSource("encounters") as GeoJSONSource | undefined;
    source?.setData(points(filtered));
  }, [filtered]);

  function choose(row: MapEncounter) {
    setSelectedId(row.source_observation_id);
    mapRef.current?.easeTo({ center: [row.longitude, row.latitude], zoom: Math.max(mapRef.current.getZoom(), 9), duration: reducedMotion() ? 0 : 350 });
  }
  function profileLink(event: MouseEvent<HTMLAnchorElement>, path: string) {
    if (!event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault(); navigate(path);
    }
  }

  return <main className="field-map-main">
    <header className="catalog-heading"><p className="eyebrow">Persisted public evidence</p><h1 ref={headingRef} tabIndex={-1}>Field Map</h1><p>Explore exact eligible Arizona encounters. This is evidence, not a species range or current-presence claim.</p></header>
    {error && <div className="error" role="alert"><strong>Could not load Field Map.</strong><span>{error}</span></div>}
    {!snapshot && !error && <p role="status">Loading the local Field Map snapshot…</p>}
    {snapshot && <>
      <section className="panel map-controls" aria-labelledby="map-filter-heading">
        <h2 id="map-filter-heading">Filter encounters</h2>
        <div><label htmlFor="map-species">Species</label><select id="map-species" value={species} onChange={(event) => setSpecies(event.target.value)}><option value="all">All species</option>{speciesOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
        <div><label htmlFor="map-family">Family</label><select id="map-family" value={selectedFamily} onChange={(event) => setSelectedFamily(event.target.value)}><option value="all">All families</option>{familyOptions.map((option) => <option key={option} value={option}>{option}</option>)}</select></div>
        <div><label htmlFor="map-recency">Recency</label><select id="map-recency" value={recency} onChange={(event) => setRecency(event.target.value as Recency)}><option value="all">All snapshot</option><option value="48h">Last 48 hours</option><option value="7d">Last 7 days</option><option value="30d">Last 30 days</option></select></div>
        <p className="map-freshness">Latest encounter: {dateTime(snapshot.snapshot_latest_observation_at)} · Source freshness: {dateTime(snapshot.source_freshness_at)}</p>
      </section>
      <p className="map-result-count" aria-live="polite">{filtered.length.toLocaleString()} eligible encounter{filtered.length === 1 ? "" : "s"}</p>
      {filtered.length === 0 && <p className="empty">{recency === "all" ? "No persisted encounters match these species and family filters." : "No persisted encounters fall inside this current-clock window. The local snapshot may be stale; choose All snapshot to inspect available evidence."}</p>}
      <div className="field-map-layout">
        <section className="panel map-panel" aria-labelledby="map-canvas-heading"><h2 id="map-canvas-heading">Arizona encounter map</h2><div ref={mapContainer} className="map-canvas" aria-label="Interactive map of eligible Arizona encounters" /></section>
        <section className="panel encounter-list-panel" aria-labelledby="encounter-list-heading"><h2 id="encounter-list-heading">Accessible encounter list</h2>{filtered.length ? <ol className="encounter-list">{filtered.map((row) => <li key={row.source_observation_id}><button type="button" aria-pressed={selectedId === row.source_observation_id} onClick={() => choose(row)}><strong>{label(row)}</strong><span>{row.location_name} · {dateTime(row.observation_at)} · {row.observation_count.toLocaleString()} observed{row.notable ? " · notable" : ""}</span>{row.access_warning && <span className="caveat">Access may be restricted despite the public source label.</span>}</button></li>)}</ol> : <p className="empty">No encounters to list.</p>}</section>
      </div>
      <section className="panel selected-encounter" aria-labelledby="selected-encounter-heading" aria-live="polite"><h2 id="selected-encounter-heading">Selected encounter</h2>{selected ? <><h3>{label(selected)}</h3><p>{selected.location_name}</p><p>{dateTime(selected.observation_at)} · {selected.observation_count.toLocaleString()} observed{selected.notable ? " · notable" : ""}</p>{selected.access_warning && <p className="caveat">Access may be restricted. Verify access before visiting.</p>}<a href={`/birds/${selected.species_code}`} onClick={(event) => profileLink(event, `/birds/${selected.species_code}`)}>View bird profile</a></> : <p>Select a map point or encounter-list row for details.</p>}</section>
      <p className="source-status map-attribution">Boundary geometry derived and generalized from January 1, 2025 U.S. Census Bureau TIGERweb data. This product uses Census Bureau data but is not endorsed or certified by the Census Bureau.</p>
    </>}
  </main>;
}
