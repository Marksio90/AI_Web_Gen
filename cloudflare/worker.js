/**
 * Cloudflare Worker — Reverse proxy for demo sites stored in R2.
 *
 * Routing:
 *   {slug}.demo.yourplatform.pl  →  R2 bucket: demo-sites/{slug}/index.html (etc.)
 *
 * Deploy:
 *   npx wrangler deploy
 *
 * Required bindings (wrangler.toml):
 *   [[r2_buckets]]
 *   binding = "DEMO_SITES"
 *   bucket_name = "demo-sites"
 */

const DEMO_SUBDOMAIN = "demo";

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css":  "text/css",
  ".js":   "application/javascript",
  ".json": "application/json",
  ".png":  "image/png",
  ".jpg":  "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif":  "image/gif",
  ".svg":  "image/svg+xml",
  ".ico":  "image/x-icon",
  ".woff2": "font/woff2",
  ".woff":  "font/woff",
  ".ttf":   "font/ttf",
  ".xml":   "application/xml",
  ".txt":   "text/plain",
};

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

export default {
  async fetch(request, env) {
    const PLATFORM_DOMAIN = env.PLATFORM_DOMAIN || "yourplatform.pl";
    const url = new URL(request.url);
    const hostname = url.hostname;

    // Extract slug from subdomain: {slug}.demo.yourplatform.pl
    const domainSuffix = `.${DEMO_SUBDOMAIN}.${PLATFORM_DOMAIN}`;
    if (!hostname.endsWith(domainSuffix)) {
      return new Response("Not found", { status: 404 });
    }

    const slug = hostname.slice(0, -domainSuffix.length);
    if (!slug || slug.includes(".")) {
      return new Response("Invalid subdomain", { status: 400 });
    }

    // Determine file path within R2
    let pathname = url.pathname;
    if (pathname === "/" || pathname === "") {
      pathname = "/index.html";
    }
    // Append index.html for directory-style paths
    if (!pathname.includes(".") || pathname.endsWith("/")) {
      pathname = pathname.replace(/\/$/, "") + "/index.html";
    }

    const r2Key = `${slug}${pathname}`;

    // Fetch from R2
    const object = await env.DEMO_SITES.get(r2Key);

    if (!object) {
      // Try index.html fallback for SPA-style routing
      const fallback = await env.DEMO_SITES.get(`${slug}/index.html`);
      if (!fallback) {
        return new Response(demoNotFoundPage(escapeHtml(slug), PLATFORM_DOMAIN), {
          status: 404,
          headers: { "Content-Type": "text/html; charset=utf-8" },
        });
      }
      return serveObject(fallback, ".html");
    }

    return serveObject(object, pathname);
  },
};

function serveObject(object, pathname) {
  const ext = "." + pathname.split(".").pop().toLowerCase();
  const contentType = MIME_TYPES[ext] || "application/octet-stream";

  const headers = new Headers();
  headers.set("Content-Type", contentType);
  headers.set("Cache-Control", "public, max-age=3600");
  headers.set("X-Robots-Tag", "noindex, nofollow");

  // Security headers
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.set("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data: https:; script-src 'self'");
  headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");

  if (object.httpMetadata?.contentType) {
    headers.set("Content-Type", object.httpMetadata.contentType);
  }

  return new Response(object.body, { headers });
}

function demoNotFoundPage(slug, platformDomain) {
  return `<!doctype html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Strona demo \u2013 w przygotowaniu</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #f8fafc; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
    .card { background: white; border-radius: 16px; padding: 48px; text-align: center; max-width: 480px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }
    h1 { color: #1e293b; font-size: 1.5rem; margin-bottom: 12px; }
    p { color: #64748b; line-height: 1.6; }
    a { color: #6366f1; text-decoration: none; font-weight: 600; }
    .slug { font-family: monospace; background: #f1f5f9; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }
  </style>
</head>
<body>
  <div class="card">
    <p style="font-size:2.5rem;margin-bottom:16px">\u26A1</p>
    <h1>Strona demo jest przygotowywana</h1>
    <p>Demo dla <span class="slug">${slug}</span> jest w\u0142a\u015Bnie generowane przez AI.<br>Spr\u00F3buj ponownie za chwil\u0119.</p>
    <p style="margin-top:24px">
      <a href="https://${platformDomain}">Dowiedz si\u0119 wi\u0119cej o platformie \u2192</a>
    </p>
  </div>
</body>
</html>`;
}
