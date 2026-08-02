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
- bypass cache for `/rufous-public/manifest.json`;
- use a hostname-scoped WAF rule to allow only GET, HEAD, and CORS preflight
  OPTIONS, reject query strings, and block paths outside the pointer and
  immutable-release namespaces;
- keep Cloudflare's default DDoS protection enabled. Do not turn on free Bot
  Fight Mode solely for Rufous: it applies to the entire shared
  `loughondata.com` zone and cannot be scoped or skipped;
- a Free-plan rate limit can match the Rufous paths but not the hostname. Treat
  that broader path-scoped rule and zone-wide Smart Tiered Cache as optional;
- apply a 90-day R2 Bucket Lock to the `rufous-public/releases/` prefix while
  leaving the mutable `rufous-public/manifest.json` pointer outside the lock;
- do not enable Cache Reserve.

The emergency cost stop is to block or detach the custom domain. Do not delete
the bucket or active release: the browser will fall back to the complete Pages
copy while the data hostname is unavailable.

Cloudflare references: [public R2 buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/),
[CORS](https://developers.cloudflare.com/r2/buckets/cors/), and
[R2 caching](https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/),
and [R2 Bucket Locks](https://developers.cloudflare.com/r2/buckets/bucket-locks/).
