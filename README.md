# CavelleYachts — Luxury Yacht Brokerage

Static website deployed to Cloudflare Pages via GitHub Actions.

## Structure

- `public/` — All website files (deploy root)
- `.github/workflows/deploy.yml` — GitHub Actions workflow for Cloudflare Pages deployment

## Deployment

Pushes to `main` automatically deploy to the existing Cloudflare Pages project `cavelleyachts` via GitHub Actions + Wrangler.

No build step — pure static HTML/CSS/JS.

## Theme

Dark navy (`#0a0c12`) + gold (`#c5a982`)

## Analytics

Microsoft Clarity — ID: `y2wvdni7jt`

## Secrets (GitHub Actions)

- `CLOUDFLARE_API_TOKEN` — Cloudflare API token
- `CLOUDFLARE_ACCOUNT_ID` — Cloudflare account ID
