# Rufous R2 account settings

These files document the small amount of Cloudflare account state that is
intentionally not created by CI. They contain no account ID, token, bucket name,
or other credential.

Use a dedicated **Standard** R2 bucket that contains public Rufous release
objects only. Attach the custom domain `rufous-data.loughondata.com`, disable its
`r2.dev` URL, and apply [`rufous-r2-cors.json`](rufous-r2-cors.json). The bucket
must never receive a DuckDB file, raw pipeline output, personal observation, or
private location.

Create two independent credentials:

- the existing Pages deployment token, limited to Pages Write;
- an R2 S3 token, limited to Object Read & Write on this exact bucket.

Neither token should have billing, DNS, Worker, or account-administration
permission. Store them only as GitHub Actions secrets. The public application
uses the custom domain and never receives either credential or the R2 S3
endpoint.

Apply these edge rules to the custom domain:

- cache `/rufous-public/releases/*` as immutable and ignore or reject query
  strings;
- cache `/rufous-media/v1/objects/*` as immutable and reject query strings;
- cache `/rufous-audio/v1/objects/*` as immutable and reject query strings;
- bypass cache for `/rufous-public/manifest.json`;
- use a hostname-scoped WAF rule to allow only GET, HEAD, and CORS preflight
  OPTIONS, reject query strings, and block paths outside the pointer,
  immutable-release, and exact content-addressed media and audio namespaces.
  Permit only `.webp` media and `.mp3`, `.wav`, `.m4a`, or `.ogg` audio.
  Browsers may fetch known object URLs but cannot list, upload, replace, or
  delete objects;
- keep Cloudflare's default DDoS protection enabled. Do not turn on free Bot
  Fight Mode solely for Rufous: it applies to the entire shared
  `loughondata.com` zone and cannot be scoped or skipped;
- keep the single Free-plan rate limit scoped to the Rufous data hostname and
  the pointer, immutable release, media, and audio paths. The current rule
  blocks an IP for 10 seconds after more than 100 matching requests in 10
  seconds;
- apply a 90-day R2 Bucket Lock to the `rufous-public/releases/` prefix while
  leaving the mutable `rufous-public/manifest.json` pointer outside the lock;
- keep the content-addressed media and audio prefixes outside Bucket Lock until
  the takedown process has been reviewed. Their names are hashes and are never
  intentionally overwritten, while leaving them unlocked permits removal of a
  mistaken or contested public item;
- do not enable Cache Reserve.

The publisher independently lists the exact media prefix before any mutation,
verifies the bytes behind every reused object, and refuses a run above 5,000
new objects/1 GiB or a projected prefix above 20,000 objects/5 GiB. A Bucket
Lock does not replace that cumulative cost gate; locked orphan objects remain
included until a later reviewed cleanup is legally possible.

Object storage is also downstream of a human pixel-review gate. Production
accepts only final WebP hashes recorded in the committed
`config/rufous-media-visual-approvals.json` ledger with their reviewed USFWS
source pages and scientific names. A local refresh can prepare contact sheets,
but neither a newly discovered hash nor changed provenance can reach this
bucket until a human reviews and commits the corresponding approval entry.

The emergency cost stop is to block or detach the custom domain. Do not delete
the bucket or active release: the browser will fall back to the complete Pages
copy while the data hostname is unavailable.

The optional trip-planner field-strategy enhancement is a separate Worker with
no R2 binding or credential. Its exact Workers Free plan gate, Turnstile setup,
credential isolation, quota fallback, and emergency stop are documented in
[`rufous-ai-free.md`](rufous-ai-free.md). Do not grant its deployment token any
of the Pages or R2 permissions described above.

Cloudflare references: [public R2 buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/),
[CORS](https://developers.cloudflare.com/r2/buckets/cors/), and
[R2 caching](https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/),
and [R2 Bucket Locks](https://developers.cloudflare.com/r2/buckets/bucket-locks/).
