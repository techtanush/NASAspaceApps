const NBSP='\u00a0';
/** Display precision never alters persisted values or scientific comparisons. */
export const PRECISION:Readonly<Record<string,number>>={m:0,km:2,Wh:1,deg:1,'°':1,'m/s':2,kg:1,s:0,min:0,K:0,percent:1,'%':1,count:0};
export function quantity(value:number|null|undefined,unit='',digits?:number):string {
 if(value==null||!Number.isFinite(value))return 'Unknown';
 let display=value;let label=unit;
 if(unit==='m'&&Math.abs(value)>=1000){display=value/1000;label='km';}
 if(unit==='percent')label='%';
 const precision=digits??PRECISION[label];
 const preserveSmall=display!==0&&Math.abs(display)<1&&(label==='m'||(precision!==undefined&&Number(display.toFixed(precision))===0));
 const options:Intl.NumberFormatOptions=preserveSmall?{minimumSignificantDigits:2,maximumSignificantDigits:3}:label==='fraction'?{maximumSignificantDigits:3}:precision===undefined?{maximumFractionDigits:2}:{minimumFractionDigits:precision,maximumFractionDigits:precision};
 const formatted=new Intl.NumberFormat('en-US',options).format(display).replace('-','−');
 return label?`${formatted}${NBSP}${label}`:formatted;
}
export function quantityRange(lower:number|null,upper:number|null,unit:string):string {if(lower===null||upper===null)return 'Unknown';return `${quantity(lower,'',PRECISION[unit])}–${quantity(upper,unit,PRECISION[unit])}`;}
export function signedQuantity(value:number|null,unit:string):string {if(value===null)return 'Unknown';return `${value>=0?'+':''}${quantity(value,unit)}`;}
export const formatQuantity=quantity;
