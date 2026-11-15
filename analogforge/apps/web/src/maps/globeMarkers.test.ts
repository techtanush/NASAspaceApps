import { expect, it, vi } from 'vitest';
import { groupNearbyLocations, markerElement, markerOverlays, type GlobeMarker } from './globeMarkers';

const sites: readonly GlobeMarker[] = Object.freeze([
  Object.freeze({ id: 'a', lat: 35.38, lng: -111.58, label: 'First location', status: 'PASS', index: 1 }),
  Object.freeze({ id: 'b', lat: 35.38, lng: -111.45, label: 'Second location', status: 'FAIL', index: 2 }),
  Object.freeze({ id: 'c', lat: -24.5, lng: -69.2, label: 'Distant location', status: 'UNKNOWN', index: 3 }),
]);

it('retains every distinct site and result while collapsing nearby labels at a real selected coordinate', () => {
  const before = JSON.stringify(sites); const overlays = markerOverlays(sites, 'b');
  expect(overlays).toHaveLength(2);
  expect(overlays.flatMap(item => item.members)).toEqual(sites);
  expect(overlays[0]!.marker).toBe(sites[1]);
  expect([overlays[0]!.lat, overlays[0]!.lng]).toEqual([sites[1]!.lat, sites[1]!.lng]);
  expect(overlays[0]!.selected).toBe(true);
  expect(overlays[0]!.members.map(member => member.status)).toEqual(['PASS', 'FAIL']);
  expect(JSON.stringify(sites)).toBe(before);
});

it('opens the selected real member and labels a mixed-result group without implying aggregate PASS', () => {
  const select = vi.fn(); const element = markerElement(markerOverlays(sites, 'b')[0]!, select);
  expect(element.textContent).toBe('2nearby sites');
  expect(element.dataset.status).toBe('UNKNOWN');
  expect(element.title).toContain('Opens site 2');
  element.click(); expect(select).toHaveBeenCalledExactlyOnceWith('b');
});

it('preserves a distant single-site label, status and link target', () => {
  const select = vi.fn(); const element = markerElement(markerOverlays(sites, 'b')[1]!, select);
  expect(element.textContent).toBe('3Distant location');
  expect(element.dataset.status).toBe('UNKNOWN');
  expect(element.dataset.group).toBe('false');
  element.click(); expect(select).toHaveBeenCalledExactlyOnceWith('c');
});

it('groups geographic neighbors across the date line and at high latitudes', () => {
  expect(groupNearbyLocations([{ lat: 0, lng: 179.8 }, { lat: 0, lng: -179.8 }])).toHaveLength(1);
  expect(groupNearbyLocations([{ lat: 89, lng: 0 }, { lat: 89, lng: 45 }])).toHaveLength(1);
  expect(groupNearbyLocations([{ lat: 0, lng: 0 }, { lat: 0, lng: 45 }])).toHaveLength(2);
});

it('does not chain adjacent neighbors into an arbitrarily wide group or invent a selection', () => {
  const markers = [0, 1, 2].map((lng, index) => ({ id: String(index), lat: 0, lng, label: String(index) }));
  const overlays = markerOverlays(markers, 'foreign-site');
  expect(overlays.map(item => item.members.length)).toEqual([2, 1]);
  expect(overlays.every(item => !item.selected)).toBe(true);
  expect(overlays[0]!.marker).toBe(markers[0]);
  expect(markerOverlays([], 'foreign-site')).toEqual([]);
});
