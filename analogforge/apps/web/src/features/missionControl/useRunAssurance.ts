import validateAssurance from '../../generated/validateAssurance.js';
import { useApi } from '../../api/hooks/useApi';
import { useWorkspace } from '../../app/WorkspaceContext';
import { useOperationArtifact, type Schema } from '../runs/RunContext';
interface Audit { workspace_id: string; run_id: string; mode: Schema['RuntimeMode']; mission_content_sha256: string; rover_content_sha256: string | null; publication: string; limitations: string[] }
/** The presentation decision is taken only from the matching validated publication audit. */
export function useRunAssurance(snapshot?: Schema['RunSnapshot'], contract?: Schema['MissionTestContract'], rover?: Schema['RoverProfile']) {
  const workspace = useWorkspace();
  const passport = useApi<Schema['AnalogPassport']>(workspace, `/passports/${snapshot?.passport_id}`, !!snapshot?.passport_id);
  const audit = useOperationArtifact<Audit>(passport.data ? [passport.data.assurance_evidence_id] : [], 'SCIENTIFIC_ASSURANCE');
  const p = passport.data; const a = audit.data;
  const valid = !!(snapshot && contract && p && a && validateAssurance(a) && p.workspace_id === snapshot.workspace_id && p.run_id === snapshot.run_id && p.mode === snapshot.mode && p.mission_revision_id === snapshot.mission_revision_id && p.rover_revision_id === snapshot.rover_revision_id && a.workspace_id === snapshot.workspace_id && a.run_id === snapshot.run_id && a.mode === snapshot.mode && a.mission_content_sha256 === contract.content_sha256 && a.rover_content_sha256 === (snapshot.rover_revision_id ? rover?.content_sha256 : null));
  return { publication: valid ? a!.publication : 'INCOMPLETE', passport: valid ? p : null, limitations: valid ? a!.limitations : [], error: passport.error || audit.error || (a && !valid ? new Error('Publication evidence does not match the current frozen inputs.') : null) };
}
