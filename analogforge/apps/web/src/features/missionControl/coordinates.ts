import { GLOBE_ASSETS, type GlobeBody } from '../../maps/globeAssets';

/** Display and camera geometry only. Scientific coordinates are produced and checked by the backend. */
const NUMBER = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/;
export function parseAngle(text: string): number { const value = text.trim(); return NUMBER.test(value) ? Number(value) : Number.NaN; }
/** Accepts east-positive longitude in either -180..180 or 0..360 and returns -180..180. */
export function normalizeLongitude(lng: number): number {
  if (!Number.isFinite(lng) || lng < -180 || lng > 360) return Number.NaN;
  return lng > 180 ? lng - 360 : lng;
}
export function validLatitude(lat: number): boolean { return Number.isFinite(lat) && lat >= -90 && lat <= 90; }
export type BoxResult = { ok: true; bbox: [number, number, number, number] } | { ok: false; reason: 'POLE' | 'ANTIMERIDIAN' | 'INVALID' };
/** A square area of the given edge length centred on a point, as west, south, east, north in degrees. */
export function areaBox(body: GlobeBody, lat: number, lng: number, edgeKm: number): BoxResult {
  if (!validLatitude(lat) || !Number.isFinite(lng) || (!Number.isFinite(edgeKm) || !(edgeKm > 0))) return { ok: false, reason: 'INVALID' };
  const halfLat = (edgeKm / 2 / GLOBE_ASSETS[body].radiusKm) * (180 / Math.PI);
  const south = lat - halfLat, north = lat + halfLat;
  if (south <= -90 || north >= 90) return { ok: false, reason: 'POLE' };
  const halfLng = halfLat / Math.cos((Math.max(Math.abs(south), Math.abs(north)) * Math.PI) / 180);
  const west = lng - halfLng, east = lng + halfLng;
  if (west < -180 || east > 180) return { ok: false, reason: 'ANTIMERIDIAN' };
  const round = (value: number) => Number(value.toFixed(6));
  return { ok: true, bbox: [round(west), round(south), round(east), round(north)] };
}
export function boxCentre(bbox: readonly number[]): { lat: number; lng: number } {
  return { lat: (bbox[1]! + bbox[3]!) / 2, lng: (bbox[0]! + bbox[2]!) / 2 };
}
export function formatLatitude(lat: number): string { return `${Math.abs(lat).toFixed(3)}° ${lat < 0 ? 'S' : 'N'}`; }
export function formatLongitude(lng: number): string { return `${Math.abs(lng).toFixed(3)}° ${lng < 0 ? 'W' : 'E'}`; }
export function formatPlace(lat: number, lng: number): string { return `${formatLatitude(lat)}, ${formatLongitude(lng)}`; }
/** The same east-positive longitude in the 0..360 convention many planetary products use. */
export function longitude360(lng: number): string { return `${(lng < 0 ? lng + 360 : lng).toFixed(3)}° E (0–360)`; }
