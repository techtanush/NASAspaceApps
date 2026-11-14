/** Local horizontal ground scale for the spherical metre-based CRSs we can identify.
 * EQC: https://proj.org/en/stable/operations/projections/eqc.html
 * Polar stereographic: https://github.com/OSGeo/PROJ/blob/9.9.0/src/projections/stere.cpp
 * Unknown units, ellipsoids and methods deliberately have no inferred ground scale.
 */
export function planetaryGroundScale(wkt:string,latitude:number,svgPerMetre:number){
 if(!Number.isFinite(latitude)||Math.abs(latitude)>90||!Number.isFinite(svgPerMetre)||svgPerMetre<=0)return null;
 const number='([-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?)';
 const sphere=new RegExp('ELLIPSOID\\["[^"]+",\\s*'+number+',\\s*0\\s*[,\\]]','i').exec(wkt);
 const units=[...wkt.matchAll(/LENGTHUNIT\["([^"]+)",\s*([\d.eE+-]+)/gi)].at(-1);
 if(!sphere||!(Number(sphere[1])>0)||!units||!/^met(?:re|er)$/i.test(units[1]??'')||Number(units[2])!==1)return null;
 const match=new RegExp('PARAMETER\\["Latitude of (?:1st )?standard parallel",\\s*'+number+',\\s*ANGLEUNIT\\["degree",\\s*'+number,'i').exec(wkt);
 if(!match||Math.abs(Number(match[2])-Math.PI/180)>1e-12)return null;const standard=Number(match[1]);if(Math.abs(standard)>90)return null;
 const radians=(degrees:number)=>degrees*Math.PI/180;let groundPerMetre:number;
 if(/METHOD\["Equidistant Cylindrical \(Spherical\)"/i.test(wkt)){
  const parallel=Math.cos(radians(standard));if(parallel<1e-10)return null;
  groundPerMetre=Math.cos(radians(latitude))/parallel;
 }else if(/METHOD\["Polar Stereographic \(variant B\)"/i.test(wkt)&&standard!==0){
  groundPerMetre=(1+Math.sin(radians(latitude*Math.sign(standard))))/(1+Math.sin(radians(Math.abs(standard))));
 }else return null;
 if(!Number.isFinite(groundPerMetre)||groundPerMetre<1e-10)return null;
 const maximum=144*groundPerMetre/svgPerMetre,power=10**Math.floor(Math.log10(maximum));
 const metres=([5,2,1].find(value=>value*power<=maximum)??1)*power;
 return {metres,svgWidth:metres*svgPerMetre/groundPerMetre,latitude};
}
