import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Home from '@/app/page';
import { mockApi } from './fetch-mock';

// The map and nearby-stop panels have their own tests; keep the page test focused on chat.
vi.mock('@/app/journey-map', () => ({
  default: () => <div data-testid="map" />,
}));
vi.mock('@/app/nearby-stops', () => ({ default: () => null }));

const stopReply = {
  answer:
    'These services are listed at your stop in the January 2026 snapshot.',
  cards: [{ Stop: '66009 · Serangoon Int', Services: '100, 101, 103' }],
  context: { intent: 'stop', stop: '66009' },
  mode: 'rules',
};

describe('Home chat', () => {
  it('shows backend status from the health check', async () => {
    mockApi({ '/api/health': () => ({ json: { model_available: false } }) });
    render(<Home />);
    expect(await screen.findByText('Limited mode')).toBeInTheDocument();
  });

  it('reports when the backend is offline', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    render(<Home />);
    expect(await screen.findByText('Backend offline')).toBeInTheDocument();
  });

  it('asks a question and renders the answer card', async () => {
    const calls = mockApi({
      '/api/health': () => ({ json: { model_available: true } }),
      '/api/chat': () => ({ json: stopReply }),
    });
    const user = userEvent.setup();
    render(<Home />);
    expect(await screen.findByText('Ready')).toBeInTheDocument();

    const send = screen.getByRole('button', { name: 'Send question' });
    expect(send).toBeDisabled();
    await user.type(
      screen.getByLabelText('Ask a bus route question'),
      'Which buses serve stop 66009?',
    );
    await user.click(send);

    expect(await screen.findByText(stopReply.answer)).toBeInTheDocument();
    expect(
      screen.getByText('Which buses serve stop 66009?'),
    ).toBeInTheDocument();
    expect(screen.getByText('66009 · Serangoon Int')).toBeInTheDocument();
    // Internal answer modes (rules/model) are not shown to riders.
    expect(screen.queryByText('rules')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Ask a bus route question')).toHaveValue('');
    expect(calls.find((c) => c.path === '/api/chat')?.body).toEqual({
      message: 'Which buses serve stop 66009?',
      context: {},
    });
  });

  it('sends a suggestion and carries context into the follow-up', async () => {
    const calls = mockApi({
      '/api/health': () => ({ json: { model_available: true } }),
      '/api/chat': () => ({ json: stopReply }),
    });
    const user = userEvent.setup();
    render(<Home />);
    await user.click(
      screen.getByRole('button', { name: 'Which buses serve stop 66009?' }),
    );
    await screen.findByText(stopReply.answer);

    await user.type(
      screen.getByLabelText('Ask a bus route question'),
      'What about Sunday?{Enter}',
    );
    await vi.waitFor(() =>
      expect(calls.filter((c) => c.path === '/api/chat')).toHaveLength(2),
    );
    expect(calls.filter((c) => c.path === '/api/chat')[1].body).toEqual({
      message: 'What about Sunday?',
      context: stopReply.context,
    });
  });

  it('answers route follow-ups locally before any journey is found', async () => {
    const calls = mockApi({
      '/api/health': () => ({ json: { model_available: true } }),
    });
    const user = userEvent.setup();
    render(<Home />);
    await user.type(
      screen.getByLabelText('Ask a bus route question'),
      'Where do I change?{Enter}',
    );
    expect(
      await screen.findByText(
        'Search for a journey first, then ask about one of its options.',
      ),
    ).toBeInTheDocument();
    expect(calls.some((c) => c.path === '/api/chat')).toBe(false);
  });

  it('shows a friendly error when the chat request fails', async () => {
    mockApi({
      '/api/health': () => ({ json: { model_available: true } }),
      '/api/chat': () => ({ status: 500, json: { error: 'boom' } }),
    });
    const user = userEvent.setup();
    render(<Home />);
    await user.type(
      screen.getByLabelText('Ask a bus route question'),
      'Last bus 168{Enter}',
    );
    expect(
      await screen.findByText(/The local backend is unavailable/),
    ).toBeInTheDocument();
  });
});
