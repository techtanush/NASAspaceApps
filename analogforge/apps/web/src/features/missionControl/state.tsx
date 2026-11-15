import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { GlobeBody } from '../../maps/globeAssets';
import type { GlobeScene } from '../../maps/GlobeStage';
import { areaBox, type BoxResult } from './coordinates';
import type { components } from '../../generated/schema';
import type { OperatorContext } from '../../api/operatorContext';
import { emptyContextDraft, type OperatorContextDraft } from '../operatorContext/OperatorContextEditor';

export type TargetBody = Exclude<GlobeBody, 'EARTH'>;
export interface Plan {
  body: TargetBody; latText: string; lngText: string; lat: number | null; lng: number | null; sizeKm: number; siteId: string | null; confirmed: boolean;
  name: string; objective: string; roverRevisionId: string | null; roverName: string | null; noRover: boolean;
  exactTarget: components['schemas']['MissionDraftInput']['target'] | null;
  practiceSource: { scenarioId: string; datasetLockId: string } | null;
  missionContextDraft: OperatorContextDraft; roverContext: OperatorContext | null; roverContextChecked: boolean;
}
const initial: Plan = { body: 'MARS', latText: '', lngText: '', lat: null, lng: null, sizeKm: 40, siteId: null, confirmed: false, name: '', objective: '', roverRevisionId: null, roverName: null, noRover: false, exactTarget: null, practiceSource: null, missionContextDraft: emptyContextDraft(), roverContext: null, roverContextChecked: false };
interface Control {
  plan: Plan; update: (patch: Partial<Plan>) => void; reset: () => void; box: BoxResult | null;
  scene: GlobeScene; setScene: (scene: GlobeScene) => void;
  handlers: { onPick?: (lat: number, lng: number) => void; onMarkerSelect?: (id: string) => void }; setHandlers: (handlers: Control['handlers']) => void;
}
const Context = createContext<Control | null>(null);
export function MissionControlProvider({ children }: { children: ReactNode }) {
  const [plan, setPlan] = useState<Plan>(initial);
  const [scene, setScene] = useState<GlobeScene>({ body: 'EARTH', autoRotate: true, layout: 'hero', focus: { lat: 18, lng: -40, altitude: 2.3 } });
  const [handlers, setHandlers] = useState<Control['handlers']>({});
  const box = useMemo<BoxResult | null>(() => plan.exactTarget ? { ok: true, bbox: [...plan.exactTarget.bbox] as [number, number, number, number] } : (plan.lat === null || plan.lng === null ? null : areaBox(plan.body, plan.lat, plan.lng, plan.sizeKm)), [plan.body, plan.lat, plan.lng, plan.sizeKm, plan.exactTarget]);
  const update = useCallback((patch: Partial<Plan>) => setPlan(current => {
    const geometryEdit = ['body', 'lat', 'lng', 'latText', 'lngText', 'sizeKm', 'siteId'].some(key => Object.hasOwn(patch, key));
    const roverEdit = Object.hasOwn(patch, 'roverRevisionId') && patch.roverRevisionId !== current.roverRevisionId;
    return { ...current, ...patch, ...(geometryEdit && !Object.hasOwn(patch, 'exactTarget') ? { exactTarget: null, practiceSource: null } : {}), ...(roverEdit ? { roverContext: null, roverContextChecked: false } : {}) };
  }), []);
  const reset = useCallback(() => setPlan(initial), []);
  const value = useMemo<Control>(() => ({ plan, update, reset, box, scene, setScene, handlers, setHandlers }), [plan, update, reset, box, scene, handlers]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useMissionControl(): Control { const value = useContext(Context); if (!value) throw new Error('Mission Control context is required'); return value; }
export const STEPS = [
  { id: 'place', label: 'Place', path: '/start/place' },
  { id: 'mission', label: 'Mission', path: '/start/mission' },
  { id: 'rover', label: 'Rover', path: '/start/rover' },
  { id: 'review', label: 'Review', path: '/start/review' },
  { id: 'tour', label: 'Earth sites', path: null },
] as const;
export type StepId = (typeof STEPS)[number]['id'];
