# Arasense Deployment Cost Control

Use this setup when you want people to use the full app but want it to stop before a small bill grows.

## Recommended domain layout

- `www.arasense.com`: public company website on Cloudflare Pages.
- `arasense.com`: redirect to `https://www.arasense.com`.
- `app.arasense.com`: protected FastAPI console/API through the Cloudflare Worker gateway.

## Why this protects cost

Google Cloud billing data is delayed, so a budget alert cannot stop usage exactly at `$1`.

The first line of defense should be the Cloudflare Worker in `cloudflare-worker/`. It blocks users and API calls before the request reaches Cloud Run.

The second line of defense is Cloud Run scaling limits:

- `min-instances 0`
- `max-instances 1`
- `cpu 1`
- `memory 1Gi`
- `concurrency 10`

The third line of defense is Google Cloud Billing alerts.

## Cloud Run environment

Run the helper script to create local config files with matching random secrets:

```powershell
.\scripts\prepare-app-deployment.ps1
```

Then replace `GCP_SERVICE_ACCOUNT_JSON` in `env.cloudrun.yaml` with the real service-account JSON.

Important app-protection variables:

```yaml
ARASENSE_BACKEND_SHARED_SECRET: "a-long-random-secret"
ARASENSE_APP_DISABLED: "false"
ARASENSE_APP_DISABLED_MESSAGE: "The current demo usage limit has been reached. The public website remains online."
```

When `ARASENSE_BACKEND_SHARED_SECRET` is set, direct requests to the Cloud Run URL are rejected unless they include:

```text
x-arasense-origin-secret: <same secret>
```

The Cloudflare Worker adds this header. Browsers do not need to know the secret.

If you need an emergency stop, set:

```yaml
ARASENSE_APP_DISABLED: "true"
```

## Cloudflare Worker

See `cloudflare-worker/README.md`.

Set these Worker variables in `wrangler.toml`:

```toml
ORIGIN_URL = "https://your-cloud-run-url"
APP_INVITE_CODE = "private-code-for-users"
APP_SESSION_TOKEN = "random-session-token"
ORIGIN_SHARED_SECRET = "same-value-as-ARASENSE_BACKEND_SHARED_SECRET"
MONTHLY_API_LIMIT = "100"
USAGE_KEY_PREFIX = "arasense-prod"
```

The Worker counts `/api/*` calls per UTC month. When the monthly limit is reached, it returns a limit message and does not forward the request to Cloud Run.

## Billing alerts

Create Google Cloud Billing alerts at:

- `$0.25`
- `$0.50`
- `$0.75`

Treat these as backup alerts. The Worker limit should stop normal demo usage first.

## Manual shutdown commands

Block public access to the Cloud Run service:

```bash
gcloud run services update arasense-api \
  --region us-central1 \
  --no-allow-unauthenticated
```

Delete the Cloud Run service:

```bash
gcloud run services delete arasense-api \
  --region us-central1
```

Keep `www.arasense.com` online even if the app is stopped.
