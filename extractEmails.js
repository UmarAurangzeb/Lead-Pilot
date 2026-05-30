const { chromium } = require("playwright");

const EMAIL_REGEX = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g;

// Matches obfuscated patterns like "name [at] domain [dot] com", "name (at) domain dot com"
const OBFUSCATED_REGEX =
  /([a-zA-Z0-9._%+\-]+)\s*(?:\[at\]|\(at\)|\{at\}|\s+at\s+|@)\s*([a-zA-Z0-9.\-]+)\s*(?:\[dot\]|\(dot\)|\{dot\}|\s+dot\s+|\.)\s*([a-zA-Z]{2,})/gi;

function decodeHtmlEntities(text) {
  if (!text) return "";
  return text
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n, 10)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCharCode(parseInt(n, 16)))
    .replace(/&amp;/g, "&")
    .replace(/&nbsp;/g, " ");
}

function extractEmailsFromText(text) {
  if (!text || typeof text !== "string") return [];
  const decoded = decodeHtmlEntities(text);
  const found = new Set();

  const direct = decoded.match(EMAIL_REGEX);
  if (direct) direct.forEach((e) => found.add(e));

  let m;
  OBFUSCATED_REGEX.lastIndex = 0;
  while ((m = OBFUSCATED_REGEX.exec(decoded)) !== null) {
    found.add(`${m[1]}@${m[2]}.${m[3]}`);
  }

  return Array.from(found);
}

/** Decode Cloudflare's data-cfemail XOR-obfuscated email. */
function decodeCfEmail(encoded) {
  if (!encoded || encoded.length < 2) return null;
  try {
    const r = parseInt(encoded.substr(0, 2), 16);
    let decoded = "";
    for (let n = 2; n < encoded.length; n += 2) {
      decoded += String.fromCharCode(parseInt(encoded.substr(n, 2), 16) ^ r);
    }
    return decoded;
  } catch {
    return null;
  }
}

/** Runs in browser: pull visible text, attributes, Cloudflare emails, JSON-LD. */
function harvestEmailsFromDom() {
  const blobs = [];
  const cfEmails = [];
  const jsonLdEmails = [];

  if (document.body) {
    blobs.push(document.body.innerText || "");
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      null
    );
    let node;
    while ((node = walker.nextNode())) {
      const v = node.nodeValue || "";
      if (v.includes("@") || /\[at\]|\(at\)|\s+at\s+/i.test(v)) blobs.push(v);
    }
  }

  document.querySelectorAll("*").forEach((el) => {
    const attrs = el.attributes;
    if (!attrs) return;
    for (let i = 0; i < attrs.length; i++) {
      const name = attrs[i].name;
      const val = attrs[i].value;
      if (!val) continue;
      if (name === "data-cfemail") {
        cfEmails.push(val);
      } else if (val.includes("@")) {
        blobs.push(val);
      }
    }
  });

  document
    .querySelectorAll('script[type="application/ld+json"]')
    .forEach((s) => {
      try {
        const data = JSON.parse(s.textContent || "{}");
        const stack = [data];
        while (stack.length) {
          const cur = stack.pop();
          if (!cur) continue;
          if (typeof cur === "string") {
            if (cur.includes("@")) jsonLdEmails.push(cur.replace(/^mailto:/, ""));
            continue;
          }
          if (Array.isArray(cur)) {
            stack.push(...cur);
            continue;
          }
          if (typeof cur === "object") {
            for (const k of Object.keys(cur)) stack.push(cur[k]);
          }
        }
      } catch {}
    });

  return { text: blobs.join("\n"), cfEmails, jsonLdEmails };
}

function normalizeUrl(url) {
  if (!url || typeof url !== "string") return null;
  let u = url.trim();
  if (!u) return null;
  if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
  return u;
}

const SUBPAGE_REGEX =
  /contact|about|support|help|team|staff|imprint|impressum|legal|privacy|kontakt|reach|connect/i;

async function scrapeEmail(page, url) {
  const normalized = normalizeUrl(url);
  if (!normalized) return [];

  const visited = new Set();
  const emails = new Set();

  function addFromText(text) {
    extractEmailsFromText(text).forEach((e) => emails.add(e));
  }

  try {
    await page.goto(normalized, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });
    visited.add(normalized);

    async function extract() {
      try {
        const mailtos = await page.$$eval("a[href^='mailto:']", (links) =>
          links.map((a) => a.href.replace(/^mailto:/i, "").split("?")[0])
        );
        mailtos.forEach((e) => emails.add(decodeURIComponent(e)));
      } catch {}

      try {
        const harvest = await page.evaluate(harvestEmailsFromDom);
        addFromText(harvest.text);
        harvest.cfEmails.forEach((enc) => {
          const decoded = decodeCfEmail(enc);
          if (decoded) emails.add(decoded);
        });
        harvest.jsonLdEmails.forEach((e) => addFromText(e));
      } catch {}

      try {
        const html = await page.content();
        addFromText(html);
      } catch {}
    }

    await extract();

    let links = [];
    try {
      links = await page.$$eval("a[href]", (anchors) =>
        anchors.map((a) => a.href).filter(Boolean)
      );
    } catch {}

    const origin = new URL(normalized).origin;
    const internalLinks = Array.from(
      new Set(
        links
          .filter((link) => {
            try {
              return new URL(link).origin === origin;
            } catch {
              return false;
            }
          })
          .filter((link) => SUBPAGE_REGEX.test(link))
      )
    ).slice(0, 10);

    for (const link of internalLinks) {
      if (visited.has(link)) continue;
      try {
        await page.goto(link, {
          waitUntil: "domcontentloaded",
          timeout: 15000,
        });
        visited.add(link);
        await extract();
      } catch (err) {
        console.error(`Failed subpage: ${link}`);
      }
    }

    return Array.from(emails);
  } catch (err) {
    console.error(`Failed: ${normalized}`, err.message);
    return [];
  }
}

async function readStdinJson() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  return JSON.parse(raw);
}

(async () => {
  const input = await readStdinJson();
  if (!Array.isArray(input)) {
    console.error("stdin must be a JSON array of leads");
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  });
  const page = await context.newPage();

  const results = [];

  for (const biz of input) {
    if (!biz.website) {
      results.push({ ...biz, emails: [] });
      continue;
    }

    console.error(`Scraping: ${biz.title || biz.website}`);

    const emails = await scrapeEmail(page, biz.website);

    results.push({
      ...biz,
      emails,
    });
  }

  await browser.close();

  process.stdout.write(JSON.stringify(results));
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
