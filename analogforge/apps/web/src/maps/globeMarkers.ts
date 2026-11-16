export interface GlobeMarker { id: string; lat: number; lng: number; label: string; status?: string; index?: number }
export interface MarkerOverlay {
  kind: 'marker'; lat: number; lng: number; marker: GlobeMarker;
  members: readonly GlobeMarker[]; selected: boolean;
  labelOffset: [number, number];
}

/** Display grouping only. Retain the original objects and never move a site or infer a result. */
export function groupNearbyLocations<T extends { lat: number; lng: number }>(locations: readonly T[]): T[][] {
  const groups: T[][] = [];
  const radians = Math.PI / 180;
  const nearby = (a: T, b: T) => {
    const haversine = Math.sin((b.lat - a.lat) * radians / 2) ** 2
      + Math.cos(a.lat * radians) * Math.cos(b.lat * radians) * Math.sin((b.lng - a.lng) * radians / 2) ** 2;
    return 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, haversine)))) / radians < 1.5;
  };
  for (const location of locations) {
    // Compare with the anchor, rather than chaining adjacent sites across a continent.
    const home = groups.find(group => nearby(group[0]!, location));
    if (home) home.push(location); else groups.push([location]);
  }
  return groups;
}

export function markerOverlays(markers: readonly GlobeMarker[], selectedId?: string | null): MarkerOverlay[] {
  return groupNearbyLocations(markers).flatMap(neighbors => neighbors.map((marker, index) => {
    // Spread only the labels. Each leader starts at its own unchanged geographic anchor.
    const angle = -Math.PI / 2 + index * 2 * Math.PI / neighbors.length;
    const radius = neighbors.length > 1 ? Math.max(62, neighbors.length * 10) : 30;
    return { kind: 'marker' as const, lat: marker.lat, lng: marker.lng, marker, members: [marker], selected: marker.id === selectedId,
      labelOffset: neighbors.length > 1 ? [Math.round(Math.cos(angle) * radius), Math.round(Math.sin(angle) * radius)] as [number, number] : [0, -30] as [number, number] };
  }));
}

export function markerElement(datum: MarkerOverlay, select: (id: string) => void): HTMLElement {
  const { marker, labelOffset: [x, y] } = datum;
  const element = document.createElement('div'); element.className = 'mc-site-anchor';
  const pin = document.createElement('span'); pin.className = 'mc-site-anchor-dot';
  const leader = document.createElement('span'); leader.className = 'mc-site-leader';
  leader.style.width = `${Math.hypot(x, y)}px`; leader.style.transform = `rotate(${Math.atan2(y, x)}rad)`;
  const button = document.createElement('button'); button.type = 'button'; button.className = 'mc-ticker';
  button.style.left = `${x}px`; button.style.top = `${y}px`;
  button.dataset.status = marker.status ?? 'UNKNOWN';
  button.setAttribute('aria-label', `Open location ${marker.index ?? ''}: ${marker.label}`);
  button.title = `${marker.label} · ${marker.lat.toFixed(5)}, ${marker.lng.toFixed(5)}`;
  button.dataset.markerId = marker.id;
  button.dataset.latitude = String(marker.lat); button.dataset.longitude = String(marker.lng);
  button.dataset.selected = String(datum.selected);
  button.dataset.group = 'false';
  const badge = document.createElement('span'); badge.className = 'mc-ticker-index'; badge.textContent = String(marker.index ?? '');
  button.append(badge); button.style.pointerEvents = 'auto';
  button.addEventListener('click', event => { event.stopPropagation(); select(marker.id); });
  element.append(leader, pin, button);
  element.dataset.selected = String(datum.selected); element.dataset.markerId = marker.id;
  return element;
}
