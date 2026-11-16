import { expect, it, vi } from 'vitest';
import { groupNearbyLocations, markerElement, markerOverlays, type GlobeMarker } from './globeMarkers';

const sites: readonly GlobeMarker[] = Object.freeze([
  Object.freeze({ id: 'a', lat: 35.38, lng: -111.58, label: 'First location', status: 'PASS', index: 1 }),
  Object.freeze({ id: 'b', lat: 35.38, lng: -111.45, label: 'Second location', status: 'FAIL', index: 2 }),
  Object.freeze({ id: 'c', lat: -24.5, lng: -69.2, label: 'Distant location', status: 'UNKNOWN', index: 3 }),
]);

it('gives every location its own exact geographic anchor and independently selectable label', () => {
  const before = JSON.stringify(sites); const overlays = markerOverlays(sites, 'b');
  expect(overlays).toHaveLength(3);
  expect(overlays.flatMap(item => item.members)).toEqual(sites);
  overlays.forEach((overlay, index) => {
    expect(overlay.marker).toBe(sites[index]);
    expect([overlay.lat, overlay.lng]).toEqual([sites[index]!.lat, sites[index]!.lng]);
    expect(overlay.selected).toBe(index === 1);
  });
  expect(overlays[0]!.labelOffset).not.toEqual(overlays[1]!.labelOffset);
  expect(JSON.stringify(sites)).toBe(before);
});

it('opens each exact location without aggregating mixed scientific outcomes', () => {
  const select = vi.fn();
  const elements = markerOverlays(sites, 'b').map(overlay => markerElement(overlay, select));
  elements.forEach((element, index) => {
    const button = element.querySelector('button')!;
    expect(button.textContent).toBe(String(index + 1));
    expect(button.dataset.status).toBe(sites[index]!.status);
    expect(Number(button.dataset.latitude)).toBe(sites[index]!.lat);
    expect(Number(button.dataset.longitude)).toBe(sites[index]!.lng);
    expect(button.dataset.group).toBe('false');
    expect(button.getAttribute('aria-label')).toContain(sites[index]!.label);
    button.click();
    expect(select).toHaveBeenLastCalledWith(sites[index]!.id);
  });
  expect(select).toHaveBeenCalledTimes(3);
});

it('groups geographic neighbors across the date line and at high latitudes', () => {
  expect(groupNearbyLocations([{ lat: 0, lng: 179.8 }, { lat: 0, lng: -179.8 }])).toHaveLength(1);
  expect(groupNearbyLocations([{ lat: 89, lng: 0 }, { lat: 89, lng: 45 }])).toHaveLength(1);
  expect(groupNearbyLocations([{ lat: 0, lng: 0 }, { lat: 0, lng: 45 }])).toHaveLength(2);
});

it('does not chain adjacent neighbors into an arbitrarily wide group or invent a selection', () => {
  const markers = [0, 1, 2].map((lng, index) => ({ id: String(index), lat: 0, lng, label: String(index) }));
  const overlays = markerOverlays(markers, 'foreign-site');
  expect(overlays.map(item => item.members.length)).toEqual([1, 1, 1]);
  expect(overlays.every(item => !item.selected)).toBe(true);
  expect(overlays[0]!.marker).toBe(markers[0]);
  expect(markerOverlays([], 'foreign-site')).toEqual([]);
});
