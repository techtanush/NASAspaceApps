import {describe,expect,it,vi} from 'vitest';
import type {components} from '../generated/schema';
import seed from '../mock/fixtures/seed.json';
import {candidateCameraBounds} from '../maps/EarthMap';
vi.mock('maplibre-gl',()=>({setWorkerUrl:vi.fn()})); // EarthMap registers the worker asset when it loads; the pure camera maths needs no map
vi.mock('maplibre-gl/dist/maplibre-gl-worker.mjs?url',()=>({default:'maplibre-gl-worker.mjs'})); // the worker file is never executed here; mocking it keeps the test hermetic when dependencies are symlinked (isolated mutation copies)
type Candidate=components['schemas']['EarthAnalogCandidate'];
describe('Earth camera displays the server extents',()=>{
 it('fits small candidate windows instead of a continent-scale default',()=>{const template=seed.candidates[0] as Candidate;const west={...template,aoi:{...template.aoi,bbox:[-111,35,-110.97,35.03]}};const east={...template,aoi:{...template.aoi,bbox:[-110.8,35,-110.77,35.03]}};expect(candidateCameraBounds([west,east])).toEqual([[-111,35],[-110.77,35.03]]);expect(candidateCameraBounds([east])).toEqual([[-110.8,35],[-110.77,35.03]]);});
 it('never reinterprets a planetary region as Earth context',()=>{const template=seed.candidates[0] as Candidate;expect(candidateCameraBounds([{...template,aoi:{...template.aoi,body:'MOON'}}])).toBeNull();expect(candidateCameraBounds([])).toBeNull();});
});
