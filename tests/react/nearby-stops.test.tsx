import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import NearbyStops from '@/app/nearby-stops';
import { mockApi } from './fetch-mock';

const serangoon = {
  search: true,
  total: 1,
  stops: [
    {
      code: '66009',
      name: 'Serangoon Int',
      road: 'Serangoon Ctrl',
      services: ['100', '315'],
    },
  ],
};

function setup(props: Partial<Parameters<typeof NearbyStops>[0]> = {}) {
  const onServices = vi.fn(),
    onOrigin = vi.fn();
  render(
    <NearbyStops
      disabled={false}
      onServices={onServices}
      onOrigin={onOrigin}
      {...props}
    />,
  );
  return { user: userEvent.setup(), onServices, onOrigin };
}

describe('NearbyStops', () => {
  it('searches stops by name and lists their services', async () => {
    const calls = mockApi({ '/api/stops/search': () => ({ json: serangoon }) });
    const { user } = setup();

    await user.click(
      screen.getByRole('button', { name: 'Search by station or road' }),
    );
    const searchButton = screen.getByRole('button', { name: 'Search' });
    expect(searchButton).toBeDisabled();

    await user.type(
      screen.getByLabelText('Station, road or stop name'),
      'Serangoon',
    );
    await user.click(searchButton);

    const stop = (await screen.findByText('Serangoon Int')).closest('article')!;
    expect(
      within(stop).getByText('Serangoon Ctrl · Stop 66009'),
    ).toBeInTheDocument();
    expect(within(stop).getByText('100')).toBeInTheDocument();
    expect(within(stop).getByText('315')).toBeInTheDocument();
    expect(screen.getByText(/Showing 1 of 1 matches/)).toBeInTheDocument();
    expect(calls).toEqual([
      { path: '/api/stops/search', body: { query: 'Serangoon' } },
    ]);
  });

  it('hands the chosen stop back to the chat', async () => {
    mockApi({ '/api/stops/search': () => ({ json: serangoon }) });
    const { user, onServices, onOrigin } = setup();
    await user.click(
      screen.getByRole('button', { name: 'Search by station or road' }),
    );
    await user.type(
      screen.getByLabelText('Station, road or stop name'),
      'Serangoon{Enter}',
    );

    await user.click(await screen.findByRole('button', { name: 'Show buses' }));
    expect(onServices).toHaveBeenCalledWith('66009');

    await user.click(
      screen.getByRole('button', { name: 'Use as starting stop' }),
    );
    expect(onOrigin).toHaveBeenCalledWith('66009');
    expect(screen.queryByText('Serangoon Int')).not.toBeInTheDocument();
  });

  it('explains when the backend is unavailable', async () => {
    mockApi({
      '/api/stops/search': () => ({ status: 500, json: { error: 'boom' } }),
    });
    const { user } = setup();
    await user.click(
      screen.getByRole('button', { name: 'Search by station or road' }),
    );
    await user.type(
      screen.getByLabelText('Station, road or stop name'),
      'Serangoon{Enter}',
    );
    expect(
      await screen.findByText(/Stop search is unavailable/),
    ).toBeInTheDocument();
  });

  it('opens the search box when location permission is denied', async () => {
    const geolocation = {
      getCurrentPosition: (_ok: unknown, fail: (e: { code: number }) => void) =>
        fail({ code: 1 }),
    };
    vi.stubGlobal(
      'navigator',
      Object.assign(Object.create(navigator) as Navigator, { geolocation }),
    );
    const { user } = setup();
    await user.click(screen.getByRole('button', { name: 'Use my location' }));
    expect(
      screen.getByText(/Location permission was not granted/),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('Station, road or stop name'),
    ).toBeInTheDocument();
  });

  it('disables actions while the chat is busy', () => {
    setup({ disabled: true });
    expect(
      screen.getByRole('button', { name: 'Use my location' }),
    ).toBeDisabled();
  });
});
