# Cavelle Enquiries Worker

Independent Cloudflare Worker that receives Cavellyachts enquiry-form
submissions and appends them to the **Website Orders** spreadsheet,
tab **Cavellyachts** — in parallel with Formspree (both paths are
independent; the site sends to both with the same `CVL-` reference).

- Endpoint: `POST /orders` (JSON)
- Runtime secret: `GOOGLE_SERVICE_ACCOUNT_JSON` (same Google service account
  as the Veloria worker — set it in Cloudflare dashboard/CLI, never in the repo)
- Vars: `SHEET_NAME=Website Orders`, `TAB_NAME=Cavellyachts`, `ALLOWED_ORIGIN=*`

Payload fields: `order_id`, `source`, `lang`, `full_name`, `email`, `phone`,
`country`, `budget`/`budget_range`, `looking_for`, `preferred_length`,
`purchase_timeline`, `description`, `message`, honeypot `website` (must be empty).

Validation: name required, plus a valid email OR phone. A client-supplied
reference is accepted only in `CVL-YYYYMMDD-XXXXX` format; otherwise the
worker generates one.

## Deploy

```bash
cd worker
npx wrangler secret put GOOGLE_SERVICE_ACCOUNT_JSON   # paste the key JSON once
npx wrangler deploy
```

The worker auto-creates the tab and header row if missing, and finds the
spreadsheet by name via the Drive API.
