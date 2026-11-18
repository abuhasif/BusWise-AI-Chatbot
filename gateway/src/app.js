import { randomBytes, randomUUID } from 'node:crypto';
import express from 'express';
import { rateLimit } from 'express-rate-limit';
import helmet from 'helmet';
import { createProxyMiddleware } from 'http-proxy-middleware';

const TOKEN_HEADER = 'x-buswise-token';
export const MIN_TOKEN_LENGTH = 32;
const REQUEST_ID = /^[A-Za-z0-9._-]{1,64}$/;
// Headers that would reveal upstream software versions.
const HIDDEN_UPSTREAM_HEADERS = ['server', 'x-powered-by'];

/**
 * Content-Security-Policy for one response. The nonce is shared with the web app
 * (vinext reads it from the request's CSP header, like Next.js) so only its own
 * inline bootstrap scripts can run.
 */
export function contentSecurityPolicy(nonce, { secure = false } = {}) {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}'`,
    // Leaflet positions map tiles with inline style attributes.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https://www.onemap.gov.sg",
    "font-src 'self'",
    "connect-src 'self'",
    "worker-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(secure ? ['upgrade-insecure-requests'] : []),
  ].join('; ');
}

/**
 * Buswise edge gateway.
 *
 *   /api/*   -> Python API (adds the shared API token; origin, method, size and rate checks)
 *   /healthz -> gateway liveness
 *   /readyz  -> gateway + upstream readiness
 *   anything else -> web app (vinext server), with a per-request CSP nonce
 */
export function createApp({
  apiUrl,
  webUrl,
  apiToken = '',
  rateLimitPerMinute = 60,
  chatRateLimitPerMinute = 20,
  globalRateLimitPerMinute = 300,
  allowedOrigins = [],
  trustProxy = false,
  maxBodyBytes = 16 * 1024,
  log = (entry) => console.log(JSON.stringify(entry)),
  fetchImpl = fetch,
}) {
  if (!apiUrl || !webUrl) throw new Error('apiUrl and webUrl are required');
  if (apiToken && apiToken.length < MIN_TOKEN_LENGTH) {
    throw new Error(`BUSWISE_API_TOKEN must be at least ${MIN_TOKEN_LENGTH} characters`);
  }
  const extraOrigins = new Set(allowedOrigins);

  const app = express();
  app.disable('x-powered-by');
  // Only trust X-Forwarded-* when a real proxy (Cloud Run, a load balancer) sits in front.
  // Otherwise a client could fake its IP and dodge the rate limits.
  app.set('trust proxy', trustProxy);

  app.use((req, res, next) => {
    const incoming = req.get('x-request-id');
    const id = incoming && REQUEST_ID.test(incoming) ? incoming : randomUUID();
    const started = process.hrtime.bigint();
    req.id = id;
    res.setHeader('x-request-id', id);
    res.on('finish', () => {
      log({
        level: 'info',
        msg: 'request',
        id,
        method: req.method,
        path: req.originalUrl.slice(0, 200),
        status: res.statusCode,
        ms: Number(process.hrtime.bigint() - started) / 1e6,
      });
    });
    next();
  });

  // Security headers. CSP is set per request below because it carries a nonce.
  app.use(
    helmet({
      contentSecurityPolicy: false,
      referrerPolicy: { policy: 'strict-origin-when-cross-origin' },
      frameguard: { action: 'deny' },
    }),
  );
  app.use((req, res, next) => {
    res.locals.cspNonce = randomBytes(16).toString('base64');
    res.setHeader('Content-Security-Policy', contentSecurityPolicy(res.locals.cspNonce, { secure: req.secure }));
    res.setHeader('Permissions-Policy', 'geolocation=(self), camera=(), microphone=(), payment=(), usb=()');
    next();
  });

  const tooMany = { error: 'Too many requests. Please wait a minute and try again.' };
  const limiter = (limit) =>
    rateLimit({ windowMs: 60_000, limit, standardHeaders: 'draft-8', legacyHeaders: false, message: tooMany });

  app.use(limiter(globalRateLimitPerMinute));

  app.get('/healthz', (_req, res) => {
    res.json({ status: 'ok', service: 'gateway' });
  });

  app.get('/readyz', async (_req, res) => {
    const check = async (url, headers = {}) => {
      try {
        const response = await fetchImpl(url, { headers, signal: AbortSignal.timeout(3000) });
        return response.ok ? 'ok' : `http ${response.status}`;
      } catch {
        return 'unreachable';
      }
    };
    const [api, web] = await Promise.all([
      check(new URL('/api/health', apiUrl), apiToken ? { [TOKEN_HEADER]: apiToken } : {}),
      check(new URL('/', webUrl)),
    ]);
    const ready = api === 'ok' && web === 'ok';
    res.status(ready ? 200 : 503).json({ status: ready ? 'ok' : 'degraded', api, web });
  });

  // --- API guard rails -------------------------------------------------------
  // CORS: same-origin only unless ALLOWED_ORIGINS lists extra origins. Native apps
  // send no Origin header and are unaffected.
  app.use('/api', (req, res, next) => {
    const origin = req.get('origin');
    const sameOrigin = !origin || origin === `${req.protocol}://${req.get('host')}`;
    if (!sameOrigin) {
      if (!extraOrigins.has(origin)) return res.status(403).json({ error: 'Cross-origin requests are not allowed' });
      res.setHeader('Access-Control-Allow-Origin', origin);
      res.setHeader('Vary', 'Origin');
    }
    if (req.method === 'OPTIONS') {
      if (!sameOrigin) {
        res.setHeader('Access-Control-Allow-Methods', 'GET, POST');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
        res.setHeader('Access-Control-Max-Age', '600');
      }
      return res.sendStatus(204);
    }
    if (req.method !== 'GET' && req.method !== 'POST') {
      res.setHeader('Allow', 'GET, POST');
      return res.status(405).json({ error: 'Method not allowed' });
    }
    if (req.method === 'POST') {
      if (!req.is('application/json')) return res.status(415).json({ error: 'Send JSON with Content-Type: application/json' });
      const length = Number(req.get('content-length'));
      if (!Number.isInteger(length) || length <= 0) return res.status(411).json({ error: 'Content-Length is required' });
      if (length > maxBodyBytes) return res.status(413).json({ error: 'Request too large' });
    }
    res.setHeader('Cache-Control', 'no-store');
    next();
  });
  app.use('/api', limiter(rateLimitPerMinute));
  // The chat endpoint can call the language model, so it gets a tighter budget.
  app.use('/api/chat', limiter(chatRateLimitPerMinute));

  const onError = (err, req, res) => {
    log({ level: 'error', msg: 'upstream error', id: req.id, path: req.originalUrl, error: err.message });
    if (res.headersSent || typeof res.status !== 'function') {
      res.end?.();
      return;
    }
    res.status(502).json({ error: 'Upstream service unavailable' });
  };
  const hideUpstreamHeaders = (proxyRes) => {
    for (const name of HIDDEN_UPSTREAM_HEADERS) delete proxyRes.headers[name];
    // CORS is decided here, never by an upstream.
    delete proxyRes.headers['access-control-allow-origin'];
  };

  app.use(
    createProxyMiddleware({
      target: apiUrl,
      changeOrigin: true,
      pathFilter: '/api',
      on: {
        proxyReq(proxyReq, req) {
          // Never forward a client-supplied token; the gateway is the only trusted caller.
          proxyReq.removeHeader(TOKEN_HEADER);
          if (apiToken) proxyReq.setHeader(TOKEN_HEADER, apiToken);
          proxyReq.setHeader('x-request-id', req.id);
        },
        proxyRes: hideUpstreamHeaders,
        error: onError,
      },
    }),
  );

  app.use(
    createProxyMiddleware({
      target: webUrl,
      changeOrigin: true,
      on: {
        proxyReq(proxyReq, req, res) {
          proxyReq.removeHeader(TOKEN_HEADER);
          // Hand the nonce to vinext so it stamps it on its inline scripts.
          proxyReq.setHeader('content-security-policy', contentSecurityPolicy(res.locals.cspNonce));
          proxyReq.setHeader('x-request-id', req.id);
        },
        proxyRes: hideUpstreamHeaders,
        error: onError,
      },
    }),
  );

  return app;
}
