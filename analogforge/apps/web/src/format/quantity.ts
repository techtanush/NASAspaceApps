const NBSP='\u00a0';
/** Display precision never alters persisted values or scientific comparisons. */
export const PRECISION:Readonly<Record<string,number>>={m:0,km:2,Wh:1,deg:1,'°':1,'m/s':2,kg:1,s:0,min:0,K:0,percent:1,'%':1,count:0};
function number(value:number,unit:string,digits?:number,useGrouping=true):string {
 const precision=digits??PRECISION[unit];
 const preserveSmall=value!==0&&Math.abs(value)<1&&(unit==='m'||(precision!==undefined&&Number(value.toFixed(precision))===0));
 const options:Intl.NumberFormatOptions=preserveSmall?{minimumSignificantDigits:2,maximumSignificantDigits:3}:unit==='fraction'?{maximumSignificantDigits:3}:precision===undefined?{maximumFractionDigits:2}:{minimumFractionDigits:precision,maximumFractionDigits:precision};
 return new Intl.NumberFormat('en-US',{...options,useGrouping}).format(value).replace('-','−');
}
export function quantity(value:number|null|undefined,unit='',digits?:number):string {
 if(value==null||!Number.isFinite(value))return 'Unknown';
 let display=value;let label=unit;
 if(unit==='m'&&Math.abs(value)>=1000){display=value/1000;label='km';}
 if(unit==='percent')label='%';
 const formatted=number(display,label,digits);
 return label?`${formatted}${NBSP}${label}`:formatted;
}
/** Numeric editors retain their labelled unit and accept unformatted text while focused. */
export function inputQuantity(value:number|null|undefined,unit:string):string {return value==null||!Number.isFinite(value)?'':number(value,unit,undefined,false).replace('−','-');}
export function quantityRange(lower:number|null,upper:number|null,unit:string):string {
 if(lower===null||upper===null||!Number.isFinite(lower)||!Number.isFinite(upper))return 'Unknown';
 // A range shares one unit: converting only its upper endpoint changes its physical meaning.
 const label=unit==='m'&&Math.max(Math.abs(lower),Math.abs(upper))>=1000?'km':unit==='percent'?'%':unit;
 const divisor=unit==='m'&&label==='km'?1000:1;
 return `${number(lower/divisor,label)}–${number(upper/divisor,label)}${label?NBSP+label:''}`;
}
export function signedQuantity(value:number|null,unit:string):string {if(value===null)return 'Unknown';return `${value>=0?'+':''}${quantity(value,unit)}`;}
export const formatQuantity=quantity;
