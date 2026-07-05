/*
  Cloudflare Pages advanced-mode worker for www.arasense.com.

  Handles POST /api/lead (trust-brief request forms) and passes every other
  request straight to the static assets. Leads are stored in the KV namespace
  bound as LEADS — if the binding is missing, the endpoint returns 503 and the
  form falls back to a mailto link, so the site never breaks.
*/

const MAX_BODY = 4096;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function handleLead(request, env) {
  const raw = await request.text();
  if (raw.length > MAX_BODY) return json({ ok: false }, 413);

  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ ok: false }, 400);
  }

  /* honeypot filled → pretend success, store nothing */
  if (body.website) return json({ ok: true });

  const email = String(body.email || "").trim().slice(0, 200);
  if (!EMAIL_RE.test(email)) return json({ ok: false, error: "invalid email" }, 400);

  if (!env.LEADS) return json({ ok: false, error: "lead storage not configured" }, 503);

  const lead = {
    email,
    org: String(body.org || "").slice(0, 200),
    city: String(body.city || "").slice(0, 80),
    page: String(body.page || "").slice(0, 200),
    name: String(body.name || "").slice(0, 120),
    msg: String(body.msg || "").slice(0, 1000),
    slots: String(body.slots || "").slice(0, 300),
    country: (request.cf && request.cf.country) || "",
    ts: new Date().toISOString(),
  };
  const key = `lead:${lead.ts}:${crypto.randomUUID().slice(0, 8)}`;
  await env.LEADS.put(key, JSON.stringify(lead));
  return json({ ok: true });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/api/lead") {
      if (request.method !== "POST") return json({ ok: false, error: "POST only" }, 405);
      return handleLead(request, env);
    }
    return env.ASSETS.fetch(request);
  },
};
