import type {components} from '../generated/schema';
type Requirement=components['schemas']['Requirement'];
export const ruleLabels:Record<Requirement['operator'],string>={GTE:'At least',LTE:'At most',BETWEEN:'Within range',EQUALS:'Exactly',PRESENT:'Must be present',NOT_NATURALLY_REPRODUCIBLE:'Not naturally reproducible'};
const observableLabels:Record<string,string>={unique_slope_exposure_m:'Unique slope exposure',completed_task_count:'Completed science tasks',final_battery_reserve_pct:'Final battery reserve',slope_band_area_fraction:'Area in the slope band',slope_distribution_w1_deg:'Slope distribution difference',surface_temperature_min_k:'Minimum surface temperature',mineral_class_present:'Mineral context',ground_clearance_m:'Ground clearance',planetary_gravity:'Planetary gravity',planetary_atmosphere:'Planetary atmosphere',route_distance_m:'Route distance',route_elapsed_s:'Route elapsed time',modeled_energy_wh:'Modeled energy',energy_conservative_wh:'Conservative modeled energy'};
export function requirementName(requirement:Pick<Requirement,'observable'|'label'>):string{return observableLabels[requirement.observable]??requirement.label;}
export function metricName(id:string):string{return observableLabels[id]??id.replaceAll('_',' ').replace(/^./,letter=>letter.toUpperCase());}
/** Copy formatting only: the original server rule remains available in details. */
export function readableRule(rule:string):string{return rule.replace(/^≥\s*/,'At least ').replace(/^≤\s*/,'At most ').replace(/^=\s*/,'Exactly ');}
