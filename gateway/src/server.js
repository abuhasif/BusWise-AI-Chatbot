import { createApp, MIN_TOKEN_LENGTH } from './app.js';

const env = process.env;
const apiToken = env.BUSWISE_API_TOKEN || '';
if (apiToken.length < MIN_TOKEN_LENGTH) {
  console.error(JSON.stringify({ level: 'fatal', msg: `Set BUSWISE_API_TOKEN to a random string of at least ${MIN_TOKEN_LENGTH} characters` }));
  process.exit(1);
}

const list = (value) => (value || '').split(',').map((s) => s.trim()).filter(Boolean);
// "1" means one proxy hop (Cloud Run, a load balancer). Leave unset when clients connect directly.
const trustProxy = /^\d+$/.test(env.TRUST_PROXY || '') ? Number(env.TRUST_PROXY) : false;

const port = Number(env.PORT || 8080);
const app = createApp({
  apiUrl: env.API_URL || 'http://127.0.0.1:8765',
  webUrl: env.WEB_URL || 'http://127.0.0.1:3000',
  apiToken,
  rateLimitPerMinute: Number(env.RATE_LIMIT_PER_MINUTE || 60),
  chatRateLimitPerMinute: Number(env.CHAT_RATE_LIMIT_PER_MINUTE || 20),
  globalRateLimitPerMinute: Number(env.GLOBAL_RATE_LIMIT_PER_MINUTE || 300),
  allowedOrigins: list(env.ALLOWED_ORIGINS),
  trustProxy,
});

const server = app.listen(port, '0.0.0.0', () => {
  console.log(JSON.stringify({ level: 'info', msg: `Buswise gateway listening on :${port}` }));
});
// Drop slow or idle clients instead of holding sockets open.
server.headersTimeout = 15_000;
server.requestTimeout = 60_000;

for (const signal of ['SIGTERM', 'SIGINT']) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
