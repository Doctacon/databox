import { MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GeoJSONSource, Map as MapLibreMap, Marker, StyleSpecification } from "maplibre-gl";
import type { FeatureCollection, GeoJsonProperties, Point, Polygon } from "geojson";
import boundariesRaw from "./assets/arizona-boundaries.geojson?raw";
import { loadMapLibre, type MapLibreRuntime } from "./maplibreRuntime";
import { getMapSnapshot } from "./mapApi";
import rufousImage from "./assets/rufous.png";
import type { CatalogPhoto, MapEncounter, MapSnapshot, TripPlanDetail } from "./types";
import { compareVisibleLabels } from "./visibleLabel";
import "maplibre-gl/dist/maplibre-gl.css";

type Navigate = (path: string) => void;
type Recency = "all" | "48h" | "7d" | "30d";

const boundaries = JSON.parse(boundariesRaw) as FeatureCollection;
const ARIZONA_BOUNDS: [[number, number], [number, number]] = [[-114.82, 31.3], [-109, 37.1]];
const KM_PER_DEGREE = 111.32;
const DISTANCE_TOLERANCE_KM = 0.01;
const RADIUS_EPSILON_KM = 1e-9;
const windows: Record<Exclude<Recency, "all">, number> = {
  "48h": 48 * 60 * 60 * 1000,
  "7d": 7 * 24 * 60 * 60 * 1000,
  "30d": 30 * 24 * 60 * 60 * 1000,
};

function useMapLibreRuntime(enabled: boolean): {
  runtime: MapLibreRuntime | null;
  failed: boolean;
} {
  const [runtime, setRuntime] = useState<MapLibreRuntime | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!enabled || runtime) return;
    let current = true;
    void loadMapLibre()
      .then((value) => { if (current) setRuntime(value); })
      .catch(() => { if (current) setFailed(true); });
    return () => { current = false; };
  }, [enabled, runtime]);
  return { runtime, failed };
}

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
    preview: { type: "geojson" as const, data: { type: "FeatureCollection", features: [] } as FeatureCollection },
  },
  layers: [
    { id: "background", type: "background" as const, paint: { "background-color": "#f3ead7" } },
    { id: "state-fill", type: "fill" as const, source: "boundaries", filter: ["==", ["get", "kind"], "state"], paint: { "fill-color": "#d8e6dd", "fill-opacity": 0.65 } },
    { id: "county-lines", type: "line" as const, source: "boundaries", filter: ["==", ["get", "kind"], "county"], paint: { "line-color": "#376a67", "line-width": 1.2, "line-opacity": 0.8 } },
    { id: "clusters", type: "circle" as const, source: "encounters", filter: ["has", "point_count"], paint: { "circle-color": "#8f3524", "circle-radius": ["step", ["get", "point_count"], 18, 25, 23, 100, 29], "circle-stroke-color": "#201d19", "circle-stroke-width": 2 } },
    { id: "encounter-points", type: "circle" as const, source: "encounters", filter: ["!", ["has", "point_count"]], paint: { "circle-color": "#f0b429", "circle-radius": 7, "circle-stroke-color": "#201d19", "circle-stroke-width": 2 } },
    { id: "preview-encounter", type: "circle" as const, source: "preview", paint: { "circle-color": "#fff4c2", "circle-radius": 11, "circle-stroke-color": "#8f3524", "circle-stroke-width": 4 } },
    { id: "selected-encounter", type: "circle" as const, source: "encounters", filter: ["==", ["get", "source_observation_id"], ""], paint: { "circle-color": "#fff4c2", "circle-radius": 12, "circle-stroke-color": "#075660", "circle-stroke-width": 4 } },
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

function EncounterThumbnail({ photo, name }: { photo: CatalogPhoto | undefined; name: string }) {
  const [failed, setFailed] = useState(false);
  const metadataAvailable = photo?.status === "available" && Boolean(photo.display_url);
  const provider = "iNaturalist";
  const attribution = metadataAvailable ? `Photo: ${photo.creator || photo.rights_holder} · ${photo.license_text} · ${provider}` : null;
  return <span className="encounter-thumbnail">
    {metadataAvailable && !failed ? <img src={photo.display_url!} alt={name} loading="lazy" onError={() => setFailed(true)} />
      : <img src={rufousImage} alt="" aria-hidden="true" loading="lazy" />}
    <small role={failed ? "status" : undefined}>{failed && attribution ? `Photo unavailable · ${attribution}` : attribution || "Photo unavailable"}</small>
  </span>;
}

function EncounterPhotoLinks({ photo }: { photo: CatalogPhoto | undefined }) {
  if (photo?.status !== "available" || !photo.source_url || !photo.license_url || !photo.license_code) return null;
  const provider = "iNaturalist";
  return <small className="encounter-photo-links">
    <a href={photo.source_url} target="_blank" rel="noreferrer">{provider} photo source</a>
    {" · "}<a href={photo.license_url} target="_blank" rel="noreferrer">{photo.license_code} license</a>
  </small>;
}

function encounterBounds(rows: MapEncounter[]): [[number, number], [number, number]] {
  const longitudes = rows.map((row) => row.longitude);
  const latitudes = rows.map((row) => row.latitude);
  return [
    [Math.min(...longitudes), Math.min(...latitudes)],
    [Math.max(...longitudes), Math.max(...latitudes)],
  ];
}

type TripEvidencePoint = {
  key: string;
  source: "ebird" | "gbif";
  sourceLabel: "eBird report" | "GBIF occurrence";
  name: string;
  location: string;
  latitude: number;
  longitude: number;
  distanceKm: number;
};

type TripMapData = {
  radiusKm: number;
  rows: TripEvidencePoint[];
  radius: FeatureCollection<Polygon, GeoJsonProperties>;
  origin: FeatureCollection<Point, GeoJsonProperties>;
  evidence: FeatureCollection<Point, GeoJsonProperties>;
  bounds: [[number, number], [number, number]];
};

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function visibleText(value: unknown): string | null {
  return typeof value === "string" && value.trim() && value.length <= 300 ? value.trim() : null;
}

function plannerDistanceKm(
  centerLatitude: number,
  centerLongitude: number,
  latitude: number,
  longitude: number,
): number {
  const latitudeDelta = latitude - centerLatitude;
  const longitudeDelta = (longitude - centerLongitude) * Math.cos(centerLatitude * Math.PI / 180);
  return KM_PER_DEGREE * Math.sqrt(latitudeDelta ** 2 + longitudeDelta ** 2);
}

function enforcedRadius(detail: TripPlanDetail): number | null {
  const toolNames = ["lookup_recent_observation_evidence", "lookup_gbif_occurrence_evidence"];
  const radii = toolNames.map((toolName) => {
    const trace = detail.tool_traces.find((row) => row.tool_name === toolName && row.tool_status === "ok");
    return finiteNumber(trace?.output_summary.enforced_radius_km);
  });
  if (radii.some((value) => value === null || value <= 0 || value > 500)) return null;
  const [first, second] = radii as [number, number];
  return Math.abs(first - second) <= Number.EPSILON * Math.max(first, second, 1) ? first : null;
}

function radiusGeometry(
  latitude: number,
  longitude: number,
  radiusKm: number,
): Pick<TripMapData, "radius" | "bounds"> {
  const latitudeDelta = radiusKm / KM_PER_DEGREE;
  const longitudeScale = Math.cos(latitude * Math.PI / 180);
  const longitudeDelta = radiusKm / (KM_PER_DEGREE * longitudeScale);
  const ring: [number, number][] = Array.from({ length: 65 }, (_, index) => {
    const angle = index / 64 * Math.PI * 2;
    return [
      longitude + longitudeDelta * Math.cos(angle),
      latitude + latitudeDelta * Math.sin(angle),
    ];
  });
  return {
    radius: {
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [ring] },
        properties: {},
      }],
    },
    bounds: [
      [longitude - longitudeDelta, latitude - latitudeDelta],
      [longitude + longitudeDelta, latitude + latitudeDelta],
    ],
  };
}

function tripMapData(detail: TripPlanDetail): TripMapData | null {
  const latitude = finiteNumber(detail.plan.latitude);
  const longitude = finiteNumber(detail.plan.longitude);
  const radiusKm = enforcedRadius(detail);
  if (latitude === null || longitude === null || radiusKm === null
    || detail.plan.region_code !== "US-AZ" || latitude < 31.3 || latitude > 37.1
    || longitude < -114.9 || longitude > -109) return null;

  const recommendations = new Map(detail.recommendations.map((row) => [row.recommendation_id, row]));
  const seen = new Set<string>();
  const rows: TripEvidencePoint[] = [];
  for (const row of detail.evidence) {
    const isEbird = row.source === "ebird" && row.evidence_type === "recent_observation";
    const isGbif = row.source === "gbif" && row.evidence_type === "occurrence_context";
    const sourceRecordId = visibleText(row.source_record_id);
    if (row.status !== "available" || (!isEbird && !isGbif) || sourceRecordId === null) continue;
    const evidenceLatitude = finiteNumber(row.payload.latitude);
    const evidenceLongitude = finiteNumber(row.payload.longitude);
    const persistedDistance = finiteNumber(row.summary.distance_km)
      ?? finiteNumber(row.payload.distance_km);
    if (evidenceLatitude === null || evidenceLongitude === null || persistedDistance === null
      || evidenceLatitude < 31.3 || evidenceLatitude > 37.1
      || evidenceLongitude < -114.9 || evidenceLongitude > -109) continue;
    const calculatedDistance = plannerDistanceKm(
      latitude,
      longitude,
      evidenceLatitude,
      evidenceLongitude,
    );
    if (persistedDistance < 0 || persistedDistance > radiusKm + RADIUS_EPSILON_KM
      || calculatedDistance > radiusKm + RADIUS_EPSILON_KM
      || Math.abs(calculatedDistance - persistedDistance) > DISTANCE_TOLERANCE_KM) continue;
    const recommendation = row.recommendation_id === null
      ? undefined
      : recommendations.get(row.recommendation_id);
    const name = visibleText(row.summary.common_name)
      ?? visibleText(row.summary.scientific_name)
      ?? visibleText(recommendation?.common_name)
      ?? visibleText(recommendation?.scientific_name);
    if (name === null) continue;
    const key = `${row.source}|${sourceRecordId}|${name.toLocaleLowerCase()}`;
    if (seen.has(key)) continue;
    const source = isEbird ? "ebird" : "gbif";
    rows.push({
      key,
      source,
      sourceLabel: isEbird ? "eBird report" : "GBIF occurrence",
      name,
      location: visibleText(isEbird ? row.summary.location_name : row.summary.locality)
        ?? "Locality not supplied",
      latitude: evidenceLatitude,
      longitude: evidenceLongitude,
      distanceKm: calculatedDistance,
    });
    seen.add(key);
  }
  rows.sort((left, right) => left.distanceKm - right.distanceKm
    || left.name.localeCompare(right.name) || left.key.localeCompare(right.key));
  const geometry = radiusGeometry(latitude, longitude, radiusKm);
  return {
    radiusKm,
    rows,
    ...geometry,
    origin: {
      type: "FeatureCollection",
      features: [{
        type: "Feature",
        geometry: { type: "Point", coordinates: [longitude, latitude] },
        properties: {},
      }],
    },
    evidence: {
      type: "FeatureCollection",
      features: rows.map((row) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [row.longitude, row.latitude] },
        properties: { source: row.source },
      })),
    },
  };
}

function tripStyle(data: TripMapData): StyleSpecification {
  return {
    version: 8,
    sources: {
      boundaries: { type: "geojson", data: boundaries },
      "trip-radius": { type: "geojson", data: data.radius },
      "trip-evidence": { type: "geojson", data: data.evidence },
      "trip-origin": { type: "geojson", data: data.origin },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#f3ead7" } },
      { id: "state-fill", type: "fill", source: "boundaries", filter: ["==", ["get", "kind"], "state"], paint: { "fill-color": "#d8e6dd", "fill-opacity": 0.65 } },
      { id: "county-lines", type: "line", source: "boundaries", filter: ["==", ["get", "kind"], "county"], paint: { "line-color": "#376a67", "line-width": 1.2, "line-opacity": 0.8 } },
      { id: "trip-radius-fill", type: "fill", source: "trip-radius", paint: { "fill-color": "#24758a", "fill-opacity": 0.14 } },
      { id: "trip-radius-line", type: "line", source: "trip-radius", paint: { "line-color": "#0d4d55", "line-width": 2, "line-dasharray": [3, 2] } },
      { id: "trip-evidence-points", type: "circle", source: "trip-evidence", paint: { "circle-color": ["match", ["get", "source"], "gbif", "#24758a", "#f0b429"], "circle-radius": 7, "circle-stroke-color": "#201d19", "circle-stroke-width": 2 } },
      { id: "trip-origin-point", type: "circle", source: "trip-origin", paint: { "circle-color": "#8f3524", "circle-radius": 9, "circle-stroke-color": "#fff8df", "circle-stroke-width": 3 } },
    ],
  };
}

function evidenceCountLabel(count: number, singular: string, plural: string): string {
  return `${count.toLocaleString()} ${count === 1 ? singular : plural}`;
}

export function TripEvidenceMap({ detail }: { detail: TripPlanDetail }) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const hasVerifiedRadius = useMemo(() => enforcedRadius(detail) !== null, [detail]);
  const data = useMemo(() => tripMapData(detail), [detail]);
  const mapRuntime = useMapLibreRuntime(Boolean(data));
  const topRecentReports = useMemo(() => detail.recommendations
    .filter((row) => row.recommendation_group === "recently_reported")
    .sort((left, right) => left.rank_order - right.rank_order)
    .map((row) => row.common_name || row.scientific_name || row.species_code)
    .filter((name): name is string => Boolean(name))
    .slice(0, 3), [detail]);

  useEffect(() => {
    const runtime = mapRuntime.runtime;
    if (!data || !runtime || !mapContainer.current || mapRef.current) return;
    const map = new runtime.Map({
      container: mapContainer.current,
      style: tripStyle(data),
      bounds: data.bounds,
      fitBoundsOptions: { padding: 28, duration: 0 },
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
    });
    mapRef.current = map;
    map.addControl(new runtime.NavigationControl({ showCompass: false }), "top-right");
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [data, mapRuntime.runtime]);

  const radiusLabel = data?.radiusKm.toLocaleString(undefined, { maximumFractionDigits: 1 });
  const ebirdCount = data?.rows.filter((row) => row.source === "ebird").length ?? 0;
  const gbifCount = data?.rows.filter((row) => row.source === "gbif").length ?? 0;
  return <section className="panel trip-evidence-map" aria-labelledby="trip-evidence-map-heading">
    <h2 id="trip-evidence-map-heading">Evidence Map</h2>
    {!data ? <p className="empty">{hasVerifiedRadius
      ? "This saved plan does not contain a valid Arizona trip location, so its evidence cannot be plotted."
      : "This saved plan does not contain matching successful eBird and GBIF enforced-radius traces, so its evidence cannot be plotted as in-radius."}</p> : <>
      <div className="trip-map-summary">
        <strong>{evidenceCountLabel(data.rows.length, "distinct persisted evidence record", "distinct persisted evidence records")} within the enforced {radiusLabel} km radius</strong>
        <ul className="trip-map-legend" aria-label="Mapped evidence sources">
          <li><span className="trip-map-swatch ebird" aria-hidden="true" />{evidenceCountLabel(ebirdCount, "eBird report", "eBird reports")}</li>
          <li><span className="trip-map-swatch gbif" aria-hidden="true" />{evidenceCountLabel(gbifCount, "GBIF occurrence", "GBIF occurrences")}</li>
          <li><span className="trip-map-swatch origin" aria-hidden="true" />Trip location</li>
        </ul>
        {topRecentReports.length > 0 && <p className="trip-map-recommendations">
          <strong>Evidence-ranked recommendations:</strong> {topRecentReports.join(" · ")}
          <small>Distinct recent eBird submissions; not encounter probability.</small>
        </p>}
      </div>
      <div ref={mapContainer} className="map-canvas" role="region" aria-label={`Map of ${data.rows.length.toLocaleString()} distinct persisted evidence records inside the enforced ${radiusLabel} kilometer radius`} />
      {mapRuntime.failed && <p className="caveat" role="alert">The interactive map could not start. The evidence summary and mapped-location list remain available.</p>}
      <details className="trip-map-locations">
        <summary>Mapped evidence locations</summary>
        {data.rows.length ? <ol>{data.rows.map((row) => <li key={row.key}>
          <strong>{row.name}</strong><span>{row.sourceLabel} · {row.location} · {row.distanceKm.toFixed(1)} km from trip location</span>
        </li>)}</ol> : <p className="empty">No qualifying coordinate-bearing evidence was persisted for this plan.</p>}
      </details>
      <p className="source-status">Points are eligible reports and occurrence records used by this plan, not predicted current presence. The radius uses the planner's displayed local-distance approximation.</p>
    </>}
  </section>;
}

export function FieldMapPage({ navigate }: { navigate: Navigate }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<Marker[]>([]);
  const encounterRef = useRef<Map<string, MapEncounter>>(new Map());
  const filteredRef = useRef<MapEncounter[]>([]);
  const fitArizonaRef = useRef(true);
  const selectedIdRef = useRef<string | null>(null);
  const previousRecencyRef = useRef<Recency>("all");
  const sourceReadyRef = useRef(false);
  const sourceGenerationRef = useRef(0);
  const markerReadyGenerationRef = useRef(-1);
  const [snapshot, setSnapshot] = useState<MapSnapshot | null>(null);
  const mapRuntime = useMapLibreRuntime(Boolean(snapshot));
  const [error, setError] = useState<string | null>(null);
  const [species, setSpecies] = useState("all");
  const [selectedFamily, setSelectedFamily] = useState("all");
  const [recency, setRecency] = useState<Recency>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoverPreviewId, setHoverPreviewId] = useState<string | null>(null);
  const [focusPreviewId, setFocusPreviewId] = useState<string | null>(null);
  const previewId = focusPreviewId ?? hoverPreviewId;

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
  const photoBySpecies = useMemo(() => new Map(snapshot?.photos.map((row) => [row.species_code, row.photo]) ?? []), [snapshot]);

  useEffect(() => {
    filteredRef.current = filtered;
    selectedIdRef.current = selectedId;
    const resetToAll = previousRecencyRef.current !== "all" && recency === "all";
    fitArizonaRef.current = resetToAll
      || (species === "all" && selectedFamily === "all" && recency === "all");
    previousRecencyRef.current = recency;
    encounterRef.current = new Map(filtered.map((row) => [row.source_observation_id, row]));
    if (selectedId && !encounterRef.current.has(selectedId)) setSelectedId(null);
    if (hoverPreviewId && !encounterRef.current.has(hoverPreviewId)) setHoverPreviewId(null);
    if (focusPreviewId && !encounterRef.current.has(focusPreviewId)) setFocusPreviewId(null);
  }, [filtered, focusPreviewId, hoverPreviewId, recency, selectedFamily, selectedId, species]);

  const applyFilteredToMap = useCallback((map: MapLibreMap) => {
    const source = map.getSource("encounters") as GeoJSONSource | undefined;
    if (!source) return;
    const rows = filteredRef.current;
    sourceGenerationRef.current += 1;
    markerReadyGenerationRef.current = -1;
    for (const marker of markerRef.current) marker.remove();
    markerRef.current = [];
    source.setData(points(rows));
    const duration = reducedMotion() ? 0 : 350;
    if (fitArizonaRef.current || rows.length === 0) {
      map.fitBounds(ARIZONA_BOUNDS, { padding: 20, duration });
    } else {
      map.fitBounds(encounterBounds(rows), { padding: 50, maxZoom: 10, duration });
    }
  }, []);

  useEffect(() => {
    const source = mapRef.current?.getSource("preview") as GeoJSONSource | undefined;
    const row = previewId ? encounterRef.current.get(previewId) : undefined;
    source?.setData(row ? points([row]) : points([]));
  }, [previewId]);

  const choose = useCallback((row: MapEncounter) => {
    setSelectedId(row.source_observation_id);
    const map = mapRef.current;
    map?.easeTo({
      center: [row.longitude, row.latitude],
      zoom: Math.max(map.getZoom(), 11),
      duration: reducedMotion() ? 0 : 350,
    });
  }, []);

  useEffect(() => {
    const runtime = mapRuntime.runtime;
    if (!snapshot || !runtime || !mapContainer.current || mapRef.current) return;
    const map = new runtime.Map({
      container: mapContainer.current,
      style: localStyle,
      bounds: ARIZONA_BOUNDS,
      fitBoundsOptions: { padding: 20, duration: 0 },
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new runtime.NavigationControl({ showCompass: false }), "top-right");

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
        button.setAttribute("aria-label", `Zoom to cluster containing ${count.toLocaleString()} eligible encounter${count === 1 ? "" : "s"}`);
        button.addEventListener("click", () => expandCluster(feature));
        markerRef.current.push(new runtime.Marker({ element: button })
          .setLngLat(feature.geometry.coordinates as [number, number]).addTo(map));
      }
    };
    map.on("load", () => {
      sourceReadyRef.current = true;
      applyFilteredToMap(map);
      map.setFilter("selected-encounter", [
        "==", ["get", "source_observation_id"], selectedIdRef.current ?? "",
      ]);
    });
    map.on("sourcedata", (event) => {
      if (event.sourceId !== "encounters" || !event.isSourceLoaded) return;
      markerReadyGenerationRef.current = sourceGenerationRef.current;
      refreshClusterMarkers();
    });
    map.on("moveend", () => {
      if (sourceReadyRef.current
        && markerReadyGenerationRef.current === sourceGenerationRef.current) {
        refreshClusterMarkers();
      }
    });
    map.on("click", "clusters", (event) => { const feature = event.features?.[0]; if (feature) expandCluster(feature); });
    map.on("click", "encounter-points", (event) => {
      const id = event.features?.[0]?.properties?.source_observation_id;
      const row = typeof id === "string" ? encounterRef.current.get(id) : undefined;
      if (row) choose(row);
    });
    return () => {
      for (const marker of markerRef.current) marker.remove();
      markerRef.current = [];
      sourceReadyRef.current = false;
      markerReadyGenerationRef.current = -1;
      map.remove();
      mapRef.current = null;
    };
  }, [applyFilteredToMap, choose, mapRuntime.runtime, snapshot]);

  useEffect(() => {
    const map = mapRef.current;
    if (map && sourceReadyRef.current) applyFilteredToMap(map);
  }, [applyFilteredToMap, filtered]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !sourceReadyRef.current) return;
    map.setFilter("selected-encounter", [
      "==", ["get", "source_observation_id"], selectedId ?? "",
    ]);
  }, [selectedId]);
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
        <section className="panel map-panel" aria-labelledby="map-canvas-heading"><h2 id="map-canvas-heading">Arizona encounter map</h2><div ref={mapContainer} className="map-canvas" aria-label="Interactive map of eligible Arizona encounters" />{mapRuntime.failed && <p className="caveat" role="alert">The interactive map could not start. Filters and the accessible encounter list remain available.</p>}</section>
        <aside className="field-map-rail" aria-label="Selected encounter and accessible encounter list">
          <section className="panel selected-encounter" aria-labelledby="selected-encounter-heading" aria-live="polite"><h2 id="selected-encounter-heading">Selected encounter</h2>{selected ? <><h3>{label(selected)}</h3><p>{selected.location_name}</p><p>{dateTime(selected.observation_at)} · {selected.observation_count.toLocaleString()} observed{selected.notable ? " · notable" : ""}</p>{selected.access_warning && <p className="caveat">Access may be restricted. Verify access before visiting.</p>}<a href={`/birds/${selected.species_code}`} onClick={(event) => profileLink(event, `/birds/${selected.species_code}`)}>View bird profile</a></> : <p>Select a map point or encounter-list row for details.</p>}</section>
          <section className="panel encounter-list-panel" aria-labelledby="encounter-list-heading"><h2 id="encounter-list-heading">Accessible encounter list</h2>{filtered.length ? <ol className="encounter-list">{filtered.map((row) => <li key={row.source_observation_id}><button type="button" aria-pressed={selectedId === row.source_observation_id} onMouseEnter={() => setHoverPreviewId(row.source_observation_id)} onMouseLeave={() => setHoverPreviewId(null)} onFocus={() => setFocusPreviewId(row.source_observation_id)} onBlur={() => setFocusPreviewId(null)} onClick={() => choose(row)}><EncounterThumbnail photo={photoBySpecies.get(row.species_code)} name={label(row)} /><span className="encounter-copy"><strong>{label(row)}</strong><span>{row.location_name} · {dateTime(row.observation_at)} · {row.observation_count.toLocaleString()} observed{row.notable ? " · notable" : ""}</span>{row.access_warning && <span className="caveat">Access may be restricted despite the public source label.</span>}</span></button><EncounterPhotoLinks photo={photoBySpecies.get(row.species_code)} /></li>)}</ol> : <p className="empty">No encounters to list.</p>}</section>
        </aside>
      </div>
      <p className="source-status map-attribution">Boundary geometry derived and generalized from January 1, 2025 U.S. Census Bureau TIGERweb data. This product uses Census Bureau data but is not endorsed or certified by the Census Bureau.</p>
    </>}
  </main>;
}
