import type { components } from '../generated/schema';
export type QualificationStatus = components['schemas']['QualificationStatus'];
export const STATUS_LABELS: Record<QualificationStatus | 'PENDING', { label: string; icon: string; description: string }> = {
  PASS: {label:'PASS',icon:'check',description:'Meets this requirement within its evidence scope'},
  PARTIAL:{label:'PARTIAL',icon:'half',description:'Partly supported within stated limits'},
  FAIL:{label:'FAIL',icon:'cross',description:'Does not meet this requirement'},
  GAP:{label:'GAP',icon:'gap',description:'Not naturally reproducible on Earth'},
  UNKNOWN:{label:'UNKNOWN',icon:'question',description:'Insufficient evidence to assess'},
  PENDING:{label:'PENDING',icon:'clock',description:'Not yet computed'},
};
