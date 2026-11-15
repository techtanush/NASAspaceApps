export interface GlobeMarker { id: string; lat: number; lng: number; label: string; status?: string; index?: number }
export interface MarkerOverlay {
  kind: 'marker'; lat: number; lng: number; marker: GlobeMarker;
  members: readonly GlobeMarker[]; selected: boolean;
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
  return groupNearbyLocations(markers).map(members => {
    const selected = members.find(marker => marker.id === selectedId);
    const marker = selected ?? members[0]!;
    // Anchor to a real member, never an invented centroid or displaced coordinate.
    return { kind: 'marker', lat: marker.lat, lng: marker.lng, marker, members, selected: Boolean(selected) };
  });
}

export function markerElement(datum: MarkerOverlay, select: (id: string) => void): HTMLElement {
  const { marker, members } = datum; const grouped = members.length > 1;
  const element = document.createElement('div'); element.className = 'mc-ticker';
  // A display group has no aggregate scientific status, even when one member passes.
  element.dataset.status = grouped ? 'UNKNOWN' : marker.status ?? 'UNKNOWN';
  element.dataset.selected = String(datum.selected); element.dataset.markerId = marker.id;
  element.dataset.group = String(grouped); element.dataset.memberCount = String(members.length);
  element.setAttribute('aria-hidden', 'true');
  element.title = grouped ? `${members.length} nearby sites. Opens site ${marker.index ?? marker.label}; every location is available in the site list.` : marker.label;
  const badge = document.createElement('span'); badge.className = 'mc-ticker-index'; badge.textContent = String(grouped ? members.length : marker.index ?? '');
  const label = document.createElement('span'); label.className = 'mc-ticker-label'; label.textContent = grouped ? 'nearby sites' : marker.label;
  element.append(badge, label); element.style.pointerEvents = 'auto';
  element.addEventListener('click', event => { event.stopPropagation(); select(marker.id); });
  return element;
}
