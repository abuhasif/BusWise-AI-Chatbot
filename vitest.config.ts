import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// Separate from vite.config.ts so component tests don't load the Cloudflare/vinext plugins.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('.', import.meta.url)),
      'next/link': fileURLToPath(
        new URL('./tests/react/next-link-stub.tsx', import.meta.url),
      ),
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/react/**/*.test.tsx'],
    setupFiles: ['tests/react/setup.ts'],
    restoreMocks: true,
    unstubGlobals: true,
  },
});
