/* PowerPath v13: dependency scheduling and evidence-first energy screening.
   Calendar-day planning templates, NOT jurisdiction-specific regulatory advice. */
(function(root){
const DAY=86400000,STATUSES=['Not started','In progress','Blocked','Complete'];
function dateDay(s){if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(s))throw Error('Use YYYY-MM-DD dates');let t=Date.parse(s+'T00:00:00Z');if(!Number.isFinite(t)||new Date(t).toISOString().slice(0,10)!==s)throw Error('Invalid calendar date');return t/DAY;}
function iso(d){return new Date(Math.round(d)*DAY).toISOString().slice(0,10);}
function add(s,n){return iso(dateDay(s)+n);}
function freshProject(route='grid'){
 const tasks=[
 ['site','Site control and infrastructure diligence','Diligence',21,[],'Development lead','Land, fiber, cooling and access rights'],
 ['request','Connection application completeness','Interconnection',21,['site'],'Utility liaison','Confirm serving utility process and information requirements'],
 ['study','Utility study and technical review','Interconnection',90,['request'],'Power lead','Obtain a project-specific study scope and written utility milestones'],
 ['commercial','Power supply and connection agreement','Commercial',45,['study'],'Commercial lead','Capacity, service conditions, costs and milestones'],
 ['planning','Land-use and building approval review','Permitting',90,['site'],'Permitting lead','Determine applicable land-use, construction and local approvals'],
 ['environment','Environmental and resource review','Permitting',60,['site'],'Environmental lead','Determine applicable environmental, water and other approvals'],
 ['equipment','Electrical equipment procurement','Delivery',240,['study'],'Procurement lead','Validate equipment specifications, quotes and delivery dates'],
 ['phase1','First-phase electrical works','Delivery',150,['commercial','planning','environment','equipment'],'Construction lead','Confirm owner/utility split and first-phase deliverable capacity'],
 ['fiber','Fiber and cooling readiness','Delivery',120,['site'],'Infrastructure lead','Verify redundant fiber, cooling design and supporting infrastructure'],
 ['first','First usable power / commissioning','Milestone',14,['phase1','fiber'],'Commissioning lead','Record tested, contracted and usable capacity'],
 ['expansion','Remaining capacity and expansion works','Delivery',180,['first'],'Construction lead','Confirm rights and upgrades needed for full required capacity'],
 ['full','Full required power / commissioning','Milestone',14,['expansion'],'Commissioning lead','Validate full-load service and operating conditions']
 ];
 if(route==='colocation'){
 tasks.splice(1,0,
 ['asset','Generation availability and rights diligence','Energy',45,['site'],'Energy lead','Validate hourly output, existing offtake, curtailment cause and rights to serve adjacent load'],
 ['firming','Firming and workload-fit study','Energy',60,['asset'],'Engineering lead','Assess dependable supply, storage/backup, islanding and workload requirements'],
 ['air','Generation and air-permit applicability review','Permitting',90,['firming'],'Permitting lead','Determine approvals for any proposed generation or backup; do not assume exempt']
 );
 tasks.find(t=>t[0]==='request')[1]='Utility / network configuration review';
 tasks.find(t=>t[0]==='request')[6]='Determine service, protection, metering and applicable utility/ISO process for co-location';
 tasks.find(t=>t[0]==='commercial')[4].push('asset');
 tasks.find(t=>t[0]==='equipment')[4].push('firming');
 tasks.find(t=>t[0]==='phase1')[4].push('air');
 }
 return {id:'project-'+route,name:route==='grid'?'Texas campus · site-first':'Energy-led campus · co-location',route,jurisdiction:'To be established',utility:'To be confirmed',workload:'Continuous',asOf:'2026-10-25',baselineFirst:'2028-04-25',targetFirst:'2028-04-25',targetFull:'2029-02-25',firstMW:25,requiredMW:75,opportunityId:null,tasks:tasks.map(([id,name,category,duration,deps,owner,scope])=>({id,name,category,duration,deps,owner,scope,authority:'To be confirmed',externalRef:'',status:'Not started',notBefore:'2026-10-25',due:'',actualFinish:'',sourceType:'Planning assumption',evidenceStatus:'Unverified',evidence:'',evidenceDate:'',notes:''}))};
}
function validateProject(p){
 if(!p||typeof p.name!=='string'||!p.name.trim()||!['grid','colocation'].includes(p.route))throw Error('Invalid project name or route');
 ['asOf','baselineFirst','targetFirst','targetFull'].forEach(k=>dateDay(p[k]));
 if(!Number.isFinite(p.firstMW)||!Number.isFinite(p.requiredMW)||p.firstMW<=0||p.requiredMW<p.firstMW)throw Error('Required MW must be at least first-phase MW, both positive');
 if(dateDay(p.targetFull)<dateDay(p.targetFirst))throw Error('Full-power target must follow first-power target');
 if(!Array.isArray(p.tasks)||!p.tasks.length||p.tasks.length>150)throw Error('Project needs 1–150 tasks');
 const ids=new Set(p.tasks.map(t=>t.id));if(ids.size!==p.tasks.length||!ids.has('first')||!ids.has('full'))throw Error('Task IDs must be unique and include first/full milestones');
 for(const t of p.tasks){
  if(!/^[a-zA-Z0-9_-]+$/.test(t.id)||!t.name?.trim()||!Number.isInteger(t.duration)||t.duration<0||t.duration>3650||!STATUSES.includes(t.status))throw Error('Invalid task name, duration or status');
  if(!Array.isArray(t.deps)||new Set(t.deps).size!==t.deps.length||t.deps.some(d=>!ids.has(d)||d===t.id))throw Error('Unknown, duplicate or circular task dependency');
  if(!['Unverified','Documented','Confirmed'].includes(t.evidenceStatus))throw Error('Invalid evidence status');
  if(t.notBefore)dateDay(t.notBefore);if(t.due)dateDay(t.due);if(t.evidenceDate&&dateDay(t.evidenceDate)>dateDay(p.asOf))throw Error('Evidence date cannot be after the as-of date');
  if(t.evidenceStatus!=='Unverified'&&(!t.evidence?.trim()||!t.evidenceDate))throw Error('Documented/confirmed evidence needs a reference and date');
  if(t.status==='Complete'){
   if(!t.actualFinish||!t.evidence?.trim()||!t.evidenceDate||t.evidenceStatus==='Unverified')throw Error('Completion requires actual finish, dated evidence and a documented/confirmed status');
   if(dateDay(t.actualFinish)>dateDay(p.asOf))throw Error('Actual finish cannot be after the as-of date');
  }
 }
 const ordered=[],done=new Set(),visiting=new Set(),by=Object.fromEntries(p.tasks.map(t=>[t.id,t]));
 function visit(id){if(visiting.has(id))throw Error('Circular task dependencies');if(done.has(id))return;visiting.add(id);by[id].deps.forEach(visit);visiting.delete(id);done.add(id);ordered.push(by[id]);}
 p.tasks.forEach(t=>visit(t.id));
 for(const t of p.tasks)if(t.status==='Complete')for(const d of t.deps){if(by[d].status!=='Complete'||dateDay(by[d].actualFinish)>dateDay(t.actualFinish))throw Error('Completed tasks need completed predecessors dated no later than their finish');}
 // Full capacity must actually follow first capacity in the dependency graph.
 function ancestors(id,s=new Set()){for(const d of by[id].deps){if(!s.has(d)){s.add(d);ancestors(d,s);}}return s;}
 if(!ancestors('full').has('first'))throw Error('Full-power milestone must depend on first power');
 return ordered;
}
function schedule(p,adjustments={}){
 const order=validateProject(p),now=dateDay(p.asOf),nodes={};
 for(const t of order){
  const pred=t.deps.map(d=>nodes[d]),depFinish=Math.max(-Infinity,...pred.map(x=>x.finish));
  const duration=Object.hasOwn(adjustments,t.id)?adjustments[t.id]:t.duration;
  if(!Number.isInteger(duration)||duration<0)throw Error('Invalid task duration adjustment');
  const start=t.status==='Complete'?dateDay(t.actualFinish):Math.max(now,t.notBefore?dateDay(t.notBefore):now,depFinish);
  const finish=t.status==='Complete'?dateDay(t.actualFinish):start+duration;
  nodes[t.id]={...t,start,finish,duration:t.status==='Complete'?0:duration,conditional:t.status==='Blocked'||pred.some(x=>x.conditional),criticalFirst:false,criticalFull:false};
 }
 function path(id,flag){const n=nodes[id];n[flag]=true;const latest=Math.max(-Infinity,...n.deps.map(d=>nodes[d].finish));if(latest>=n.start)for(const d of n.deps)if(nodes[d].finish===latest)path(d,flag);}
 path('first','criticalFirst');path('full','criticalFull');
 const first=nodes.first,full=nodes.full,delta=Math.max(0,Math.ceil((first.finish-dateDay(p.baselineFirst))/30.4375));
 return {nodes,order:order.map(t=>nodes[t.id]),firstDate:iso(first.finish),fullDate:iso(full.finish),conditional:first.conditional||full.conditional,firstLateDays:Math.max(0,first.finish-dateDay(p.targetFirst)),fullLateDays:Math.max(0,full.finish-dateDay(p.targetFull)),financeDelay:delta,blocked:order.filter(t=>t.status==='Blocked').length,unverified:order.filter(t=>t.evidenceStatus==='Unverified').length};
}
function advice(p){const s=schedule(p),out=[];
 for(const t of s.order){if(t.status==='Complete')continue;
  const critical=t.criticalFirst||t.criticalFull;
  if(t.status==='Blocked')out.push({priority:critical?1:2,task:t.id,title:'Resolve blocker: '+t.name,reason:'An unresolved blocker makes downstream dates conditional.'+(t.notes?' Recorded blocker: '+t.notes:''),action:'Record the missing decision or document, contact the accountable owner, and enter a realistic remaining duration after resolution.',days:null});
  if(critical&&t.duration>0){const reduction=Math.min(30,Math.ceil(t.duration*.25)),alt=schedule(p,{[t.id]:Math.max(0,t.duration-reduction)}),days=dateDay(s.firstDate)-dateDay(alt.firstDate),fullDays=dateDay(s.fullDate)-dateDay(alt.fullDate);if(days>0||fullDays>0)out.push({priority:3,task:t.id,title:'Test acceleration: '+t.name,reason:`A hypothetical ${reduction}-day reduction moves first power ${days} days and full power ${fullDays} days earlier in this dependency model.`,action:'Validate whether parallel review, a complete submission, a revised scope or expedited delivery is available. No acceleration is assumed approved.',days,fullDays,reduction});}
  if(t.evidenceStatus==='Unverified'&&critical)out.push({priority:4,task:t.id,title:'Validate schedule evidence: '+t.name,reason:'A critical-path duration is a planning assumption.',action:'Obtain a dated utility, agency, consultant or supplier reference and confirm its scope.',days:null});
  if(t.due&&dateDay(t.due)<dateDay(p.asOf))out.push({priority:2,task:t.id,title:'Overdue action: '+t.name,reason:'The recorded due date has passed.',action:'Confirm status with '+(t.owner||'an assigned owner')+' and update the remaining duration and evidence.',days:null});
 }
 if(p.route==='colocation')out.unshift({priority:1,task:'asset',title:'Validate the right to use the energy',reason:'Adjacent generation is not a confirmed supply entitlement.',action:'Confirm existing offtake, dependable hourly supply, service rights and required utility/ISO approvals before treating the asset as usable power.',days:null});
 return out.sort((a,b)=>a.priority-b.priority);
}
function validateAsset(a){
 if(!a||typeof a.id!=='string'||!a.id.trim()||typeof a.name!=='string'||!a.name.trim())throw Error('Asset needs an ID and name');
 if(!['Curtailed renewables','Existing generation','Stranded gas','Industrial / brownfield'].includes(a.type))throw Error('Unsupported energy opportunity type');
 for(const k of ['nameplateMW','surplusMW','dependableMW','contractableMW','hours','firstMonths','firmingCost','energyCost','infraCapex','fiberKm'])if(!Number.isFinite(a[k])||a[k]<0)throw Error('Invalid asset field: '+k);
 if(a.hours>8760||a.contractableMW>a.surplusMW||a.dependableMW>a.surplusMW||a.surplusMW>a.nameplateMW)throw Error('Check nameplate / surplus / dependable / contractable MW and annual hours');
 for(const k of ['land','fiber','cooling','rights'])if(!['Unknown','Needs work','Confirmed'].includes(a[k]))throw Error('Invalid readiness status');
 if(!['Unverified','Documented','Confirmed'].includes(a.evidenceStatus))throw Error('Invalid asset evidence status');
 if(a.evidenceStatus!=='Unverified'&&(!a.source?.trim()||!a.sourceDate))throw Error('Asset evidence needs a dated source reference');if(a.sourceDate)dateDay(a.sourceDate);
 if(!['Continuous','Flexible'].includes(a.workload))throw Error('Invalid workload type');
 return a;
}
function screen(a,req){validateAsset(a);if(!['Continuous','Flexible'].includes(req.workload))throw Error('Invalid discovery workload');if(!Number.isFinite(req.mw)||req.mw<=0||!Number.isFinite(req.maxMonths)||req.maxMonths<0)throw Error('Invalid discovery requirements');
 const usable=Math.min(a.dependableMW,a.contractableMW),flex=Math.min(a.surplusMW,a.contractableMW);
 const fitMW=req.workload==='Flexible'?flex:usable,coverage=Math.min(1,fitMW/req.mw),blockers=[],gaps=[];
 if(fitMW<req.mw)blockers.push(`Only ${fitMW} MW ${req.workload==='Flexible'?'potentially contractable surplus':'dependable and contractable supply'} against ${req.mw} MW required`);
 if(a.firstMonths>req.maxMonths)blockers.push('Estimated first-power timing exceeds the requested window');
 for(const k of ['land','fiber','cooling','rights'])if(a[k]!=='Confirmed')gaps.push(k+': '+a[k].toLowerCase());
 if(a.evidenceStatus==='Unverified')gaps.push('Power availability and timing lack documented evidence');
 if(a.hours<8760&&req.workload==='Continuous')gaps.push('Intermittent / limited-hour energy: validate a complete firming configuration');
 // Explicit heuristic used only to triage; not a probability or power-flow model.
 const readiness=['land','fiber','cooling','rights'].filter(k=>a[k]==='Confirmed').length/4;
 const time=Math.max(0,1-a.firstMonths/Math.max(req.maxMonths*2,1));
 const confidence={Unverified:0,Documented:.5,Confirmed:1}[a.evidenceStatus];
 const score=Math.round(45*coverage+25*time+20*readiness+10*confidence);
 return {asset:a,fitMW,coverage,score,blockers,gaps,cost:a.energyCost+a.firmingCost,verdict:blockers.length?'Gap to requirements':gaps.length?'Diligence required':'Ready for detailed study'};
}
function screenAll(assets,req){if(!Array.isArray(assets)||assets.length>1000)throw Error('Import at most 1,000 opportunities');const ids=new Set();for(const a of assets){if(ids.has(a.id))throw Error('Duplicate opportunity ID');ids.add(a.id);}return assets.map(a=>screen(a,req)).sort((a,b)=>a.blockers.length-b.blockers.length||b.score-a.score||a.cost-b.cost);}
const api={freshProject,validateProject,schedule,advice,validateAsset,screen,screenAll,dateDay,iso,add,STATUSES};if(typeof module!=='undefined')module.exports=api;root.PowerDevelopment=api;
})(typeof globalThis!=='undefined'?globalThis:this);
