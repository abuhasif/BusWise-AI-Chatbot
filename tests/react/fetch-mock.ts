import { vi } from 'vitest';

type Handler = (
  body: unknown,
) =>
  | { status?: number; json: unknown }
  | Promise<{ status?: number; json: unknown }>;

/** Stubs global fetch with per-path handlers and records each request. */
export function mockApi(routes: Record<string, Handler>) {
  const calls: { path: string; body: unknown }[] = [];
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path =
        typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.pathname
            : input.url;
      const body: unknown =
        typeof init?.body === 'string' ? JSON.parse(init.body) : undefined;
      calls.push({ path, body });
      const handler = routes[path];
      if (!handler) throw new TypeError(`Unexpected request to ${path}`);
      const { status = 200, json } = await handler(body);
      return new Response(JSON.stringify(json), {
        status,
        headers: { 'Content-Type': 'application/json' },
      });
    },
  );
  vi.stubGlobal('fetch', fetchMock);
  return calls;
}
