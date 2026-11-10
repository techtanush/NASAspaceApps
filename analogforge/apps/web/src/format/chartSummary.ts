import {quantity} from './quantity';
type Bin={label:string;value:number|null};
/** Describe only supplied plotted values; missing bins cannot establish a trend. */
export function chartSummary(values:readonly Bin[],unit:string):string {
 const known=values.filter((item):item is Bin & {value:number}=>item.value!==null&&Number.isFinite(item.value));
 if(!known.length)return 'No known plotted values are available; the pattern is unknown.';
 const describe=(item:Bin & {value:number})=>`${item.label} (${quantity(item.value,unit)})`;
 const missing=values.length-known.length;
 const caveat=missing?` ${missing} of ${values.length} bins are unknown; a complete trend cannot be determined.`:'';
 if(known.length===1)return `Only one known value: ${describe(known[0]!)}.${caveat}`;
 const first=known[0]!,last=known.at(-1)!;
 const minimum=Math.min(...known.map(item=>item.value)),maximum=Math.max(...known.map(item=>item.value));
 if(minimum===maximum)return `All ${known.length} known values are equal at ${quantity(minimum,unit)}.${caveat}`;
 if(!missing){
  const decreasing=known.every((item,index)=>index===0||item.value<=known[index-1]!.value);
  const increasing=known.every((item,index)=>index===0||item.value>=known[index-1]!.value);
  if(decreasing||increasing)return `Values ${decreasing?'decrease':'increase'} from ${describe(first)} to ${describe(last)}.`;
 }
 const peaks=known.filter(item=>item.value===maximum).map(item=>item.label).join(', ');
 const lows=known.filter(item=>item.value===minimum).map(item=>item.label).join(', ');
 return `Highest supplied value: ${peaks} at ${quantity(maximum,unit)}; lowest: ${lows} at ${quantity(minimum,unit)}.${caveat}`;
}
