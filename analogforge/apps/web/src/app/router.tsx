import { lazy,Suspense } from 'react';
import { Navigate,Route,Routes,useParams } from 'react-router-dom';
import { Workspace } from '../features/workspace/Workspace';
import { MissionEditor } from '../features/missions/MissionEditor';
import { RoverEditor } from '../features/rovers/RoverEditor';
import { RequirementTable } from '../features/missions/RequirementTable';
import { RunShell } from '../features/runs/RunShell';
import { useRun } from '../features/runs/RunContext';
import { TargetView } from '../features/targets/TargetView';
import { AnalogsView } from '../features/analogs/AnalogsView';
import { QualificationView } from '../features/qualification/QualificationView';
import { CompatibilityView } from '../features/compatibility/CompatibilityView';
import { PortfolioView } from '../features/portfolio/PortfolioView';
import { TestLabView } from '../features/testLab/TestLabView';
import { PassportView } from '../features/passport/PassportView';
import { thirdParty } from './thirdParty';
import { Skeleton,Table } from '../components/ui';
const Styleguide=import.meta.env.DEV?lazy(()=>import('../styleguide/Styleguide')):null;
function MissionView(){const {contract}=useRun();return <div className="page-stack"><h1 tabIndex={-1}>Accepted mission contract</h1><p>{contract.objective}</p><RequirementTable contract={contract}/></div>;}
function Rovers(){const {roverId}=useParams();return <div className="page-stack"><h1 tabIndex={-1}>Rover library</h1><RoverEditor initialId={roverId}/></div>;}
function About(){return <div className="page-stack"><h1 tabIndex={-1}>About AnalogForge</h1><p>Mission-conditioned analog qualification. Not a NASA product; no endorsement implied.</p><Table caption="Open-source components and licences"><thead><tr><th scope="col">Component</th><th scope="col">Version</th><th scope="col">Licence</th></tr></thead><tbody>{thirdParty.map(({name,version,licence})=><tr key={name}><th scope="row">{name}</th><td className="mono">{version}</td><td>{licence}</td></tr>)}</tbody></Table></div>;}
export function AppRoutes(){return <Routes><Route path="/" element={<Workspace/>}/><Route path="/missions/new" element={<MissionEditor/>}/><Route path="/missions/:missionId/edit" element={<MissionEditor/>}/><Route path="/rovers" element={<Rovers/>}/><Route path="/rovers/:roverId" element={<Rovers/>}/><Route path="/runs/:runId" element={<RunShell/>}><Route index element={<Navigate to="target" replace/>}/><Route path="mission" element={<MissionView/>}/><Route path="target" element={<TargetView/>}/><Route path="analogs" element={<AnalogsView/>}/><Route path="qualification" element={<QualificationView/>}/><Route path="compatibility" element={<CompatibilityView/>}/><Route path="portfolio" element={<PortfolioView/>}/><Route path="test-lab" element={<TestLabView/>}/><Route path="passport" element={<PassportView/>}/></Route><Route path="/about" element={<About/>}/>{Styleguide&&<Route path="/__styleguide" element={<Suspense fallback={<Skeleton/>}><Styleguide/></Suspense>}/>}<Route path="*" element={<div className="page-stack"><h1>View not found</h1><p>This route does not identify an available workspace view.</p></div>}/></Routes>;}
