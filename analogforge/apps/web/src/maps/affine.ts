/** GDAL order: origin x, x pixel, row rotation, origin y, column rotation, y pixel. */
export type Affine = readonly [number,number,number,number,number,number];
export type Point = readonly [number,number];
export function pixelToWorld(transform:Affine,pixel:Point):[number,number] { const [a,b,c,d,e,f]=transform;return [a+b*pixel[0]+c*pixel[1],d+e*pixel[0]+f*pixel[1]]; }
export function worldToPixel(transform:Affine,world:Point):[number,number] {const [a,b,c,d,e,f]=transform;const det=b*f-c*e;if(Math.abs(det)<Number.EPSILON)throw new Error('Singular display transform');const x=world[0]-a,y=world[1]-d;return [(f*x-c*y)/det,(-e*x+b*y)/det];}
export function screenToWorld(transform:Affine,screen:Point,viewport:{x:number;y:number;scale:number}):[number,number] {if(viewport.scale<=0)throw new Error('Invalid viewport scale');return pixelToWorld(transform,[(screen[0]-viewport.x)/viewport.scale,(screen[1]-viewport.y)/viewport.scale]);}
export function worldToScreen(transform:Affine,world:Point,viewport:{x:number;y:number;scale:number}):[number,number] {const p=worldToPixel(transform,world);return [p[0]*viewport.scale+viewport.x,p[1]*viewport.scale+viewport.y];}
export function earthCorners(bbox:readonly number[]):[number,number][] {const [w,s,e,n]=bbox;return [[w!,n!],[e!,n!],[e!,s!],[w!,s!]];}
