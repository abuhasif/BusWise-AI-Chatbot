import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import JourneyMap, { type MapResult } from '@/app/journey-map';
import { mockApi } from './fetch-mock';

// Leaflet needs a real layout engine; a chainable fake is enough for these tests.
vi.mock('leaflet', () => {
  const layer = () => {
    const self: Record<string, unknown> = {};
    for (const name of [
      'addTo',
      'on',
      'bindTooltip',
      'setView',
      'fitBounds',
      'clearLayers',
      'remove',
    ])
      self[name] = () => self;
    self.getZoom = () => 11;
    return self;
  };
  return {
    map: layer,
    tileLayer: layer,
    layerGroup: layer,
    circleMarker: layer,
    circle: layer,
    polyline: layer,
    canvas: () => ({}),
    latLngBounds: () => ({}),
  };
});

const journey: MapResult = {
  source: 'OneMap',
  notice: 'Bus journeys for departure now.',
  origin: { name: 'Woodlands Int', point: [1.437, 103.786] },
  destination: { name: 'Hougang Int', point: [1.371, 103.892] },
  routes: [
    {
      label: 'Bus 168',
      minutes: 55,
      legs: [
        {
          mode: 'BUS',
          service: '168',
          from: 'Woodlands Int',
          to: 'Hougang Int',
          points: [],
        },
      ],
    },
    {
      label: 'Bus 858 → 72',
      minutes: 64,
      legs: [
        {
          mode: 'BUS',
          service: '858',
          from: 'Woodlands Int',
          to: 'Yishun Int',
          points: [],
        },
        {
          mode: 'BUS',
          service: '72',
          from: 'Yishun Int',
          to: 'Hougang Int',
          points: [],
        },
      ],
    },
  ],
};

function setup() {
  const onRequest = vi.fn(),
    onReply = vi.fn(),
    onSelect = vi.fn();
  render(
    <JourneyMap onRequest={onRequest} onReply={onReply} onSelect={onSelect} />,
  );
  return { user: userEvent.setup(), onRequest, onReply, onSelect };
}

describe('JourneyMap', () => {
  it('finds a journey and lets the rider compare options', async () => {
    const calls = mockApi({
      '/api/map/stops': () => ({ json: { stops: [] } }),
      '/api/map/journey': () => ({ json: journey }),
    });
    const { user, onRequest, onReply, onSelect } = setup();

    await user.type(screen.getByLabelText('From'), 'Woodlands Int');
    await user.type(screen.getByLabelText('To'), 'Hougang Int');
    await user.click(screen.getByRole('button', { name: 'Find buses' }));

    const first = await screen.findByRole('button', {
      name: 'Bus 168 · 55 min',
    });
    expect(first).toHaveAttribute('aria-pressed', 'true');
    expect(onRequest).toHaveBeenCalledWith('Woodlands Int', 'Hougang Int');
    expect(onReply).toHaveBeenCalledWith(journey);
    expect(calls.find((c) => c.path === '/api/map/journey')?.body).toEqual({
      origin: 'Woodlands Int',
      destination: 'Hougang Int',
      options: {},
    });

    await user.click(
      screen.getByRole('button', { name: 'Bus 858 → 72 · 64 min' }),
    );
    expect(onSelect).toHaveBeenCalledWith(1);
    expect(
      screen.getByText('Bus 72: Yishun Int → Hougang Int'),
    ).toBeInTheDocument();
  });

  it('sends typed coordinates as a point', async () => {
    const calls = mockApi({
      '/api/map/stops': () => ({ json: { stops: [] } }),
      '/api/map/journey': () => ({ json: journey }),
    });
    const { user } = setup();
    await user.type(screen.getByLabelText('From'), '1.437, 103.786');
    await user.type(screen.getByLabelText('To'), '66009');
    await user.click(screen.getByRole('button', { name: 'Find buses' }));
    await screen.findByRole('button', { name: 'Bus 168 · 55 min' });
    expect(
      calls.find((c) => c.path === '/api/map/journey')?.body,
    ).toMatchObject({ origin: [1.437, 103.786], destination: '66009' });
  });

  it('shows the API error and reports it to the chat', async () => {
    mockApi({
      '/api/map/stops': () => ({ json: { stops: [] } }),
      '/api/map/journey': () => ({
        status: 400,
        json: { error: 'Could not locate destination' },
      }),
    });
    const { user, onReply } = setup();
    await user.type(screen.getByLabelText('From'), 'Woodlands Int');
    await user.type(screen.getByLabelText('To'), 'Nowhere');
    await user.click(screen.getByRole('button', { name: 'Find buses' }));
    expect(
      await screen.findByText('Could not locate destination'),
    ).toBeInTheDocument();
    expect(onReply).toHaveBeenCalledWith(null, 'Could not locate destination');
  });
});
