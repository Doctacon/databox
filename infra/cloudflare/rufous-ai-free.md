# Rufous Workers AI Free release gate

Rufous's deterministic trip planner remains a static Cloudflare Pages app. Its
optional field-strategy action selection is the repository's one reviewed dynamic service,
published only at `https://rufous-ai.loughondata.com`. The Worker has no access
to Pages, R2, KV, D1, Queues, Durable Objects, email, analytics storage, or user
records. Its only declared bindings are Workers AI and the built-in rate
limiter. The Turnstile secret is provisioned directly on the Worker and is not
declared as a plaintext Wrangler variable.

This uses the existing Cloudflare account. R2 billing does not itself enroll the
account in Workers Paid, but an operator must verify the **Workers & Pages plan**
still says **Free** before enabling a deployment. The repository variable is a
manual attestation, not a billing API check.

## One-time account setup

1. In Cloudflare, confirm the Workers plan is **Free**. Do not upgrade it.
2. Create a Turnstile widget that allows exactly
   `rufous.loughondata.com`. Record its public site key and secret. After the
   initial `rufous-ai` script exists, but before enabling the Pages client,
   provision the secret directly on that Worker as `TURNSTILE_SECRET`.
   Configure the expected Turnstile action as `trip_plan_enrich`.
3. Keep `workers.dev` and Worker preview URLs disabled. Attach only the custom
   domain `rufous-ai.loughondata.com`.
4. Create one deployment token with **Workers Scripts Edit** for this Cloudflare
   account and **Workers Routes Edit** for the `loughondata.com` zone/custom
   domain. Cloudflare grants the script permission at account scope, not per
   script; repository workflow policy limits its use to `rufous-ai`. The token
   must have no Billing, R2, Pages, Turnstile, or broader DNS-administration
   permission.
5. Configure these GitHub repository variables:

   - `RUF_AI_RELEASE_ENABLED=true`
   - `RUF_AI_WORKERS_PLAN=free`
   - `RUF_AI_ACCOUNT_ID` with the Cloudflare account identifier
   - `RUF_AI_TURNSTILE_SITE_KEY` with the public widget site key

6. Configure exactly one GitHub Actions secret for this workflow:
   `RUF_AI_WORKER_API_TOKEN`. Do not reuse the Pages token or either R2 S3
   credential.

The Turnstile secret remains only in Cloudflare. It is deliberately absent from
GitHub and every `VITE_` variable. The account ID and Turnstile site key are not
credentials, but they still remain environment configuration rather than being
hard-coded into application source.

## Deployment and fallback

`.github/workflows/rufous-ai-worker.yaml` tests pull requests without secrets
and deploys only a current `main` revision. Deployment fails unless both manual
gates have their exact values. It uses the standard GitHub-hosted Ubuntu runner
and the isolated Worker token; it never receives Pages or R2 credentials.

The browser creates and saves a complete deterministic plan before offering AI
field-strategy enhancement. A production enhancement requires a fresh, single-use Turnstile
token. The Worker validates the token, its hostname, and the exact
`trip_plan_enrich` action, applies its rate limit, and makes at most one bounded
model call with no retry. The model receives only the reviewed fixed schema and
returns allowlisted action identifiers; fixed browser code renders their prose.

On Workers Free, Cloudflare's daily Workers AI allowance is the financial stop:
after the free neurons are exhausted, model operations fail until the UTC
reset. The Worker converts quota, timeout, validation, and model failures into a
bounded unavailable response. The browser retains the deterministic plan. The
separate Workers Free request limit similarly fails closed. Rate limiting and
Turnstile reduce abuse, but neither is treated as the accounting boundary.

R2 has separate billing and is not contacted by this Worker. The browser's
existing direct, read-only R2 data path is unchanged.

## Operational checks

Before each enablement and at least quarterly:

- verify the dashboard still reports Workers Free and the documented free
  allowances have not changed;
- confirm `RUF_AI_WORKERS_PLAN` is exactly `free` and rotate the deployment
  token if its scope has expanded;
- confirm only the two reviewed runtime bindings and the pre-provisioned
  Turnstile secret exist;
- confirm `workers.dev` and preview URLs remain disabled;
- exercise invalid, reused, and expired Turnstile tokens, rate limiting, model
  timeout, Workers AI quota exhaustion, and total Worker unavailability;
- verify plan creation, saved plans, maps, media, and calendar downloads still
  work with the Worker disabled.

The emergency AI stop is to set `RUF_AI_RELEASE_ENABLED=false` and disable the
custom domain. A later Pages build may omit the public site key as well. Never
upgrade the Workers plan as a response to quota exhaustion; deterministic
planning is the intended fallback.

Account compromise, a manual Workers Paid upgrade, or a future pricing change
can defeat this operational guarantee. Protect Cloudflare and GitHub with
passkeys or two-factor authentication and repeat the plan review quarterly.

Cloudflare references: [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/),
[Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/),
[Workers limits](https://developers.cloudflare.com/workers/platform/limits/),
and [Turnstile server-side validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/).
