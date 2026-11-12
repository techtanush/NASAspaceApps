import type {components} from '../generated/schema';
type Requirement=components['schemas']['Requirement'];
export const ruleLabels:Record<Requirement['operator'],string>={GTE:'At least',LTE:'At most',BETWEEN:'Within range',EQUALS:'Exactly',PRESENT:'Must be present',NOT_NATURALLY_REPRODUCIBLE:'Not naturally reproducible'};
const observableLabels:Record<string,string>={unique_slope_exposure_m:'Unique slope exposure',completed_task_count:'Completed science tasks',final_battery_reserve_pct:'Final battery reserve',slope_band_area_fraction:'Area in the slope band',slope_distribution_w1_deg:'Slope distribution difference',surface_temperature_min_k:'Minimum surface temperature',mineral_class_present:'Mineral context',ground_clearance_m:'Ground clearance',planetary_gravity:'Planetary gravity',planetary_atmosphere:'Planetary atmosphere',route_distance_m:'Route distance',route_elapsed_s:'Route elapsed time',modeled_energy_wh:'Modeled energy',energy_conservative_wh:'Conservative modeled energy',unique_exposure_m:'Unique slope exposure',reserve_pct:'Battery reserve',tasks_completed:'Completed science tasks'};
export function requirementName(requirement:Pick<Requirement,'observable'|'label'>):string{return observableLabels[requirement.observable]??requirement.label;}
export function metricName(id:string):string{const base=id.split(':')[0]!;return observableLabels[id]??observableLabels[base]??base.replaceAll('_',' ').replace(/^./,letter=>letter.toUpperCase());}
/** Copy formatting only: the original server rule remains available in details. */
export function readableRule(rule:string):string{return rule.replace(/^≥\s*/,'At least ').replace(/^≤\s*/,'At most ').replace(/^=\s*/,'Exactly ');}

/** Present a diagnostic once; the original code and message remain in details. */
export function diagnosticSummary(code:string,message:string):string {
 let text=message.trim();if(text.startsWith(`${code}:`))text=text.slice(code.length+1).trim();if(!text)text=code;
 if(text==='EXPOSURE_SHORTFALL')return 'Required unique slope exposure was not reached.';
 return /^[A-Z][A-Z0-9_]+$/.test(text)?text.toLowerCase().replaceAll('_',' ').replace(/^./,letter=>letter.toUpperCase()):text;
}
/** Parse only an explicitly recorded single-field comparison; never infer a value. */
export function recordedChange(line:string|undefined):{field:string;before:string;after:string}|null {
 // The platform writes ASCII '->'; fixtures use '→'. Both mean the same recorded change.
 if(!line)return null;const match=/^Changed elements:\s*([^:]+):\s*(.+?)\s*(?:→|->)\s*(.+)$/.exec(line);
 if(!match||!match[1]?.trim()||!match[2]?.trim()||!match[3]?.trim())return null;
 return {field:match[1].trim(),before:match[2].trim(),after:match[3].trim()};
}
