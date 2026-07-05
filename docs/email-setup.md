# aras@arasense.com setup (10 minutes, two dashboards)

DNS discovery (2026-07-05): arasense.com already has Namecheap email
forwarding live (MX -> eforward*.registrar-servers.com, SPF includes
spf.efwd.registrar-servers.com). So no migration is needed; the address
is a forwarding rule away.

## Step 1 - receive mail (Namecheap, ~2 min)

1. namecheap.com -> Domain List -> arasense.com -> Manage.
2. "Redirect Email" (a.k.a. Email Forwarding).
3. Add: alias `aras` -> forward to `arasbotan.izzaddin@gmail.com`.
   Optionally add `hello` and a catch-all to the same inbox.
4. Send a test mail to aras@arasense.com and confirm it lands in Gmail.

## Step 2 - send as aras@arasense.com from Gmail (~5 min)

1. Gmail -> Settings -> Accounts and Import -> "Send mail as" -> Add.
2. Name: Aras Izzaddin · Email: aras@arasense.com · untick "treat as alias" is
   NOT needed; leave it ticked.
3. SMTP server: smtp.gmail.com · port 587 · username: arasbotan.izzaddin@gmail.com
   · password: a Gmail App Password (Google Account -> Security -> 2-Step ->
   App passwords).
4. Gmail sends a verification code to aras@arasense.com; it arrives in the
   same inbox via Step 1. Confirm.
5. Optionally set aras@arasense.com as the default "From".

## Step 3 - tell the site (1 command, done by Claude on request)

Once a test send and a test receive both work, say the word and the visible
contact address across www.arasense.com (footers, briefing page, lead-form
messages, JSON-LD) switches from arasbotan.izzaddin@poliba.it to
aras@arasense.com in one commit.

## Later (when outbound volume grows)

Gmail send-as delivers fine for one-to-one founder mail, but bulk or
cold outreach deserves real DKIM alignment: move to Zoho Mail (free tier)
or Google Workspace on the domain, which replaces Step 1-2 and adds
DKIM/DMARC records at Namecheap. Not needed for the first pilots.

## Where briefing requests land

The /briefing page stores structured requests (name, org, topic, preferred
windows) in the LEADS KV namespace. Read them with:

    npx wrangler kv key list --namespace-id <ID> --prefix lead: | ConvertFrom-Json | ForEach-Object name
    npx wrangler kv key get "<key>" --namespace-id <ID>

The namespace is `arasense-leads`, ID `f263b2f4939543a9ada03bc2db1db395`
(bound to the Pages project as LEADS on 2026-07-05; funnel verified end to end).
