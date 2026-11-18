import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { createApp } from '../src/app.js';

const TOKEN = 'test-token-0123456789abcdef0123456789';

// Tiny fake upstreams that echo what they received.
function upstream(name) {
  const server = http.createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => (body += chunk));
    req.on('end', () => {
      res.setHeader('content-type', 'application/json');
      res.setHeader('server', 'BaseHTTP/0.6 Python/3.12.0');
      res.setHeader('access-control-allow-origin', '*');
      res.end(JSON.stringify({
        name, method: req.method, url: req.url, body,
        token: req.headers['x-buswise-token'] ?? null,
        csp: req.headers['content-security-policy'] ?? null,
      }));
    });
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}
const url = (server) => `http://127.0.0.1:${server.address().port}`;
const listen = (app) => new Promise((resolve) => { const s = app.listen(0, '127.0.0.1', () => resolve(s)); });
const json = (body, headers = {}) => ({ method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: JSON.stringify(body) });

let api, web, gateway, base;
const make = (options = {}) => createApp({ apiUrl: url(api), webUrl: url(web), apiToken: TOKEN, log: () => {}, ...options });
async function withApp(options, fn) {
  const server = await listen(make(options));
  try { await fn(url(server)); } finally { server.close(); }
}

before(async () => {
  api = await upstream('api');
  web = await upstream('web');
  gateway = await listen(make({ allowedOrigins: ['https://app.example'] }));
  base = url(gateway);
});
after(() => { for (const s of [api, web, gateway]) s.close(); });

test('healthz reports the gateway is alive', async () => {
  const response = await fetch(`${base}/healthz`);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: 'ok', service: 'gateway' });
});

test('/api requests go to the Python API with the gateway token, not the client one', async () => {
  const response = await fetch(`${base}/api/chat`, json({ message: 'hi' }, { 'x-buswise-token': 'forged' }));
  const data = await response.json();
  assert.equal(data.name, 'api');
  assert.equal(data.url, '/api/chat');
  assert.equal(data.token, TOKEN);
  assert.equal(data.body, '{"message":"hi"}');
  assert.equal(response.headers.get('cache-control'), 'no-store');
});

test('page requests go to the web app with a CSP nonce and without the API token', async () => {
  const response = await fetch(`${base}/some/page?x=1`, { headers: { 'x-buswise-token': TOKEN } });
  const data = await response.json();
  assert.equal(data.name, 'web');
  assert.equal(data.url, '/some/page?x=1');
  assert.equal(data.token, null);
  const nonce = /'nonce-([^']+)'/.exec(response.headers.get('content-security-policy'))?.[1];
  assert.ok(nonce, 'response CSP carries a nonce');
  assert.match(data.csp, new RegExp(`'nonce-${nonce.replace(/[+/=]/g, '\\$&')}'`), 'web app receives the same nonce');
});

test('each response gets a fresh nonce', async () => {
  const nonces = await Promise.all([1, 2].map(async () => (await fetch(`${base}/`)).headers.get('content-security-policy')));
  assert.notEqual(nonces[0], nonces[1]);
});

test('security headers are set and upstream version headers are hidden', async () => {
  const response = await fetch(`${base}/`);
  const h = response.headers;
  const csp = h.get('content-security-policy');
  for (const directive of ["default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'self'"]) assert.ok(csp.includes(directive), directive);
  assert.ok(!/script-src[^;]*unsafe-inline/.test(csp), 'no unsafe-inline scripts');
  assert.equal(h.get('x-content-type-options'), 'nosniff');
  assert.equal(h.get('x-frame-options'), 'DENY');
  assert.equal(h.get('referrer-policy'), 'strict-origin-when-cross-origin');
  assert.match(h.get('strict-transport-security'), /max-age=\d+/);
  assert.match(h.get('permissions-policy'), /camera=\(\)/);
  assert.equal(h.get('cross-origin-opener-policy'), 'same-origin');
  assert.equal(h.get('server'), null);
  assert.equal(h.get('x-powered-by'), null);
  assert.equal(h.get('access-control-allow-origin'), null, 'upstream wildcard CORS is stripped');
});

test('readyz checks both upstreams', async () => {
  const response = await fetch(`${base}/readyz`);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: 'ok', api: 'ok', web: 'ok' });
});

test('CORS: other websites cannot call the API; listed origins can', async () => {
  const evil = await fetch(`${base}/api/chat`, json({ message: 'hi' }, { origin: 'https://evil.example' }));
  assert.equal(evil.status, 403);
  assert.equal(evil.headers.get('access-control-allow-origin'), null);

  const same = await fetch(`${base}/api/chat`, json({ message: 'hi' }, { origin: base }));
  assert.equal(same.status, 200);
  assert.equal(same.headers.get('access-control-allow-origin'), null, 'same-origin needs no CORS header');

  const listed = await fetch(`${base}/api/chat`, json({ message: 'hi' }, { origin: 'https://app.example' }));
  assert.equal(listed.status, 200);
  assert.equal(listed.headers.get('access-control-allow-origin'), 'https://app.example');

  const preflight = await fetch(`${base}/api/chat`, { method: 'OPTIONS', headers: { origin: 'https://app.example' } });
  assert.equal(preflight.status, 204);
  assert.match(preflight.headers.get('access-control-allow-methods'), /POST/);
});

test('API rejects bad methods, non-JSON bodies and oversized requests', async () => {
  assert.equal((await fetch(`${base}/api/chat`, { method: 'DELETE' })).status, 405);
  assert.equal((await fetch(`${base}/api/chat`, { method: 'POST', headers: { 'content-type': 'text/plain' }, body: '{}' })).status, 415);
  assert.equal((await fetch(`${base}/api/chat`, json({ message: 'x'.repeat(20_000) }))).status, 413);
});

test('a malformed request id is replaced rather than echoed', async () => {
  const response = await fetch(`${base}/healthz`, { headers: { 'x-request-id': 'bad id <script>' } });
  assert.match(response.headers.get('x-request-id'), /^[0-9a-f-]{36}$/);
  const kept = await fetch(`${base}/healthz`, { headers: { 'x-request-id': 'trace-123' } });
  assert.equal(kept.headers.get('x-request-id'), 'trace-123');
});

test('/api is rate limited per client, with a tighter limit on chat', async () => {
  await withApp({ rateLimitPerMinute: 3, chatRateLimitPerMinute: 1 }, async (b) => {
    const chat = [];
    for (let i = 0; i < 2; i++) chat.push((await fetch(`${b}/api/chat`, json({ message: 'hi' }))).status);
    assert.deepEqual(chat, [200, 429]);
    assert.equal((await fetch(`${b}/api/health`)).status, 200);
    assert.equal((await fetch(`${b}/api/health`)).status, 429, 'chat calls count towards the /api limit too');
    assert.equal((await fetch(`${b}/`)).status, 200, 'pages are not limited by the /api budget');
  });
});

test('a global limit protects every route', async () => {
  await withApp({ globalRateLimitPerMinute: 2 }, async (b) => {
    const statuses = [];
    for (let i = 0; i < 3; i++) statuses.push((await fetch(`${b}/`)).status);
    assert.deepEqual(statuses, [200, 200, 429]);
  });
});

test('spoofed X-Forwarded-For is ignored unless a trusted proxy is configured', async () => {
  await withApp({ rateLimitPerMinute: 1 }, async (b) => {
    assert.equal((await fetch(`${b}/api/health`, { headers: { 'x-forwarded-for': '1.1.1.1' } })).status, 200);
    assert.equal((await fetch(`${b}/api/health`, { headers: { 'x-forwarded-for': '2.2.2.2' } })).status, 429);
  });
});

test('a weak API token is refused at startup', () => {
  assert.throws(() => createApp({ apiUrl: 'http://a', webUrl: 'http://b', apiToken: 'short' }), /at least 32/);
});

test('an unreachable upstream returns 502 and readyz reports degraded', async () => {
  const server = await listen(createApp({ apiUrl: 'http://127.0.0.1:9', webUrl: url(web), log: () => {} }));
  try {
    const response = await fetch(`${url(server)}/api/health`);
    assert.equal(response.status, 502);
    assert.deepEqual(await response.json(), { error: 'Upstream service unavailable' });
    const ready = await fetch(`${url(server)}/readyz`);
    assert.equal(ready.status, 503);
    assert.equal((await ready.json()).api, 'unreachable');
  } finally {
    server.close();
  }
});
