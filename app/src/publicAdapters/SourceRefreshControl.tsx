import { useEffect, useState } from "react";
import type { PublicManifest } from "../publicTypes";
import { publicManifest } from "./runtime";

export function SourceRefreshControl() {
  const [manifest, setManifest] = useState<PublicManifest | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    let current = true;
    void publicManifest()
      .then((value) => { if (current) setManifest(value); })
      .catch(() => { if (current) setUnavailable(true); });
    return () => { current = false; };
  }, []);
  return <div className="header-refresh">
    <p>Published snapshot · browser-only</p>
    {manifest && <span className="refresh-status">
      Immutable JSON release · {new Date(manifest.generated_at).toLocaleString()}
    </span>}
    {!manifest && !unavailable && <span className="refresh-status" role="status">Reading snapshot…</span>}
    {unavailable && <span className="refresh-status error" role="alert">Published snapshot unavailable</span>}
  </div>;
}
