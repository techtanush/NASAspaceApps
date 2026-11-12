/** Display geometry only; never derives terrain measurements. */
export function formatCoordinate(value:number,axis:'lon'|'lat'):string {
 if(!Number.isFinite(value))return 'Unknown';
 const normalized=Math.abs(value)<0.000005?0:value;
 const magnitude=Math.abs(normalized).toFixed(5);
 return `${magnitude}° ${axis==='lon'?(normalized<0?'W':'E'):(normalized<0?'S':'N')}`;
}
export function formatCoordinatePair(lon:number,lat:number,frame='WGS84'):string {
 return `${formatCoordinate(lon,'lon')}, ${formatCoordinate(lat,'lat')} · ${frame}`;
}
export function formatBounds(bbox:readonly number[],frame='WGS84'):string {
 if(bbox.length!==4)return `Unknown extent · ${frame}`;
 return `West ${formatCoordinate(bbox[0]!,'lon')}; south ${formatCoordinate(bbox[1]!,'lat')}; east ${formatCoordinate(bbox[2]!,'lon')}; north ${formatCoordinate(bbox[3]!,'lat')} · ${frame}`;
}
