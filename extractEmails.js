/**
 * Two-stage email scraper.
 *
 *   Stage 1 — fast parallel HTTP fetch (no browser). Concurrency 20.
 *             Catches every site that exposes emails in static HTML (~70%+
 *             of small-business sites).
 *
 *   Stage 2 — Playwright fallback, concurrency 4. Only runs against the
 *             subset that came back empty from stage 1 (typically JS-heavy
 *             sites: Wix, Webflow, Framer, etc). Waits for networkidle so
 *             JS-rendered emails appear.
 *
 *   Both stages share the same email-extraction helpers (regex + HTML entity
 *   decode + Cloudflare data-cfemail XOR + JSON-LD + [at]/[dot] obfuscation).
 *
 *   stdin: JSON array of leads `[{ title, website, ... }, ...]`
 *   stdout: JSON array of leads with `emails: string[]` added.
 */
const { chromium } = require("playwright");

const EMAIL_REGEX = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g;
const OBFUSCATED_REGEX =
  /([a-zA-Z0-9._%+\-]+)\s*(?:\[at\]|\(at\)|\{at\}|\s+at\s+)\s*([a-zA-Z0-9.\-]+)\s*(?:\[dot\]|\(dot\)|\{dot\}|\s+dot\s+|\.)\s*([a-zA-Z]{2,})/gi;
const CF_DATA_RE = /data-cfemail=["']([0-9a-fA-F]+)["']/g;
const HREF_RE = /<a[^>]+href=["']([^"']+)["']/gi;
const MAILTO_RE = /mailto:([^"'?>\s]+)/gi;
const SUBPAGE_RE =
  /contact|about|support|help|team|staff|imprint|impressum|legal|privacy|kontakt|reach|connect/i;

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

const HTTP_CONCURRENCY = parseInt(process.env.HTTP_CONCURRENCY || "20", 10);
const PW_CONCURRENCY = parseInt(process.env.PW_CONCURRENCY || "4", 10);
const HTTP_TIMEOUT_MS = parseInt(process.env.HTTP_TIMEOUT_MS || "8000", 10);
const PW_TIMEOUT_MS = parseInt(process.env.PW_TIMEOUT_MS || "20000", 10);
const MAX_SUBPAGES = parseInt(process.env.MAX_SUBPAGES || "4", 10);

// ── helpers ────────────────────────────────────────────────────────────────

function decodeHtmlEntities(text) {
  if (!text) return "";
  return text
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n, 10)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCharCode(parseInt(n, 16)))
    .replace(/&amp;/g, "&")
    .replace(/&nbsp;/g, " ");
}

function decodeCfEmail(encoded) {
  if (!encoded || encoded.length < 4) return null;
  try {
    const r = parseInt(encoded.substr(0, 2), 16);
    let out = "";
    for (let n = 2; n < encoded.length; n += 2) {
      out += String.fromCharCode(parseInt(encoded.substr(n, 2), 16) ^ r);
    }
    return out.includes("@") ? out : null;
  } catch {
    return null;
  }
}

function extractFromHtml(html) {
  if (!html) return [];
  const out = new Set();
  const decoded = decodeHtmlEntities(html);

  // 1. Plain email regex
  const direct = decoded.match(EMAIL_REGEX);
  if (direct) direct.forEach((e) => out.add(e));

  // 2. Obfuscated "name [at] domain [dot] com"
  let m;
  OBFUSCATED_REGEX.lastIndex = 0;
  while ((m = OBFUSCATED_REGEX.exec(decoded)) !== null) {
    out.add(`${m[1]}@${m[2]}.${m[3]}`);
  }

  // 3. mailto:
  MAILTO_RE.lastIndex = 0;
  while ((m = MAILTO_RE.exec(html)) !== null) {
    try {
      out.add(decodeURIComponent(m[1]).split("?")[0]);
    } catch {
      out.add(m[1].split("?")[0]);
    }
  }

  // 4. Cloudflare data-cfemail XOR
  CF_DATA_RE.lastIndex = 0;
  while ((m = CF_DATA_RE.exec(html)) !== null) {
    const decoded = decodeCfEmail(m[1]);
    if (decoded) out.add(decoded);
  }

  // 5. JSON-LD <script type="application/ld+json">
  const jsonLdRe =
    /<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  while ((m = jsonLdRe.exec(html)) !== null) {
    try {
      const data = JSON.parse(m[1].trim());
      const stack = [data];
      while (stack.length) {
        const cur = stack.pop();
        if (cur == null) continue;
        if (typeof cur === "string") {
          const inner = cur.match(EMAIL_REGEX);
          if (inner) inner.forEach((e) => out.add(e));
        } else if (Array.isArray(cur)) {
          stack.push(...cur);
        } else if (typeof cur === "object") {
          for (const k of Object.keys(cur)) stack.push(cur[k]);
        }
      }
    } catch {}
  }

  return Array.from(out);
}

function normalizeUrl(url) {
  if (!url || typeof url !== "string") return null;
  let u = url.trim();
  if (!u) return null;
  if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
  try {
    return new URL(u).toString();
  } catch {
    return null;
  }
}

function findSubpages(html, baseUrl) {
  if (!html) return [];
  const out = new Set();
  let m;
  const origin = (() => {
    try {
      return new URL(baseUrl).origin;
    } catch {
      return null;
    }
  })();
  if (!origin) return [];

  HREF_RE.lastIndex = 0;
  while ((m = HREF_RE.exec(html)) !== null) {
    const href = m[1];
    if (!href || href.startsWith("#") || href.startsWith("mailto:")) continue;
    let absolute;
    try {
      absolute = new URL(href, baseUrl).toString();
    } catch {
      continue;
    }
    if (!absolute.startsWith(origin)) continue;
    if (!SUBPAGE_RE.test(absolute)) continue;
    out.add(absolute.split("#")[0]);
  }
  return Array.from(out).slice(0, MAX_SUBPAGES);
}

async function fetchText(url, timeoutMs = HTTP_TIMEOUT_MS) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      headers: {
        "User-Agent": UA,
        Accept: "text/html,application/xhtml+xml",
      },
      redirect: "follow",
      signal: ctrl.signal,
    });
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  } finally {
    clearTimeout(t);
  }
}

// ── stage 1: parallel HTTP ────────────────────────────────────────────────

async function httpScrape(rawUrl) {
  const url = normalizeUrl(rawUrl);
  if (!url) return [];

  const out = new Set();
  const home = await fetchText(url);
  if (!home) return [];
  extractFromHtml(home).forEach((e) => out.add(e));

  const subpages = findSubpages(home, url);
  await Promise.all(
    subpages.map(async (link) => {
      const html = await fetchText(link);
      if (!html) return;
      extractFromHtml(html).forEach((e) => out.add(e));
    })
  );

  return Array.from(out);
}

// ── stage 2: Playwright fallback ──────────────────────────────────────────

async function playwrightScrape(context, rawUrl) {
  const url = normalizeUrl(rawUrl);
  if (!url) return [];
  const page = await context.newPage();
  const out = new Set();

  async function scan() {
    try {
      // Try to let JS-rendered content settle, but don't block forever
      await page
        .waitForLoadState("networkidle", { timeout: 5000 })
        .catch(() => {});
    } catch {}

    try {
      const mailtos = await page.$$eval("a[href^='mailto:']", (links) =>
        links.map((a) => a.href.replace(/^mailto:/i, "").split("?")[0])
      );
      mailtos.forEach((e) => out.add(decodeURIComponent(e)));
    } catch {}

    try {
      const html = await page.content();
      extractFromHtml(html).forEach((e) => out.add(e));
    } catch {}

    try {
      // Pull innerText too — covers cases where the email is JS-injected
      // text not in the rendered HTML source.
      const text = await page.evaluate(() => document.body?.innerText || "");
      extractFromHtml(text).forEach((e) => out.add(e));
    } catch {}
  }

  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: PW_TIMEOUT_MS });
    await scan();

    const html = await page.content().catch(() => "");
    const subpages = findSubpages(html, url);

    for (const link of subpages.slice(0, 3)) {
      try {
        await page.goto(link, {
          waitUntil: "domcontentloaded",
          timeout: 12000,
        });
        await scan();
      } catch {}
    }
  } catch (err) {
    console.error(`PW failed: ${url} — ${err.message}`);
  } finally {
    await page.close().catch(() => {});
  }

  return Array.from(out);
}

// ── concurrency primitive ─────────────────────────────────────────────────

async function parallelMap(items, concurrency, fn) {
  const results = new Array(items.length);
  let idx = 0;
  async function worker() {
    while (true) {
      const i = idx++;
      if (i >= items.length) return;
      try {
        results[i] = await fn(items[i], i);
      } catch (err) {
        results[i] = err;
      }
    }
  }
  await Promise.all(
    Array(Math.min(concurrency, items.length)).fill(0).map(worker)
  );
  return results;
}

// ── stdin/stdout ──────────────────────────────────────────────────────────

async function readStdinJson() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

(async () => {
  const input = await readStdinJson();
  if (!Array.isArray(input)) {
    console.error("stdin must be a JSON array of leads");
    process.exit(1);
  }

  // ── Stage 1: parallel HTTP ────────────────────────────────────────────
  console.error(
    `[stage1] HTTP scrape ${input.length} leads (concurrency=${HTTP_CONCURRENCY})`
  );
  const t1 = Date.now();
  const stage1 = await parallelMap(input, HTTP_CONCURRENCY, async (biz) => {
    if (!biz.website) return { ...biz, emails: [] };
    const emails = await httpScrape(biz.website);
    return { ...biz, emails };
  });
  console.error(
    `[stage1] done in ${((Date.now() - t1) / 1000).toFixed(1)}s — ` +
      `${stage1.filter((r) => r.emails.length > 0).length}/${input.length} hit`
  );

  // ── Stage 2: Playwright for empty results ─────────────────────────────
  const needPw = stage1.filter((r) => r.website && r.emails.length === 0);
  if (needPw.length > 0) {
    console.error(
      `[stage2] Playwright fallback for ${needPw.length} leads ` +
        `(concurrency=${PW_CONCURRENCY})`
    );
    const t2 = Date.now();
    const browser = await chromium.launch({ headless: true });
    try {
      const contexts = await Promise.all(
        Array(PW_CONCURRENCY)
          .fill(0)
          .map(() => browser.newContext({ userAgent: UA }))
      );
      let cIdx = 0;
      const pwResults = await parallelMap(needPw, PW_CONCURRENCY, async (biz) => {
        const ctx = contexts[cIdx++ % contexts.length];
        const emails = await playwrightScrape(ctx, biz.website);
        return { website: biz.website, emails };
      });
      await Promise.all(contexts.map((c) => c.close().catch(() => {})));
      const byWebsite = new Map(
        pwResults.filter(Boolean).map((r) => [r.website, r.emails])
      );
      for (const lead of stage1) {
        if (lead.emails.length === 0 && byWebsite.has(lead.website)) {
          lead.emails = byWebsite.get(lead.website);
        }
      }
      console.error(
        `[stage2] done in ${((Date.now() - t2) / 1000).toFixed(1)}s — ` +
          `${pwResults.filter((r) => r && r.emails.length > 0).length}/${needPw.length} hit`
      );
    } finally {
      await browser.close().catch(() => {});
    }
  }

  process.stdout.write(JSON.stringify(stage1));
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
