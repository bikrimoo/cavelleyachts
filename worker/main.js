/**
 * Cavelle Yachts Enquiries API — Cloudflare Worker
 *
 * Independent backend for the Cavellyachts enquiry forms. Receives
 * submissions in parallel with Formspree and appends them to the Google
 * Sheet "Website Orders" (tab "Cavellyachts") using the same Google
 * service account as the Veloria worker.
 *
 * No platform dependency: plain Cloudflare Workers + Google Sheets API v4.
 * Deploy with `npx wrangler deploy` from this folder, or via the Cloudflare
 * API. Mirrors worker/ of the Veloria project (kept intentionally separate).
 *
 * Environment / secrets (see worker/README.md):
 *   GOOGLE_SERVICE_ACCOUNT_JSON  (secret)   Full JSON key of the Google service account
 *   ALLOWED_ORIGIN               (optional) Restrict CORS, e.g. "https://cavelleyachts.com"
 *   SHEET_NAME / TAB_NAME        (vars)     Spreadsheet and tab name.
 *                                           Default: Website Orders / Cavellyachts.
 */

const SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets";
const DRIVE_API = "https://www.googleapis.com/drive/v3";
const TOKEN_URL = "https://oauth2.googleapis.com/token";
const SCOPES =
  "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive.metadata.readonly";

const HEADERS = [
  "Date",
  "Reference",
  "Source",
  "Language",
  "Full Name",
  "Email",
  "Phone",
  "Country",
  "Budget",
  "Looking For",
  "Preferred Length",
  "Purchase Timeline",
  "Description",
  "Message",
  "Status",
];

// ---------------------------------------------------------------- utilities

const enc = new TextEncoder();

function toBase64Url(bytes) {
  const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = "";
  for (const b of view) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlDecode(input) {
  const b64 = input.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((input.length + 3) % 4);
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

/** Build a Google OAuth2 access token from the service account key. */
let cachedToken = null;

async function getGoogleToken(env) {
  if (cachedToken && cachedToken.expiresAt > Date.now() + 60_000) return cachedToken.token;

  const sa = JSON.parse(env.GOOGLE_SERVICE_ACCOUNT_JSON);
  const now = Math.floor(Date.now() / 1000);
  const header = toBase64Url(enc.encode(JSON.stringify({ alg: "RS256", typ: "JWT" })));
  const claims = toBase64Url(
    enc.encode(
      JSON.stringify({
        iss: sa.client_email,
        scope: SCOPES,
        aud: TOKEN_URL,
        iat: now,
        exp: now + 3600,
      }),
    ),
  );

  const key = await crypto.subtle.importKey(
    "pkcs8",
    base64UrlDecode(sa.private_key.replace(/-----[^-]+-----/g, "").replace(/\s+/g, "")),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    enc.encode(`${header}.${claims}`),
  );

  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion: `${header}.${claims}.${toBase64Url(signature)}`,
    }),
  });
  if (!res.ok) throw new Error(`Google token exchange failed: ${res.status} ${await res.text()}`);

  const data = await res.json();
  cachedToken = { token: data.access_token, expiresAt: Date.now() + data.expires_in * 1000 };
  return cachedToken.token;
}

// ------------------------------------------------------------ sheet plumbing

/** Find the spreadsheet ID: explicit var > search Drive by name > create it. */
async function resolveSpreadsheetId(env, token) {
  const sheetName = env.SHEET_NAME || "Website Orders";
  const q = encodeURIComponent(
    `name = '${sheetName.replace(/'/g, "\\'")}' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false`,
  );
  const search = await fetch(`${DRIVE_API}/files?q=${q}&pageSize=1&orderBy=modifiedTime desc`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (search.ok) {
    const files = (await search.json()).files;
    if (files && files.length > 0) return files[0].id;
  }

  const tabName = env.TAB_NAME || "Cavellyachts";
  const created = await fetch(SHEETS_API, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      properties: { title: sheetName },
      sheets: [{ properties: { title: tabName } }],
    }),
  });
  if (!created.ok)
    throw new Error(`Could not find or create the sheet: ${created.status} ${await created.text()}`);
  const sheet = await created.json();
  return sheet.spreadsheetId;
}

/** Make sure the tab and its header row exist, return the tab name. */
async function ensureTabAndHeader(spreadsheetId, env, token) {
  const tabName = env.TAB_NAME || "Cavellyachts";

  const meta = await fetch(`${SHEETS_API}/${spreadsheetId}?fields=sheets.properties.title`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!meta.ok) throw new Error(`Sheet metadata failed: ${meta.status}`);
  const tabs = (await meta.json()).sheets.map((s) => s.properties.title);

  if (!tabs.includes(tabName)) {
    await fetch(`${SHEETS_API}/${spreadsheetId}:batchUpdate`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ requests: [{ addSheet: { properties: { title: tabName } } }] }),
    });
  }

  // Ensure header row (only writes when A1 is empty).
  const firstCell = await fetch(
    `${SHEETS_API}/${spreadsheetId}/values/${encodeURIComponent(tabName)}!A1`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (firstCell.ok) {
    const values = (await firstCell.json()).values;
    if (!values || values.length === 0) {
      await fetch(
        `${SHEETS_API}/${spreadsheetId}/values/${encodeURIComponent(tabName)}!A1?valueInputOption=RAW`,
        {
          method: "PUT",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify({ values: [HEADERS] }),
        },
      );
    }
  }

  return tabName;
}

async function appendEnquiry(spreadsheetId, tabName, row, token) {
  const range = encodeURIComponent(`${tabName}!A:O`);
  const res = await fetch(
    `${SHEETS_API}/${spreadsheetId}/values/${range}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ values: [row] }),
    },
  );
  if (!res.ok) throw new Error(`Sheets append failed: ${res.status} ${await res.text()}`);
}

// ---------------------------------------------------------------- validation

function sanitize(value, maxLen) {
  if (typeof value !== "string") return "";
  return value.trim().slice(0, maxLen);
}

function validate(body) {
  if (typeof body !== "object" || body === null) return { ok: false, error: "Invalid payload" };
  const b = body;

  // Honeypot: real users never fill this hidden field.
  if (sanitize(b.website, 200) !== "") return { ok: false, error: "Spam detected" };

  const fullName = sanitize(b.full_name, 120);
  const email = sanitize(b.email, 150);
  const phoneRaw = sanitize(b.phone, 30);
  const source = sanitize(b.source, 80) || "website";
  const lang = b.lang === "ar" ? "ar" : "en";
  const country = sanitize(b.country, 80);
  const budget = sanitize(b.budget || b.budget_range, 100);
  const lookingFor = sanitize(b.looking_for, 200);
  const preferredLength = sanitize(b.preferred_length, 100);
  const timeline = sanitize(b.purchase_timeline, 100);
  const description = sanitize(b.description, 500);
  const message = sanitize(b.message, 1000);
  const reference = sanitize(b.order_id, 30);

  if (fullName.length < 2) return { ok: false, error: "Missing name" };
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email);
  const phoneOk = /^[+0-9 ()\-.]{6,20}$/.test(phoneRaw);
  if (!emailOk && !phoneOk) return { ok: false, error: "Missing email or phone" };

  // Accept a client-provided reference only if it matches our format.
  const safeRef = /^CVL-\d{8}-[A-Z0-9]{4,6}$/.test(reference) ? reference : "";

  return {
    ok: true,
    enquiry: {
      order_id: safeRef,
      source,
      lang,
      full_name: fullName,
      email,
      phone: phoneRaw,
      country,
      budget,
      looking_for: lookingFor,
      preferred_length: preferredLength,
      purchase_timeline: timeline,
      description,
      message,
    },
  };
}

function makeReference() {
  const d = new Date();
  const date = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
  const rand = Math.random().toString(36).slice(2, 7).toUpperCase();
  return `CVL-${date}-${rand}`;
}

// ------------------------------------------------------------------- worker

export default {
  async fetch(request, env) {
    const origin = env.ALLOWED_ORIGIN || "*";
    const cors = {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
      ...(origin !== "*" ? { Vary: "Origin" } : {}),
    };

    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (request.method !== "POST") {
      return new Response(JSON.stringify({ ok: false, error: "Method not allowed" }), {
        status: 405,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    const url = new URL(request.url);
    if (url.pathname !== "/orders") {
      return new Response(JSON.stringify({ ok: false, error: "Not found" }), {
        status: 404,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response(JSON.stringify({ ok: false, error: "Invalid JSON" }), {
        status: 400,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    const parsed = validate(body);
    if (!parsed.ok) {
      return new Response(JSON.stringify({ ok: false, error: parsed.error }), {
        status: 400,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    if (!env.GOOGLE_SERVICE_ACCOUNT_JSON) {
      return new Response(
        JSON.stringify({ ok: false, error: "Server not configured: missing Google credentials" }),
        { status: 500, headers: { ...cors, "Content-Type": "application/json" } },
      );
    }

    const enquiry = parsed.enquiry;
    const orderId = enquiry.order_id || makeReference();

    try {
      const token = await getGoogleToken(env);
      const spreadsheetId = await resolveSpreadsheetId(env, token);
      const tabName = await ensureTabAndHeader(spreadsheetId, env, token);
      const timestamp = new Date().toLocaleString("fr-FR", { timeZone: "Africa/Casablanca" });
      await appendEnquiry(
        spreadsheetId,
        tabName,
        [
          timestamp,
          orderId,
          enquiry.source,
          enquiry.lang,
          enquiry.full_name,
          enquiry.email,
          enquiry.phone,
          enquiry.country,
          enquiry.budget,
          enquiry.looking_for,
          enquiry.preferred_length,
          enquiry.purchase_timeline,
          enquiry.description,
          enquiry.message,
          "new",
        ],
        token,
      );
      return new Response(JSON.stringify({ ok: true, orderId }), {
        headers: { ...cors, "Content-Type": "application/json" },
      });
    } catch (err) {
      console.error("Enquiry pipeline failed:", err);
      return new Response(JSON.stringify({ ok: false, error: "Could not save the enquiry" }), {
        status: 502,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }
  },
};
