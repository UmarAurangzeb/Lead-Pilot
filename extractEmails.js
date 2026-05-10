const { chromium } = require("playwright");

const EMAIL_REGEX = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}/g;

function extractEmailsFromText(text) {
  if (!text || typeof text !== "string") return [];
  const matches = text.match(EMAIL_REGEX);
  return matches || [];
}

/** Runs in browser: visible text, text nodes containing "@", and any attribute value containing "@". */
function harvestEmailsFromDom() {
  const blobs = [];

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
      if (v.includes("@")) blobs.push(v);
    }
  }

  document.querySelectorAll("*").forEach((el) => {
    const attrs = el.attributes;
    if (!attrs) return;
    for (let i = 0; i < attrs.length; i++) {
      const val = attrs[i].value;
      if (val && val.includes("@")) blobs.push(val);
    }
  });

  return blobs.join("\n");
}

function normalizeUrl(url) {
  if (!url || typeof url !== "string") return null;
  let u = url.trim();
  if (!u) return null;
  if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
  return u;
}

async function scrapeEmail(page, url) {
  const normalized = normalizeUrl(url);
  if (!normalized) return [];

  const visited = new Set();
  const emails = new Set();

  function addFromText(text) {
    extractEmailsFromText(text).forEach((e) => emails.add(e));
  }

  try {
    await page.goto(normalized, { waitUntil: "domcontentloaded", timeout: 30000 });
    visited.add(normalized);

    async function extract() {
      const mailtos = await page.$$eval("a[href^='mailto:']", (links) =>
        links.map((a) => a.href.replace("mailto:", "").split("?")[0])
      );
      mailtos.forEach((e) => emails.add(e));

      const domBlob = await page.evaluate(harvestEmailsFromDom);
      addFromText(domBlob);

      const html = await page.content();
      addFromText(html);
    }
    await extract();

    const links = await page.$$eval("a[href]", (anchors) =>
      anchors.map((a) => a.href)
    );

    const internalLinks = links
      .filter((link) => link.startsWith(normalized))
      .filter((link) => /contact|about|support|help/i.test(link))
      .slice(0, 5);

    for (const link of internalLinks) {
      if (visited.has(link)) continue;

      try {
        await page.goto(link, { waitUntil: "domcontentloaded", timeout: 15000 });
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
  const page = await browser.newPage();

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
