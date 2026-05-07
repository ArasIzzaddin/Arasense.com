# Static Site Deployment

This folder contains a static landing page version of Arasense for publishing `www.arasense.com` without running the FastAPI backend.

## Why this version exists

- No GCP billing setup required to get the domain live.
- Good enough for client outreach, demos, and credibility.
- Keeps a clean migration path to `Firebase Hosting + Cloud Run` later.

## Recommended host

Use `Cloudflare Pages` for now.

## What to upload

Upload the contents of this `site/` folder:

- `index.html`
- `favicon.svg`
- `README.md` is only for you and does not need to be deployed

## Cloudflare Pages steps

1. Create a Cloudflare account.
2. Open `Workers & Pages`.
3. Create a new `Pages` project.
4. Choose `Upload assets`.
5. Upload the files from this `site/` folder.
6. After deploy, attach the custom domain `www.arasense.com`.
7. In your domain DNS, point `www` to the target Cloudflare gives you.
8. Add a redirect from `arasense.com` to `https://www.arasense.com`.

## Later migration to GCP

When you want the real backend live:

1. Deploy the FastAPI app from the repo root to `Cloud Run`.
2. Put `Firebase Hosting` in front of it.
3. Move `www.arasense.com` from the static site to Firebase Hosting.
4. Keep the same domain; only the hosting target changes.

## Current limitations

- No FastAPI endpoints
- No Python backend
- No Earth Engine features
- No live flood or climate analysis

This is a presentation site only.
