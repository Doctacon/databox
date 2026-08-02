import { useEffect, useRef, useState } from "react";
import { getPublicAttribution } from "./publicData";
import { publicManifest } from "./publicAdapters/runtime";
import type {
  PublicAttribution,
  PublicAttributionSource,
  PublicManifest,
} from "./publicTypes";

type ManifestLoader = (signal?: AbortSignal) => Promise<PublicManifest>;
type AttributionLoader = (path: string, signal?: AbortSignal) => Promise<PublicAttribution>;

export type PublicCreditsPageProps = {
  loadManifest?: ManifestLoader;
  loadAttribution?: AttributionLoader;
};

export function safeAttributionHref(value: unknown): string | null {
  if (
    typeof value !== "string"
    || value !== value.trim()
    || !value
    || value.includes("\\")
    || /[\u0000-\u001f\u007f]/.test(value)
  ) return null;
  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:"
      || !url.hostname
      || url.username
      || url.password
      || url.port
    ) return null;
    return url.href;
  } catch {
    return null;
  }
}

export function safeDoiHref(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const doi = value.trim();
  if (doi !== value || !/^10\.\d{4,9}\/[A-Z0-9._;()/:+-]+$/i.test(doi)) return null;
  return `https://doi.org/${doi}`;
}

function sourceHost(href: string): string {
  return new URL(href).hostname.replace(/^www\./, "");
}

function SourceCredit({ source }: { source: PublicAttributionSource }) {
  const sourceHref = safeAttributionHref(source.url);
  const licenseHref = safeAttributionHref(source.license_url);
  return <article className="panel credit-source">
    <h2>{source.title}</h2>
    <dl className="credit-details">
      <div><dt>Provider</dt><dd>{source.provider}</dd></div>
      <div><dt>License</dt><dd>{licenseHref
        ? <a href={licenseHref} target="_blank" rel="noreferrer">{source.license}</a>
        : source.license}</dd></div>
    </dl>
    <p><strong>Credit:</strong> {source.credit}</p>
    {source.modifications && <p><strong>Changes made by Rufous:</strong> {source.modifications}</p>}
    {source.disclaimer && <p className="caveat"><strong>Source notice:</strong> {source.disclaimer}</p>}
    {sourceHref
      ? <a href={sourceHref} target="_blank" rel="noreferrer">Open provider source on {sourceHost(sourceHref)}</a>
      : <p className="source-status">Provider source link unavailable.</p>}
  </article>;
}

export function PublicCreditsPage({
  loadManifest = publicManifest,
  loadAttribution = getPublicAttribution,
}: PublicCreditsPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [manifest, setManifest] = useState<PublicManifest | null>(null);
  const [attribution, setAttribution] = useState<PublicAttribution | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    void loadManifest(controller.signal)
      .then(async (loadedManifest) => ({
        manifest: loadedManifest,
        attribution: await loadAttribution(loadedManifest.attribution_path, controller.signal),
      }))
      .then((loaded) => {
        if (!current) return;
        setManifest(loaded.manifest);
        setAttribution(loaded.attribution);
      })
      .catch((reason: unknown) => {
        if (!current || controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "Public attribution is unavailable.");
      });
    return () => {
      current = false;
      controller.abort();
    };
  }, [loadAttribution, loadManifest]);

  return <main className="credits-main">
    <header className="catalog-heading">
      <p className="eyebrow">Public data provenance</p>
      <h1 ref={headingRef} tabIndex={-1}>Credits and data sources</h1>
      <p>Rufous publishes only audited, licensed records and government place and boundary data. These credits travel with every public release.</p>
    </header>
    {error && <div className="error" role="alert"><strong>Could not load public credits.</strong><span>{error}</span></div>}
    {!attribution && !error && <p role="status">Loading release credits…</p>}
    {manifest && attribution && <>
      <section className="notice credit-release" aria-labelledby="credit-release-heading">
        <h2 id="credit-release-heading">About this release</h2>
        <p>{manifest.release_mode === "production"
          ? "This production snapshot uses licensed historical GBIF occurrences. It does not use the direct eBird API or eBird hotspots."
          : "This preview uses fictional bird occurrences. It is not production observation data."}</p>
        <p className="source-status">Generated {new Date(manifest.generated_at).toLocaleString()} · Release {manifest.data_version} · {manifest.counts.observations.toLocaleString()} occurrence records</p>
      </section>
      <section className="credits-grid" aria-label="Release-level data sources">
        {attribution.sources.map((source) => <SourceCredit key={`${source.provider}-${source.title}`} source={source} />)}
      </section>
      {attribution.items.length > 0 && <section className="panel credit-items" aria-labelledby="credit-items-heading">
        <h2 id="credit-items-heading">Dataset, occurrence, and media citations</h2>
        <ul>{attribution.items.map((item) => {
          const sourceHref = safeAttributionHref(item.source_url);
          const licenseHref = safeAttributionHref(item.license_url);
          const doiHref = safeDoiHref(item.dataset_doi);
          return <li key={item.attribution_id}>
            <strong>{item.dataset_title || item.creator}</strong>
            <span>Provider: {item.provider}</span>
            <span>Creator: {item.creator}</span>
            {item.publisher && <span>Publisher: {item.publisher}</span>}
            {item.dataset_citation && <span>Recommended citation: {item.dataset_citation}</span>}
            <span>License: {licenseHref
              ? <a href={licenseHref} target="_blank" rel="noreferrer">{item.license}</a>
              : item.license}</span>
            {doiHref && <a href={doiHref} target="_blank" rel="noreferrer">Dataset DOI: {item.dataset_doi}</a>}
            {sourceHref
              ? <a href={sourceHref} target="_blank" rel="noreferrer">Open cited source on {sourceHost(sourceHref)}</a>
              : <span className="source-status">Cited source link unavailable.</span>}
          </li>;
        })}</ul>
      </section>}
      <p className="source-status credit-policy">Licensing is fail-closed: records with missing, malformed, noncommercial, no-derivatives, or all-rights-reserved terms are excluded from the public release.</p>
    </>}
  </main>;
}
