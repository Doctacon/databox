import { useSQLQuery } from "@motherduck/react-sql-query";
import * as d3 from "d3";
import { useState, useRef, useEffect, useMemo } from "react";
import {
  ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip as RTooltip,
  CartesianGrid, Treemap, ComposedChart, Line, Area, Bar, Legend,
} from "recharts";
import {
  MapIcon, Bird, CloudRain, BarChart3, AlertCircle, Layers,
  Thermometer, Waves, TrendingUp, Search,
} from "lucide-react";
import azGeoRaw from "./az-geo.json";

// ────────────────────────────────────────────────────────────────────────
// Helpers / Palette
// ────────────────────────────────────────────────────────────────────────
const N = (v: unknown): number => (v != null ? Number(v) : 0);
const S = (v: unknown): string => (v != null ? String(v) : "");

const INK = "#231f20";
const MUTED = "#6a6a6a";
const SOFT = "#f8f8f8";
const BORDER = "#e5e5e5";

const BLUE = "#0777b3";
const ORANGE = "#e18727";
const RED = "#bd4e35";
const GREEN = "#4a8c4a";
const PURPLE = "#7b5ea8";
const TEAL = "#2aa198";
const GOLD = "#c19a3a";

const FAMILY_COLORS = [
  BLUE, ORANGE, RED, GREEN, PURPLE, TEAL, GOLD,
  "#d94a8c", "#5566a8", "#7aa83a", "#a84a4a", "#4aa8a8",
];

function speciesColor(n: number) {
  return n >= 15 ? RED : n >= 10 ? ORANGE : BLUE;
}

const AZ_STATE = azGeoRaw.state as unknown as GeoJSON.Feature<GeoJSON.MultiPolygon>;
const AZ_COUNTIES = azGeoRaw.counties as unknown as GeoJSON.FeatureCollection<GeoJSON.Polygon>;

// ────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────
interface HotspotPt {
  id: string; name: string; county: string;
  lon: number; lat: number;
  species: number; obs: number; notable: number; diversity: number;
  peakSeason: string; topBird: string;
}

interface FamilyStat {
  family: string; species: number; obs: number; color: string;
}

interface HeatCell { family: string; tod: string; n: number }

interface SpeciesWx {
  code: string; name: string; family: string;
  avgHigh: number; avgLow: number; p25: number; p75: number;
  pctRainy: number; obs: number; days: number; season: string;
}

interface DailyRow {
  date: string;
  obs: number; notables: number; species: number;
  tmax: number | null; prcp: number | null;
  discharge: number | null;
}

interface NotablePt {
  id: string; species: string; family: string;
  location: string; locId: string; lat: number; lon: number;
  date: string; count: number;
}

interface MarkerPt { id: string; lat: number; lon: number; label: string }

// ────────────────────────────────────────────────────────────────────────
// Small UI atoms
// ────────────────────────────────────────────────────────────────────────
function Card({ title, icon, children, right }: {
  title?: string; icon?: React.ReactNode; children: React.ReactNode; right?: React.ReactNode;
}) {
  return (
    <div style={{
      background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 8,
      padding: 20, marginBottom: 16,
    }}>
      {title && (
        <div style={{ display: "flex", alignItems: "center", marginBottom: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {icon}
            <h2 style={{ fontSize: 15, fontWeight: 600, color: INK, margin: 0 }}>{title}</h2>
          </div>
          {right && <div style={{ marginLeft: "auto" }}>{right}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

function KpiTile({ label, value, sub, loading }: {
  label: string; value: string | number | null; sub?: string; loading?: boolean;
}) {
  return (
    <div>
      {loading || value == null
        ? <div style={{ height: 36, width: 80, background: "#eee", borderRadius: 4 }} />
        : <p style={{ color: INK, fontSize: 30, fontWeight: 700, lineHeight: 1, margin: 0 }}>
            {typeof value === "number" ? value.toLocaleString() : value}
          </p>
      }
      <p style={{ color: MUTED, fontSize: 12, marginTop: 6, marginBottom: 0 }}>{label}</p>
      {sub && <p style={{ color: MUTED, fontSize: 10, marginTop: 2, marginBottom: 0 }}>{sub}</p>}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Map (upgraded)
// ────────────────────────────────────────────────────────────────────────
type MapLayer = "species" | "obs" | "notable" | "flock";
type Overlay = "weather" | "stream" | null;

interface MapProps {
  points: HotspotPt[];
  weatherStations: MarkerPt[];
  streamSites: MarkerPt[];
  familyFilter: string | null;
  layer: MapLayer;
  overlay: Overlay;
  onHotspotClick: (pt: HotspotPt) => void;
  height?: number;
}

function valueForLayer(pt: HotspotPt, layer: MapLayer): number {
  switch (layer) {
    case "species": return pt.species;
    case "obs": return pt.obs;
    case "notable": return pt.notable;
    case "flock": return pt.diversity * 10;
  }
}

function HotspotMap({ points, weatherStations, streamSites, layer, overlay, onHotspotClick, height = 460 }: MapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  const [tip, setTip] = useState<{ x: number; y: number; pt: HotspotPt } | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(e => setWidth(e[0].contentRect.width));
    ro.observe(containerRef.current);
    setWidth(containerRef.current.clientWidth);
    return () => ro.disconnect();
  }, []);

  const proj = useMemo(() => d3.geoMercator().fitSize([width, height], AZ_STATE), [width, height]);
  const path = useMemo(() => d3.geoPath().projection(proj), [proj]);

  const statePath = path(AZ_STATE) ?? "";
  const countyPaths = AZ_COUNTIES.features.map(f => ({
    id: String(f.properties?.id ?? ""),
    d: path(f) ?? "",
  }));

  const vals = points.map(p => valueForLayer(p, layer));
  const maxVal = Math.max(1, ...vals);
  const radius = d3.scaleSqrt().domain([0, maxVal]).range([2, 14]);
  const colorScale = d3.scaleSequential(d3.interpolateViridis).domain([0, maxVal]);

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100%" }}>
      <svg width={width} height={height} style={{ display: "block" }}>
        {countyPaths.map(c => <path key={c.id} d={c.d} fill="#f0f4f7" stroke="none" />)}
        {countyPaths.map(c => (
          <path key={c.id + "-s"} d={c.d} fill="none" stroke="#c8d4dc" strokeWidth={0.7} />
        ))}
        <path d={statePath} fill="none" stroke="#7aa8c4" strokeWidth={1.6} />

        {/* Overlay markers */}
        {overlay === "weather" && weatherStations.map(m => {
          const p = proj([m.lon, m.lat]); if (!p) return null;
          return <rect key={m.id} x={p[0] - 2} y={p[1] - 2} width={4} height={4} fill={TEAL} fillOpacity={0.6} />;
        })}
        {overlay === "stream" && streamSites.map(m => {
          const p = proj([m.lon, m.lat]); if (!p) return null;
          return <polygon key={m.id} points={`${p[0]},${p[1]-3} ${p[0]+3},${p[1]+2} ${p[0]-3},${p[1]+2}`} fill={PURPLE} fillOpacity={0.7} />;
        })}

        {/* Hotspot dots */}
        {[...points].sort((a, b) => valueForLayer(a, layer) - valueForLayer(b, layer)).map(pt => {
          const p = proj([pt.lon, pt.lat]); if (!p) return null;
          const v = valueForLayer(pt, layer);
          const r = radius(v);
          return (
            <circle
              key={pt.id}
              cx={p[0]} cy={p[1]} r={r}
              fill={colorScale(v)}
              fillOpacity={0.85}
              stroke="#fff"
              strokeWidth={0.6}
              style={{ cursor: "pointer" }}
              onMouseEnter={() => setTip({ x: p[0], y: p[1], pt })}
              onMouseLeave={() => setTip(null)}
              onClick={() => onHotspotClick(pt)}
            />
          );
        })}
      </svg>

      {tip && (
        <div style={{
          position: "absolute", left: tip.x + 12, top: Math.max(0, tip.y - 20),
          background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 4,
          padding: "8px 10px", fontSize: 11, pointerEvents: "none", zIndex: 10,
          boxShadow: "0 2px 8px rgba(0,0,0,0.12)", maxWidth: 220,
        }}>
          <p style={{ fontWeight: 600, color: INK, marginBottom: 4, margin: 0 }}>{tip.pt.name}</p>
          <p style={{ color: MUTED, margin: "2px 0" }}>Species: <strong style={{ color: INK }}>{tip.pt.species}</strong></p>
          <p style={{ color: MUTED, margin: "2px 0" }}>Obs: <strong style={{ color: INK }}>{tip.pt.obs.toLocaleString()}</strong></p>
          <p style={{ color: MUTED, margin: "2px 0" }}>H′: <strong style={{ color: INK }}>{tip.pt.diversity.toFixed(3)}</strong></p>
          <p style={{ color: MUTED, margin: "2px 0", fontStyle: "italic" }}>click for details</p>
        </div>
      )}

      {/* Legend — color ramp */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8, fontSize: 11, color: MUTED }}>
        <span>0</span>
        <div style={{
          flex: 1, height: 8, borderRadius: 4,
          background: `linear-gradient(to right, ${colorScale(0)}, ${colorScale(maxVal * 0.25)}, ${colorScale(maxVal * 0.5)}, ${colorScale(maxVal * 0.75)}, ${colorScale(maxVal)})`,
        }} />
        <span>{Math.round(maxVal)}</span>
        <span style={{ marginLeft: 8 }}>dot size ∝ value</span>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Time-of-day × Family heatmap
// ────────────────────────────────────────────────────────────────────────
function TimeOfDayHeatmap({ cells, families }: { cells: HeatCell[]; families: string[] }) {
  const tods = ["Morning", "Afternoon", "Evening", "Night"];
  const maxN = Math.max(1, ...cells.map(c => c.n));
  const color = d3.scaleSequential(d3.interpolateInferno).domain([0, maxN]);

  const W = 680;
  const H = Math.max(220, families.length * 22 + 40);
  const pad = { t: 30, r: 20, b: 20, l: 180 };
  const cellW = (W - pad.l - pad.r) / tods.length;
  const cellH = (H - pad.t - pad.b) / families.length;

  const lookup = new Map<string, number>();
  cells.forEach(c => lookup.set(`${c.family}||${c.tod}`, c.n));

  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={W} height={H}>
        {tods.map((t, i) => (
          <text key={t}
            x={pad.l + cellW * i + cellW / 2}
            y={pad.t - 10}
            textAnchor="middle"
            style={{ fontSize: 11, fill: MUTED, fontWeight: 600 }}
          >{t}</text>
        ))}
        {families.map((f, fi) => (
          <g key={f}>
            <text x={pad.l - 8} y={pad.t + cellH * fi + cellH / 2 + 4}
              textAnchor="end" style={{ fontSize: 10, fill: INK }}>
              {f.length > 24 ? f.slice(0, 22) + "…" : f}
            </text>
            {tods.map((t, ti) => {
              const v = lookup.get(`${f}||${t}`) ?? 0;
              return (
                <g key={t}>
                  <rect
                    x={pad.l + cellW * ti + 1}
                    y={pad.t + cellH * fi + 1}
                    width={cellW - 2} height={cellH - 2}
                    fill={v > 0 ? color(v) : "#f5f5f5"}
                  />
                  {v > 0 && cellH > 14 && (
                    <text
                      x={pad.l + cellW * ti + cellW / 2}
                      y={pad.t + cellH * fi + cellH / 2 + 3}
                      textAnchor="middle"
                      style={{ fontSize: 9, fill: v > maxN * 0.5 ? "#fff" : INK, fontWeight: 600 }}
                    >{v}</text>
                  )}
                </g>
              );
            })}
          </g>
        ))}
      </svg>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Species × Weather scatter (recharts)
// ────────────────────────────────────────────────────────────────────────
function SpeciesWeatherScatter({ data }: { data: SpeciesWx[] }) {
  const seasons = Array.from(new Set(data.map(d => d.season))).filter(Boolean);
  const seasonColor: Record<string, string> = {
    winter: BLUE, spring: GREEN, summer: ORANGE, fall: RED, "": MUTED,
  };
  const grouped = seasons.map(s => ({
    season: s || "unknown",
    points: data.filter(d => d.season === s).map(d => ({
      x: d.avgHigh, y: d.pctRainy, z: d.obs, name: d.name, family: d.family,
    })),
  }));

  return (
    <ResponsiveContainer width="100%" height={340}>
      <ScatterChart margin={{ top: 10, right: 20, bottom: 40, left: 20 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis type="number" dataKey="x" name="Avg High Temp"
          label={{ value: "Avg high temp (°C)", position: "insideBottom", offset: -10, fill: MUTED, fontSize: 12 }}
          tick={{ fill: MUTED, fontSize: 11 }} stroke="#ccc" />
        <YAxis type="number" dataKey="y" name="% Rainy Days"
          label={{ value: "% rainy days", angle: -90, position: "insideLeft", fill: MUTED, fontSize: 12 }}
          tick={{ fill: MUTED, fontSize: 11 }} stroke="#ccc" />
        <ZAxis type="number" dataKey="z" range={[30, 500]} name="Observations" />
        <RTooltip
          cursor={{ strokeDasharray: "3 3" }}
          content={({ payload }) => {
            if (!payload || !payload.length) return null;
            const d = payload[0].payload;
            return (
              <div style={{ background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 4, padding: 8, fontSize: 11 }}>
                <div style={{ fontWeight: 600, color: INK }}>{d.name}</div>
                <div style={{ color: MUTED }}>{d.family}</div>
                <div style={{ marginTop: 4, color: INK }}>
                  {d.x?.toFixed(1)}°C · {d.y?.toFixed(1)}% rainy · {d.z?.toLocaleString()} obs
                </div>
              </div>
            );
          }}
        />
        <Legend verticalAlign="top" height={28} iconSize={10} wrapperStyle={{ fontSize: 11 }} />
        {grouped.map(g => (
          <Scatter key={g.season} name={g.season} data={g.points} fill={seasonColor[g.season] ?? MUTED} fillOpacity={0.7} />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Temp-range beeswarm (d3 force)
// ────────────────────────────────────────────────────────────────────────
function TempRangeBeeswarm({ data }: { data: SpeciesWx[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(760);
  const height = 320;

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(e => setWidth(e[0].contentRect.width));
    ro.observe(containerRef.current);
    setWidth(containerRef.current.clientWidth);
    return () => ro.disconnect();
  }, []);

  const pad = { t: 20, r: 20, b: 40, l: 30 };
  const xMin = Math.min(...data.map(d => d.p25), 0) - 2;
  const xMax = Math.max(...data.map(d => d.p75), 0) + 2;
  const x = d3.scaleLinear().domain([xMin, xMax]).range([pad.l, width - pad.r]);

  const nodes = useMemo(() => {
    const ns = data.map(d => ({
      ...d, x: x((d.p25 + d.p75) / 2), y: height / 2, r: Math.max(3, Math.sqrt(d.obs) * 0.6),
    }));
    const sim = d3.forceSimulation(ns as d3.SimulationNodeDatum[])
      .force("x", d3.forceX((d: any) => x((d.p25 + d.p75) / 2)).strength(0.9))
      .force("y", d3.forceY(height / 2).strength(0.08))
      .force("collide", d3.forceCollide((d: any) => d.r + 1))
      .stop();
    for (let i = 0; i < 200; i++) sim.tick();
    return ns;
  }, [data, width]);

  const families = Array.from(new Set(data.map(d => d.family))).filter(Boolean).slice(0, FAMILY_COLORS.length);
  const famColor = new Map(families.map((f, i) => [f, FAMILY_COLORS[i]]));

  const ticks = x.ticks(8);

  const [hover, setHover] = useState<{ x: number; y: number; n: any } | null>(null);

  return (
    <div ref={containerRef} style={{ width: "100%", position: "relative" }}>
      <svg width={width} height={height} style={{ display: "block" }}>
        {ticks.map(t => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={pad.t} y2={height - pad.b} stroke="#eee" />
            <text x={x(t)} y={height - pad.b + 14} textAnchor="middle" style={{ fontSize: 10, fill: MUTED }}>{t}</text>
          </g>
        ))}
        <text x={width / 2} y={height - 8} textAnchor="middle" style={{ fontSize: 11, fill: MUTED }}>
          Temperature midpoint (°C) — dot size ∝ observations · color by family
        </text>
        {nodes.map((n: any) => (
          <circle key={n.code} cx={n.x} cy={n.y} r={n.r}
            fill={famColor.get(n.family) ?? MUTED} fillOpacity={0.75}
            stroke="#fff" strokeWidth={0.5}
            style={{ cursor: "pointer" }}
            onMouseEnter={() => setHover({ x: n.x, y: n.y, n })}
            onMouseLeave={() => setHover(null)}
          />
        ))}
      </svg>
      {hover && (
        <div style={{
          position: "absolute", left: hover.x + 10, top: Math.max(0, hover.y - 30),
          background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 4,
          padding: "6px 10px", fontSize: 11, pointerEvents: "none", zIndex: 10,
          boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
        }}>
          <div style={{ fontWeight: 600, color: INK }}>{hover.n.name}</div>
          <div style={{ color: MUTED }}>{hover.n.family}</div>
          <div style={{ color: INK, marginTop: 2 }}>
            {hover.n.p25.toFixed(1)}–{hover.n.p75.toFixed(1)}°C · {hover.n.obs.toLocaleString()} obs
          </div>
        </div>
      )}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Family treemap (recharts)
// ────────────────────────────────────────────────────────────────────────
function FamilyTreemap({ stats, onSelect, selected }: {
  stats: FamilyStat[]; onSelect: (f: string | null) => void; selected: string | null;
}) {
  const data = stats.map(s => ({
    name: s.family, size: s.obs, species: s.species, fill: s.color,
  }));
  const total = stats.reduce((a, b) => a + b.obs, 0);
  return (
    <ResponsiveContainer width="100%" height={320}>
      <Treemap
        data={data}
        dataKey="size"
        stroke="#fff"
        content={(props: any) => {
          const { x, y, width, height, name, size, species, fill } = props;
          const active = selected === name;
          const isLarge = width > 80 && height > 40;
          return (
            <g style={{ cursor: "pointer" }}
              onClick={() => onSelect(active ? null : name)}>
              <rect x={x} y={y} width={width} height={height}
                fill={fill ?? BLUE}
                fillOpacity={selected ? (active ? 0.95 : 0.3) : 0.85}
                stroke={active ? INK : "#fff"}
                strokeWidth={active ? 2 : 1} />
              {isLarge && name && (
                <>
                  <text x={x + 6} y={y + 16} style={{ fontSize: 11, fill: "#fff", fontWeight: 600 }}>
                    {name.length > 22 ? name.slice(0, 20) + "…" : name}
                  </text>
                  <text x={x + 6} y={y + 30} style={{ fontSize: 10, fill: "rgba(255,255,255,0.85)" }}>
                    {size?.toLocaleString()} obs · {species} sp
                  </text>
                  <text x={x + 6} y={y + height - 6} style={{ fontSize: 9, fill: "rgba(255,255,255,0.7)" }}>
                    {total > 0 ? ((size / total) * 100).toFixed(1) : 0}%
                  </text>
                </>
              )}
              {!isLarge && width > 28 && height > 16 && (
                <text x={x + 4} y={y + 12} style={{ fontSize: 9, fill: "#fff" }}>
                  {name && name.length > 10 ? name.slice(0, 8) + "…" : name}
                </text>
              )}
            </g>
          );
        }}
      />
    </ResponsiveContainer>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Cross-domain timeseries
// ────────────────────────────────────────────────────────────────────────
function CrossDomainChart({ rows }: { rows: DailyRow[] }) {
  const fmtDate = (d: string) => d.slice(5); // MM-DD

  return (
    <>
      <p style={{ fontSize: 11, color: MUTED, margin: "0 0 8px 0" }}>
        Daily bird observations overlaid on temperature, precipitation, and streamflow — one row per domain.
      </p>

      <div style={{ fontSize: 11, color: MUTED, marginBottom: 4, fontWeight: 600 }}>Bird observations / day</div>
      <ResponsiveContainer width="100%" height={140}>
        <ComposedChart data={rows} margin={{ top: 5, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: MUTED, fontSize: 10 }} stroke="#ccc" />
          <YAxis tick={{ fill: MUTED, fontSize: 10 }} stroke="#ccc" />
          <RTooltip
            contentStyle={{ fontSize: 11, border: `1px solid ${BORDER}` }}
            labelFormatter={fmtDate}
          />
          <Bar dataKey="obs" fill={BLUE} fillOpacity={0.55} name="Total obs" />
          <Line type="monotone" dataKey="notables" stroke={RED} strokeWidth={2} dot={false} name="Notables" />
        </ComposedChart>
      </ResponsiveContainer>

      <div style={{ fontSize: 11, color: MUTED, marginTop: 14, marginBottom: 4, fontWeight: 600 }}>Temperature & precipitation</div>
      <ResponsiveContainer width="100%" height={120}>
        <ComposedChart data={rows} margin={{ top: 5, right: 20, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: MUTED, fontSize: 10 }} stroke="#ccc" />
          <YAxis yAxisId="t" tick={{ fill: MUTED, fontSize: 10 }} stroke="#ccc" />
          <YAxis yAxisId="p" orientation="right" tick={{ fill: MUTED, fontSize: 10 }} stroke="#ccc" />
          <RTooltip contentStyle={{ fontSize: 11, border: `1px solid ${BORDER}` }} labelFormatter={fmtDate} />
          <Area yAxisId="t" type="monotone" dataKey="tmax" stroke={ORANGE} fill={ORANGE} fillOpacity={0.2} name="Tmax °C" />
          <Bar yAxisId="p" dataKey="prcp" fill={BLUE} fillOpacity={0.7} name="Prcp mm" />
        </ComposedChart>
      </ResponsiveContainer>

      <div style={{ fontSize: 11, color: MUTED, marginTop: 14, marginBottom: 4, fontWeight: 600 }}>Median daily streamflow (USGS AZ sites)</div>
      <ResponsiveContainer width="100%" height={110}>
        <ComposedChart data={rows} margin={{ top: 5, right: 20, left: 0, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="date" tickFormatter={fmtDate} tick={{ fill: MUTED, fontSize: 10 }} stroke="#ccc" />
          <YAxis tick={{ fill: MUTED, fontSize: 10 }} stroke="#ccc" />
          <RTooltip contentStyle={{ fontSize: 11, border: `1px solid ${BORDER}` }} labelFormatter={fmtDate} />
          <Area type="monotone" dataKey="discharge" stroke={PURPLE} fill={PURPLE} fillOpacity={0.25} name="Median cfs" />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Notables feed
// ────────────────────────────────────────────────────────────────────────
function NotablesFeed({ items, searchTerm, onSearch }: {
  items: NotablePt[]; searchTerm: string; onSearch: (s: string) => void;
}) {
  const filtered = items.filter(i => {
    if (!searchTerm) return true;
    const t = searchTerm.toLowerCase();
    return i.species.toLowerCase().includes(t)
      || i.location.toLowerCase().includes(t)
      || i.family.toLowerCase().includes(t);
  });

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <Search size={14} color={MUTED} />
        <input
          value={searchTerm}
          onChange={e => onSearch(e.target.value)}
          placeholder="filter species, family, or location…"
          style={{
            flex: 1, padding: "6px 10px", border: `1px solid ${BORDER}`,
            borderRadius: 4, fontSize: 12, outline: "none",
          }}
        />
        <span style={{ fontSize: 11, color: MUTED }}>
          {filtered.length.toLocaleString()} / {items.length.toLocaleString()}
        </span>
      </div>

      <div style={{ maxHeight: 520, overflowY: "auto", border: `1px solid ${BORDER}`, borderRadius: 4 }}>
        {filtered.slice(0, 200).map((it, i) => (
          <div key={it.id + "-" + i} style={{
            padding: "10px 12px",
            borderBottom: i < filtered.length - 1 ? `1px solid ${BORDER}` : "none",
            background: i % 2 === 0 ? "#fff" : "#fafafa",
            display: "grid", gridTemplateColumns: "1fr auto", gap: 8,
          }}>
            <div>
              <div style={{ fontWeight: 600, color: INK, fontSize: 13 }}>{it.species}</div>
              <div style={{ color: MUTED, fontSize: 11, marginTop: 2 }}>
                {it.family} · {it.location}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 11, color: MUTED }}>{it.date}</div>
              <div style={{ fontSize: 11, color: RED, fontWeight: 600, marginTop: 2 }}>
                {it.count > 0 ? `×${it.count}` : "present"}
              </div>
            </div>
          </div>
        ))}
        {filtered.length > 200 && (
          <div style={{ padding: 8, fontSize: 11, color: MUTED, textAlign: "center" }}>
            showing first 200 of {filtered.length}
          </div>
        )}
      </div>
    </>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Hotspot leaderboard w/ sparkline
// ────────────────────────────────────────────────────────────────────────
function Sparkline({ values, color }: { values: number[]; color: string }) {
  if (!values.length) return <svg width={60} height={16} />;
  const max = Math.max(1, ...values);
  const w = 60, h = 16, stepX = w / Math.max(1, values.length - 1);
  const pts = values.map((v, i) => `${i * stepX},${h - (v / max) * h}`).join(" ");
  return (
    <svg width={w} height={h}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.4} />
    </svg>
  );
}

function HotspotLeaderboard({ hotspots, sparklines }: {
  hotspots: HotspotPt[]; sparklines: Map<string, number[]>;
}) {
  const top = [...hotspots].sort((a, b) => b.species - a.species).slice(0, 20);
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr style={{ borderBottom: `2px solid ${BORDER}`, textAlign: "left" }}>
            {["#", "Hotspot", "County", "Species", "Obs", "H′", "7-day trend", "Peak", "% Notable"].map(h => (
              <th key={h} style={{ padding: "8px 10px", color: MUTED, fontWeight: 600, whiteSpace: "nowrap" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {top.map((r, i) => (
            <tr key={r.id} style={{ borderBottom: `1px solid ${BORDER}`, background: i % 2 === 0 ? "#fff" : "#fafafa" }}>
              <td style={{ padding: "8px 10px", color: "#999" }}>{i + 1}</td>
              <td style={{ padding: "8px 10px", color: INK, fontWeight: i < 3 ? 600 : 400 }}>{r.name}</td>
              <td style={{ padding: "8px 10px", color: MUTED }}>{r.county.replace("US-AZ-", "")}</td>
              <td style={{ padding: "8px 10px", fontWeight: 600, color: speciesColor(r.species) }}>{r.species}</td>
              <td style={{ padding: "8px 10px", color: INK }}>{r.obs.toLocaleString()}</td>
              <td style={{ padding: "8px 10px", color: INK }}>{r.diversity.toFixed(3)}</td>
              <td style={{ padding: "8px 10px" }}>
                <Sparkline values={sparklines.get(r.id) ?? []} color={speciesColor(r.species)} />
              </td>
              <td style={{ padding: "8px 10px", color: MUTED, textTransform: "capitalize" }}>{r.peakSeason}</td>
              <td style={{ padding: "8px 10px", color: r.notable > 5 ? RED : INK }}>{r.notable}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────
// Main
// ────────────────────────────────────────────────────────────────────────
type Tab = "overview" | "map" | "species" | "crossdomain" | "notables";

export default function BiodiversityDashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [selectedFamily, setSelectedFamily] = useState<string | null>(null);
  const [mapLayer, setMapLayer] = useState<MapLayer>("species");
  const [overlay, setOverlay] = useState<Overlay>(null);
  const [drawerHotspot, setDrawerHotspot] = useState<HotspotPt | null>(null);
  const [search, setSearch] = useState("");

  // ── SQL ──
  const kpis = useSQLQuery(`
    WITH obs AS (
      SELECT COUNT(*) AS obs_n,
             COUNT(DISTINCT species_code) AS species_n,
             SUM(CASE WHEN is_notable THEN 1 ELSE 0 END) AS notable_n
      FROM "databox"."ebird"."int_ebird_enriched_observations"
    ),
    h AS (SELECT COUNT(*) AS hot_n FROM "databox"."ebird"."fct_hotspot_species_diversity"),
    w AS (SELECT AVG(tmax) AS avg_tmax, COUNT(DISTINCT station) AS st_n FROM "databox"."noaa"."fct_daily_weather" WHERE tmax IS NOT NULL),
    s AS (SELECT COUNT(DISTINCT site_no) AS sf_n FROM "databox"."usgs"."fct_daily_streamflow")
    SELECT obs.obs_n, obs.species_n, obs.notable_n, h.hot_n, w.avg_tmax, w.st_n, s.sf_n FROM obs, h, w, s
  `);

  const hotspots = useSQLQuery(`
    SELECT location_id, location_name, county_code,
      ROUND(longitude::DOUBLE, 4) AS lon,
      ROUND(latitude::DOUBLE, 4) AS lat,
      total_species_count AS species,
      total_observations AS obs,
      ROUND(pct_notable_observations::DOUBLE, 1) AS notable,
      ROUND(shannon_diversity_index::DOUBLE, 3) AS diversity,
      COALESCE(peak_season, '') AS peak,
      COALESCE(most_common_species_name, '') AS top_bird
    FROM "databox"."ebird"."fct_hotspot_species_diversity"
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
  `);

  const families = useSQLQuery(`
    SELECT
      COALESCE(NULLIF(family_common_name, ''), 'Unknown') AS family,
      COUNT(*) AS obs,
      COUNT(DISTINCT species_code) AS species
    FROM "databox"."ebird"."int_ebird_enriched_observations"
    GROUP BY 1
    ORDER BY obs DESC
    LIMIT 12
  `);

  const heatmap = useSQLQuery(`
    WITH top_fams AS (
      SELECT COALESCE(NULLIF(family_common_name, ''), 'Unknown') AS family, COUNT(*) AS n
      FROM "databox"."ebird"."int_ebird_enriched_observations"
      GROUP BY 1 ORDER BY n DESC LIMIT 10
    )
    SELECT
      COALESCE(NULLIF(e.family_common_name, ''), 'Unknown') AS family,
      e.time_of_day AS tod,
      COUNT(*) AS n
    FROM "databox"."ebird"."int_ebird_enriched_observations" e
    JOIN top_fams t ON t.family = COALESCE(NULLIF(e.family_common_name, ''), 'Unknown')
    WHERE e.time_of_day IS NOT NULL
    GROUP BY 1, 2
  `);

  const speciesWx = useSQLQuery(`
    SELECT
      sp.species_code AS code,
      sp.common_name AS name,
      COALESCE(NULLIF(sp.family_common_name, ''), 'Unknown') AS family,
      sp.avg_high_temp_c::DOUBLE AS avg_high,
      sp.avg_low_temp_c::DOUBLE AS avg_low,
      sp.p25_high_temp_c::DOUBLE AS p25,
      sp.p75_high_temp_c::DOUBLE AS p75,
      sp.pct_rainy_days::DOUBLE AS pct_rainy,
      sp.total_observations::BIGINT AS obs,
      sp.total_observation_days::BIGINT AS days,
      COALESCE(sp.dominant_season, '') AS season
    FROM "databox"."analytics"."fct_species_weather_preferences" sp
    WHERE sp.avg_high_temp_c IS NOT NULL
      AND sp.p25_high_temp_c IS NOT NULL
      AND sp.p75_high_temp_c IS NOT NULL
  `);

  const daily = useSQLQuery(`
    WITH b AS (
      SELECT observation_date AS d,
             COUNT(*) AS obs,
             SUM(CASE WHEN is_notable THEN 1 ELSE 0 END) AS notables,
             COUNT(DISTINCT species_code) AS species
      FROM "databox"."ebird"."int_ebird_enriched_observations" GROUP BY 1
    ),
    w AS (
      SELECT observation_date AS d, AVG(tmax) AS tmax, AVG(prcp) AS prcp
      FROM "databox"."noaa"."fct_daily_weather" GROUP BY 1
    ),
    sf AS (
      SELECT observation_date AS d, MEDIAN(discharge_cfs) AS discharge
      FROM "databox"."usgs"."fct_daily_streamflow"
      WHERE discharge_cfs > 0
      GROUP BY 1
    )
    SELECT
      CAST(b.d AS VARCHAR) AS date,
      b.obs::BIGINT AS obs,
      b.notables::BIGINT AS notables,
      b.species::BIGINT AS species,
      w.tmax::DOUBLE AS tmax,
      w.prcp::DOUBLE AS prcp,
      sf.discharge::DOUBLE AS discharge
    FROM b LEFT JOIN w ON w.d = b.d LEFT JOIN sf ON sf.d = b.d
    ORDER BY b.d
  `);

  const notables = useSQLQuery(`
    SELECT
      submission_id AS id,
      common_name AS species,
      COALESCE(NULLIF(family_common_name, ''), 'Unknown') AS family,
      location_name AS location,
      location_id AS loc_id,
      latitude::DOUBLE AS lat,
      longitude::DOUBLE AS lon,
      CAST(observation_date AS VARCHAR) AS date,
      count::BIGINT AS count
    FROM "databox"."ebird"."int_ebird_enriched_observations"
    WHERE is_notable = TRUE
    ORDER BY observation_date DESC, common_name
    LIMIT 500
  `);

  const stations = useSQLQuery(`
    SELECT station_id AS id, latitude::DOUBLE AS lat, longitude::DOUBLE AS lon, station_name AS label
    FROM "databox"."noaa_staging"."stg_noaa_stations"
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
  `);

  const streams = useSQLQuery(`
    SELECT site_no AS id, latitude::DOUBLE AS lat, longitude::DOUBLE AS lon, site_name AS label
    FROM "databox"."usgs_staging"."stg_usgs_sites"
    WHERE state_cd = '04' AND latitude IS NOT NULL AND longitude IS NOT NULL
  `);

  const hotspotSparks = useSQLQuery(`
    SELECT
      location_id,
      CAST(observation_date AS VARCHAR) AS d,
      COUNT(*) AS n
    FROM "databox"."ebird"."int_ebird_enriched_observations"
    WHERE observation_date >= (SELECT MAX(observation_date) FROM "databox"."ebird"."int_ebird_enriched_observations") - INTERVAL 7 DAY
    GROUP BY 1, 2
  `);

  const drawerTopSpecies = useSQLQuery(
    drawerHotspot ? `
      SELECT
        common_name AS name,
        COALESCE(NULLIF(family_common_name, ''), 'Unknown') AS family,
        COUNT(*) AS n,
        SUM(CASE WHEN is_notable THEN 1 ELSE 0 END) AS notable_n,
        MAX(CAST(observation_date AS VARCHAR)) AS last_seen
      FROM "databox"."ebird"."int_ebird_enriched_observations"
      WHERE location_id = '${drawerHotspot.id.replace(/'/g, "''")}'
      GROUP BY 1, 2
      ORDER BY n DESC
      LIMIT 15
    ` : `SELECT 1 WHERE FALSE`
  );

  // ── Derived ──
  const kpiRow = Array.isArray(kpis.data) ? kpis.data[0] : null;

  const pts: HotspotPt[] = useMemo(() =>
    (Array.isArray(hotspots.data) ? hotspots.data : []).map((r: any) => ({
      id: S(r.location_id), name: S(r.location_name), county: S(r.county_code),
      lon: N(r.lon), lat: N(r.lat),
      species: N(r.species), obs: N(r.obs), notable: N(r.notable),
      diversity: N(r.diversity), peakSeason: S(r.peak), topBird: S(r.top_bird),
    })),
    [hotspots.data]
  );

  const familyStats: FamilyStat[] = useMemo(() => {
    const rows = Array.isArray(families.data) ? families.data : [];
    return rows.map((r: any, i: number) => ({
      family: S(r.family), obs: N(r.obs), species: N(r.species),
      color: FAMILY_COLORS[i % FAMILY_COLORS.length],
    }));
  }, [families.data]);

  const heatCells: HeatCell[] = useMemo(() =>
    (Array.isArray(heatmap.data) ? heatmap.data : []).map((r: any) => ({
      family: S(r.family), tod: S(r.tod), n: N(r.n),
    })),
    [heatmap.data]
  );

  const heatFamilies = useMemo(() => {
    const fams = Array.from(new Set(heatCells.map(c => c.family)));
    const totals = new Map<string, number>();
    heatCells.forEach(c => totals.set(c.family, (totals.get(c.family) ?? 0) + c.n));
    return fams.sort((a, b) => (totals.get(b) ?? 0) - (totals.get(a) ?? 0));
  }, [heatCells]);

  const speciesWxData: SpeciesWx[] = useMemo(() =>
    (Array.isArray(speciesWx.data) ? speciesWx.data : []).map((r: any) => ({
      code: S(r.code), name: S(r.name), family: S(r.family),
      avgHigh: N(r.avg_high), avgLow: N(r.avg_low),
      p25: N(r.p25), p75: N(r.p75),
      pctRainy: N(r.pct_rainy), obs: N(r.obs), days: N(r.days),
      season: S(r.season),
    })).filter(d => d.obs > 0),
    [speciesWx.data]
  );

  const dailyRows: DailyRow[] = useMemo(() =>
    (Array.isArray(daily.data) ? daily.data : []).map((r: any) => ({
      date: S(r.date),
      obs: N(r.obs), notables: N(r.notables), species: N(r.species),
      tmax: r.tmax == null ? null : N(r.tmax),
      prcp: r.prcp == null ? null : N(r.prcp),
      discharge: r.discharge == null ? null : N(r.discharge),
    })),
    [daily.data]
  );

  const notableItems: NotablePt[] = useMemo(() =>
    (Array.isArray(notables.data) ? notables.data : []).map((r: any) => ({
      id: S(r.id), species: S(r.species), family: S(r.family),
      location: S(r.location), locId: S(r.loc_id),
      lat: N(r.lat), lon: N(r.lon),
      date: S(r.date), count: N(r.count),
    })),
    [notables.data]
  );

  const weatherMarkers: MarkerPt[] = useMemo(() =>
    (Array.isArray(stations.data) ? stations.data : []).map((r: any) => ({
      id: S(r.id), lat: N(r.lat), lon: N(r.lon), label: S(r.label),
    })),
    [stations.data]
  );

  const streamMarkers: MarkerPt[] = useMemo(() =>
    (Array.isArray(streams.data) ? streams.data : []).map((r: any) => ({
      id: S(r.id), lat: N(r.lat), lon: N(r.lon), label: S(r.label),
    })),
    [streams.data]
  );

  const sparkMap: Map<string, number[]> = useMemo(() => {
    const rows = Array.isArray(hotspotSparks.data) ? hotspotSparks.data : [];
    const byLoc = new Map<string, Map<string, number>>();
    rows.forEach((r: any) => {
      const loc = S(r.location_id); const d = S(r.d); const n = N(r.n);
      if (!byLoc.has(loc)) byLoc.set(loc, new Map());
      byLoc.get(loc)!.set(d, n);
    });
    const allDates = Array.from(new Set(rows.map((r: any) => S(r.d)))).sort();
    const out = new Map<string, number[]>();
    byLoc.forEach((m, loc) => {
      out.set(loc, allDates.map(d => m.get(d) ?? 0));
    });
    return out;
  }, [hotspotSparks.data]);

  // Family filter: restrict species-level views + notables
  const filteredSpeciesWx = selectedFamily
    ? speciesWxData.filter(d => d.family === selectedFamily)
    : speciesWxData;
  const filteredNotables = selectedFamily
    ? notableItems.filter(n => n.family === selectedFamily)
    : notableItems;

  // ── Render ──
  return (
    <div style={{ background: SOFT, minHeight: "100vh", padding: "20px 24px", fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <div style={{ maxWidth: 1240, margin: "0 auto" }}>

        {/* Header */}
        <header style={{ marginBottom: 18 }}>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: INK, margin: 0 }}>
            Arizona Biodiversity Intelligence
          </h1>
          <p style={{ color: MUTED, fontSize: 13, marginTop: 6, marginBottom: 0 }}>
            eBird × NOAA × USGS · 30-day window · US-AZ
          </p>
        </header>

        {/* KPIs */}
        <Card>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 24 }}>
            <KpiTile label="Species" value={kpis.isLoading ? null : N(kpiRow?.species_n)} loading={kpis.isLoading} />
            <KpiTile label="Observations" value={kpis.isLoading ? null : N(kpiRow?.obs_n)} loading={kpis.isLoading} />
            <KpiTile label="Hotspots" value={kpis.isLoading ? null : N(kpiRow?.hot_n)} loading={kpis.isLoading} />
            <KpiTile label="Notable sightings" value={kpis.isLoading ? null : N(kpiRow?.notable_n)} loading={kpis.isLoading} />
            <KpiTile label="Avg Tmax °C" value={kpis.isLoading ? null : N(kpiRow?.avg_tmax).toFixed(1)} sub={`${N(kpiRow?.st_n)} NOAA stations`} loading={kpis.isLoading} />
            <KpiTile label="Stream sites" value={kpis.isLoading ? null : N(kpiRow?.sf_n)} sub="USGS gages" loading={kpis.isLoading} />
          </div>
        </Card>

        {/* Family filter + Tab nav */}
        <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center", flexWrap: "wrap" }}>
          {(["overview", "map", "species", "crossdomain", "notables"] as Tab[]).map(t => {
            const label = ({ overview: "Overview", map: "Map", species: "Species", crossdomain: "Cross-domain", notables: "Notables" } as any)[t];
            const Icon = ({ overview: BarChart3, map: MapIcon, species: Bird, crossdomain: CloudRain, notables: AlertCircle } as any)[t];
            const active = tab === t;
            return (
              <button key={t} onClick={() => setTab(t)} style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "8px 14px", borderRadius: 6,
                border: `1px solid ${active ? INK : BORDER}`,
                background: active ? INK : "#fff",
                color: active ? "#fff" : INK,
                fontSize: 13, fontWeight: 600, cursor: "pointer",
              }}>
                <Icon size={14} />{label}
              </button>
            );
          })}
          {selectedFamily && (
            <button onClick={() => setSelectedFamily(null)} style={{
              marginLeft: "auto", padding: "6px 10px", borderRadius: 4,
              border: `1px solid ${ORANGE}`, background: "#fff6eb", color: ORANGE,
              fontSize: 11, cursor: "pointer",
            }}>
              Filter: {selectedFamily} ×
            </button>
          )}
        </div>

        {/* ── OVERVIEW TAB ── */}
        {tab === "overview" && (
          <>
            <Card title="Family composition" icon={<BarChart3 size={14} color={INK} />}
              right={<span style={{ fontSize: 11, color: MUTED }}>click to filter other views</span>}>
              {families.isLoading
                ? <div style={{ height: 320, background: "#eee", borderRadius: 4 }} />
                : <FamilyTreemap stats={familyStats} onSelect={setSelectedFamily} selected={selectedFamily} />
              }
            </Card>

            <Card title="Cross-domain timeseries" icon={<TrendingUp size={14} color={INK} />}>
              {daily.isLoading
                ? <div style={{ height: 400, background: "#eee", borderRadius: 4 }} />
                : <CrossDomainChart rows={dailyRows} />
              }
            </Card>

            <Card title="Hotspot leaderboard" icon={<BarChart3 size={14} color={INK} />}>
              {hotspots.isLoading
                ? <div style={{ height: 300, background: "#eee", borderRadius: 4 }} />
                : <HotspotLeaderboard hotspots={pts} sparklines={sparkMap} />
              }
            </Card>
          </>
        )}

        {/* ── MAP TAB ── */}
        {tab === "map" && (
          <Card title="Hotspot map" icon={<MapIcon size={14} color={INK} />}
            right={
              <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                <div style={{ display: "flex", gap: 4 }}>
                  {(["species", "obs", "notable", "flock"] as MapLayer[]).map(l => (
                    <button key={l} onClick={() => setMapLayer(l)} style={{
                      padding: "4px 10px", fontSize: 11, borderRadius: 4,
                      border: `1px solid ${mapLayer === l ? INK : BORDER}`,
                      background: mapLayer === l ? INK : "#fff",
                      color: mapLayer === l ? "#fff" : INK,
                      cursor: "pointer", textTransform: "capitalize",
                    }}>{l === "flock" ? "diversity" : l}</button>
                  ))}
                </div>
                <div style={{ display: "flex", gap: 4 }}>
                  <button onClick={() => setOverlay(overlay === "weather" ? null : "weather")} style={{
                    padding: "4px 10px", fontSize: 11, borderRadius: 4,
                    border: `1px solid ${overlay === "weather" ? TEAL : BORDER}`,
                    background: overlay === "weather" ? "#e6f5f3" : "#fff", color: TEAL,
                    cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
                  }}><Layers size={11} />weather</button>
                  <button onClick={() => setOverlay(overlay === "stream" ? null : "stream")} style={{
                    padding: "4px 10px", fontSize: 11, borderRadius: 4,
                    border: `1px solid ${overlay === "stream" ? PURPLE : BORDER}`,
                    background: overlay === "stream" ? "#f0ebf7" : "#fff", color: PURPLE,
                    cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
                  }}><Waves size={11} />streams</button>
                </div>
              </div>
            }
          >
            <div style={{ display: "grid", gridTemplateColumns: drawerHotspot ? "1fr 320px" : "1fr", gap: 16 }}>
              <div>
                {hotspots.isLoading
                  ? <div style={{ height: 460, background: "#eee", borderRadius: 4 }} />
                  : <HotspotMap
                      points={pts}
                      weatherStations={weatherMarkers}
                      streamSites={streamMarkers}
                      familyFilter={selectedFamily}
                      layer={mapLayer}
                      overlay={overlay}
                      onHotspotClick={setDrawerHotspot}
                    />
                }
              </div>

              {drawerHotspot && (
                <div style={{ border: `1px solid ${BORDER}`, borderRadius: 6, padding: 14, background: "#fafafa" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: 8 }}>
                    <h3 style={{ fontSize: 13, fontWeight: 700, color: INK, margin: 0 }}>{drawerHotspot.name}</h3>
                    <button onClick={() => setDrawerHotspot(null)} style={{
                      border: "none", background: "transparent", fontSize: 16, cursor: "pointer", color: MUTED,
                    }}>×</button>
                  </div>
                  <div style={{ fontSize: 11, color: MUTED, marginBottom: 10 }}>
                    {drawerHotspot.county.replace("US-AZ-", "")} · {drawerHotspot.lat.toFixed(3)}, {drawerHotspot.lon.toFixed(3)}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
                    <div><div style={{ fontSize: 10, color: MUTED }}>Species</div><div style={{ fontSize: 18, fontWeight: 700, color: speciesColor(drawerHotspot.species) }}>{drawerHotspot.species}</div></div>
                    <div><div style={{ fontSize: 10, color: MUTED }}>Shannon H′</div><div style={{ fontSize: 18, fontWeight: 700, color: INK }}>{drawerHotspot.diversity.toFixed(3)}</div></div>
                    <div><div style={{ fontSize: 10, color: MUTED }}>Obs</div><div style={{ fontSize: 14, fontWeight: 600, color: INK }}>{drawerHotspot.obs.toLocaleString()}</div></div>
                    <div><div style={{ fontSize: 10, color: MUTED }}>Notable %</div><div style={{ fontSize: 14, fontWeight: 600, color: drawerHotspot.notable > 5 ? RED : INK }}>{drawerHotspot.notable}%</div></div>
                  </div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: INK, marginBottom: 6 }}>Top species here</div>
                  {drawerTopSpecies.isLoading ? (
                    <div style={{ height: 200, background: "#eee", borderRadius: 4 }} />
                  ) : (
                    <div style={{ maxHeight: 300, overflowY: "auto" }}>
                      {(Array.isArray(drawerTopSpecies.data) ? drawerTopSpecies.data : []).map((r: any, i: number) => (
                        <div key={i} style={{
                          padding: "6px 0", borderBottom: `1px solid ${BORDER}`,
                          display: "flex", justifyContent: "space-between", alignItems: "center",
                        }}>
                          <div>
                            <div style={{ fontSize: 11, color: INK, fontWeight: 500 }}>{S(r.name)}</div>
                            <div style={{ fontSize: 9, color: MUTED }}>{S(r.family)}</div>
                          </div>
                          <div style={{ fontSize: 11, color: INK, fontWeight: 600 }}>{N(r.n)}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>
        )}

        {/* ── SPECIES TAB ── */}
        {tab === "species" && (
          <>
            <Card title="Species × weather positioning" icon={<Thermometer size={14} color={INK} />}
              right={<span style={{ fontSize: 11, color: MUTED }}>{filteredSpeciesWx.length} species</span>}>
              {speciesWx.isLoading
                ? <div style={{ height: 340, background: "#eee", borderRadius: 4 }} />
                : filteredSpeciesWx.length === 0
                ? <div style={{ color: MUTED, fontSize: 12, padding: 40, textAlign: "center" }}>No species match current filter</div>
                : <SpeciesWeatherScatter data={filteredSpeciesWx} />
              }
            </Card>

            <Card title="Temperature tolerance beeswarm" icon={<Thermometer size={14} color={INK} />}>
              {speciesWx.isLoading
                ? <div style={{ height: 320, background: "#eee", borderRadius: 4 }} />
                : filteredSpeciesWx.length === 0
                ? <div style={{ color: MUTED, fontSize: 12, padding: 40, textAlign: "center" }}>No species match current filter</div>
                : <TempRangeBeeswarm data={filteredSpeciesWx} />
              }
            </Card>

            <Card title="Time of day × family" icon={<BarChart3 size={14} color={INK} />}>
              {heatmap.isLoading
                ? <div style={{ height: 280, background: "#eee", borderRadius: 4 }} />
                : <TimeOfDayHeatmap cells={heatCells} families={heatFamilies} />
              }
            </Card>
          </>
        )}

        {/* ── CROSS-DOMAIN TAB ── */}
        {tab === "crossdomain" && (
          <Card title="Birds × weather × streamflow" icon={<CloudRain size={14} color={INK} />}>
            {daily.isLoading
              ? <div style={{ height: 500, background: "#eee", borderRadius: 4 }} />
              : <CrossDomainChart rows={dailyRows} />
            }
          </Card>
        )}

        {/* ── NOTABLES TAB ── */}
        {tab === "notables" && (
          <Card title="Notable observations feed" icon={<AlertCircle size={14} color={INK} />}
            right={<span style={{ fontSize: 11, color: MUTED }}>rare/reviewable sightings</span>}>
            {notables.isLoading
              ? <div style={{ height: 500, background: "#eee", borderRadius: 4 }} />
              : <NotablesFeed items={filteredNotables} searchTerm={search} onSearch={setSearch} />
            }
          </Card>
        )}

        <p style={{ textAlign: "center", fontSize: 10, color: MUTED, marginTop: 20 }}>
          Data: eBird API · NOAA CDO · USGS NWIS · databox data pipeline
        </p>
      </div>
    </div>
  );
}
