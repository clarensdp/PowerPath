/* Enterprise shell: navigation, command bar, theme, status bar, Overview launchpad.
   Reads finance (app.js), development (development-ui.js) and site (intel.js) state; changes no model logic. */
const VIEWS_ALL=['overview','sites','discover','connection','model','evidence','compare','stress','help','decision','connectors','project','diligence','finance259'];const FKEYS=['overview','sites','discover','connection','model','evidence','decision','project'];
const VIEW_NAMES={model:'Underwrite · Project model',overview:'Overview',sites:'Find · Site map',discover:'Find · Energy opportunities',connection:'Plan · Connection plan',compare:'Underwrite · Power plans',stress:'Underwrite · Scenarios',evidence:'Data & method',help:'Help & walkthrough',decision:'Decide · Power delivery',connectors:'Data connectors',project:'Project · Operating system',diligence:'Project · Evidence & documents',finance259:'Finance · Debt facilities (alpha)'};
const DEV_VIEWS=['overview','sites','discover','connection','model','evidence','decision','project','diligence','finance259'];
switchView=function(id){
 if(!VIEWS_ALL.includes(id))id='overview';
 try{const active=typeof dev!=='undefined'?dev.projects.find(p=>p.id===dev.projectId):null;if(active){document.getElementById('ctxProjectName').textContent=active.name||'Active project';document.getElementById('ctxProjectDetail').textContent=(active.requiredMW??'?')+' MW requested · '+(active.route||'development')+' · Power and legal rights unverified';}}catch(e){}
 for(const b of document.querySelectorAll('[data-tab]')){const on=b.dataset.tab===id;b.classList.toggle('active',on);b.setAttribute('aria-selected',on?'true':'false');}
 for(const v of VIEWS_ALL)$('#'+v).classList.toggle('hide',v!==id);
 const isDev=DEV_VIEWS.includes(id);
 document.querySelector('.layout').classList.toggle('developmentMode',isDev);
 document.querySelector('.sidebar').classList.toggle('hide',isDev);
 $('#recommendation').classList.toggle('hide',isDev);$('#metrics').classList.toggle('hide',isDev);
 $('#memo').onclick=isDev?$('#exportDevelopmentMemo').onclick:financialMemoHandler;
 $('#crumb').textContent=VIEW_NAMES[id];
 if(id==='project'&&typeof renderProject21==='function')renderProject21();if(id==='diligence'&&window.PowerPathDiligence)PowerPathDiligence.render();if(id==='overview')renderOverview();if(id==='connectors'&&window.PowerPathConnectors)PowerPathConnectors.render();if(id==='decision'&&typeof renderDecision==='function')renderDecision();
 if(id==='finance259'&&window.PowerPathFacilities259)PowerPathFacilities259.render();if(id==='sites'&&typeof renderSites==='function')renderSites();if(id==='model'&&typeof renderModel==='function'){MPID=MPID||dev.projectId;renderModel();}
 try{localStorage.setItem('pp_view',id);}catch{}
 const m=$('#main');if(m)m.scrollTop=0;
};
function ovStatus(kind,text){return `<span class="status ${kind}"><i></i>${esc(text)}</span>`;}
function monthDate(asOf,m){const d=new Date((asOf||new Date().toISOString().slice(0,10))+'T00:00:00Z');d.setUTCMonth(d.getUTCMonth()+m);return d.toISOString().slice(0,10);}
function renderOverview(){
 if(!$('#ovKpis')||typeof siteEcon!=='function')return;
 const projs=dev.projects.map(p=>({p,s:D.schedule(p),ad:D.advice(p),site:linkedSite(p),f:projectEval(p.id).fin}));
 const mw=projs.reduce((t,x)=>t+(+x.p.requiredMW||0),0),totNpv=projs.reduce((t,x)=>t+x.f.npv,0);
  const powerAtRisk=projs.filter(x=>x.f.unservedH>24||x.s.unverified>0||x.s.blocked>0).reduce((t,x)=>t+(+x.p.requiredMW||0),0);
 const earliest=projs.slice().sort((x,y)=>x.s.firstDate.localeCompare(y.s.firstDate))[0];
 const w=watchItems(projs),urgent=w.items.filter(i=>i[0]==='p1').length;
 $('#ovKpis').innerHTML=[
  ['Pipeline',`${mw.toLocaleString()} MW`,`${projs.length} project${projs.length===1?'':'s'}`],
  ['Earliest first power',earliest?earliest.s.firstDate:'–',earliest?esc(earliest.p.name):''],
  ['MW needing verification',`${powerAtRisk.toLocaleString()} MW`,'Unverified schedule, rights or model shortfalls',powerAtRisk>0?'negative':''],
  ['Decisions / actions',String(w.items.length),urgent?`<span class="negative">${urgent} urgent</span>`:'none urgent']
 ].map(([l,v,s,c])=>`<div><small>${l}</small><b class="${c||''}">${v}</b><span>${s}</span></div>`).join('');
 $('#ovPipeline').innerHTML=table(['Project','Market','First power','Cost of power','NPV','Unserved'],projs.map(x=>[
  `<b>${esc(x.p.name)}</b><br><small>${x.p.requiredMW} MW · ${x.p.route==='colocation'?'co-location':'site-first'}</small>`,
  x.site?`${esc(x.site.name)}<br><small>${esc(x.site.grid)}</small>`:'<small>Not linked</small>',
  (()=>{const md=x.f.powerOn!=null?monthDate(x.p.asOf,x.f.powerOn):null,gap=md?Math.round((Date.parse(md)-Date.parse(x.s.firstDate))/864e5):0;return `${x.s.firstDate}<br><small>${x.s.firstLateDays?`<span class="negative">${x.s.firstLateDays} d late</span>`:'on target'}${md&&Math.abs(gap)>60?` · <span class="negative" title="The project model's power-on month differs from the connection plan">model ${md.slice(0,7)}</span>`:''}</small>`;})(),
  x.f.cost?'$'+x.f.cost.toFixed(1)+'<br><small>per MWh</small>':'–',
  `<span>${money(x.f.npv)}</span><br><small>Scenario only · ${fmtPct(x.f.irr)} IRR</small>`,
  x.f.unservedH>24?`<span class="negative">${Math.round(x.f.unservedH).toLocaleString()} h</span>`:'<span class="positive">none</span>']),projs.map(x=>x.p.id===dev.projectId?'selected clk':'clk'));
 $('#ovPipeline').querySelectorAll('tbody tr').forEach((tr,i)=>{tr.tabIndex=0;tr.dataset.ovproj=projs[i].p.id;});
 $('#ovWatchN').textContent=w.items.length>4?`top 4 of ${w.items.length}`:'';
 $('#ovWatch').innerHTML=w.items.length?w.items.slice(0,4).map(([p,t,d,pid])=>`<div class="qitem"><span class="prio ${p}">${p.toUpperCase()}</span><div><b>${esc(t)}</b><span>${esc(d)}</span></div>${pid?`<button data-ovproj="${esc(pid)}">Open</button>`:'<span></span>'}</div>`).join('')+w.changes:'<p class="small">Nothing needs attention.</p>'+w.changes;
 const econ=allSiteEcon().filter(r=>Number.isFinite(r.e.breakRent)).sort((x,y)=>x.e.breakRent-y.e.breakRent).slice(0,5);
 $('#ovMarkets').innerHTML=table(['State','Power on','Cost of power','Carbon','Break-even rent'],econ.map(r=>[`<b>${esc(r.s.name)}</b><br><small>${esc(r.s.grid)}</small>`,'M'+r.e.open,'$'+r.e.cost.toFixed(1),(r.e.kg!=null?Math.round(r.e.kg):'–')+' kg','<b>$'+r.e.breakRent.toFixed(0)+'</b>']),econ.map(()=>'clk'));
 $('#ovMarkets').querySelectorAll('tbody tr').forEach((tr,i)=>{tr.tabIndex=0;tr.dataset.site=econ[i].s.ab;});
 const scr=D.screenAll(dev.assets,dev.requirements).sort((x,y)=>y.score-x.score).slice(0,4);
 $('#ovOpps').innerHTML=scr.length?table(['Opportunity','Fit MW','Power in','Score'],scr.map(r=>[`<b>${esc(r.asset.name)}</b><br><small>${esc(r.asset.type)}${/fictional|illustrative/i.test(r.asset.name+r.asset.region+r.asset.source)?' · demo record':''}</small>`,r.fitMW,`${r.asset.firstMonths} mo`,`<b>${r.score}</b>`]),scr.map(()=>'clk')):'<p class="small">No opportunities yet. Add plants from the site map or import a dataset.</p>';
 $('#ovOpps').querySelectorAll('tbody tr').forEach((tr,i)=>{tr.tabIndex=0;tr.dataset.ovasset=scr[i].asset.id;});
 const p=project();if(p)$('#asof').textContent='AS OF '+p.asOf;
 if(typeof decisionBadge==='function')document.querySelectorAll('#ovPipeline tbody tr').forEach((tr,i)=>{let cell=tr.querySelector('td:first-child');if(cell)cell.insertAdjacentHTML('beforeend',decisionBadge(projs[i].p));});
}
function openProject(pid,taskId){dev.projectId=pid;dev.taskId=taskId||'study';renderDev();switchView('connection');}
document.addEventListener('click',e=>{
 const pr=e.target.closest('[data-ovproj]');if(pr){openProject(pr.dataset.ovproj);return;}
 const tk=e.target.closest('[data-ovtask]');if(tk){openProject(tk.dataset.ovpid,tk.dataset.ovtask);setTimeout(()=>$('#taskEditor').scrollIntoView({behavior:'smooth',block:'start'}),50);return;}
 const mk=e.target.closest('#ovMarkets tr[data-site]');if(mk){selectSite(mk.dataset.site);switchView('sites');return;}
 const as=e.target.closest('[data-ovasset]');if(as){dev.assetId=as.dataset.ovasset;renderDev();switchView('discover');}
});
document.addEventListener('keydown',e=>{
 const r=e.target.closest&&e.target.closest('tr[data-ovproj],tr[data-ovasset],tr[data-site]');if(r&&e.key==='Enter'){r.click();return;}
 const typing=/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
 if((e.key==='/'&&!typing)||((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k')){e.preventDefault();$('#cmd').focus();$('#cmd').select();return;}
 const f=['F1','F2','F3','F4','F5','F6'].indexOf(e.key);if(f>=0){e.preventDefault();switchView(FKEYS[f]);}
});
const CODES={OVR:'overview',OVERVIEW:'overview',HOME:'overview',HELP:'help',GUIDE:'help',STRATEGY:'decision',STRATEGIES:'decision',DECIDE:'decision',DECISION:'decision',PROJECT:'project',WORKSPACE:'project',MAP:'sites',SITES:'sites',FIND:'sites',ORIG:'discover',OPP:'discover',DISC:'discover',CONN:'connection',PLAN:'connection',ECON:'model',MODEL:'model',UNDERWRITE:'model',SCEN:'model',WHAT:'model',DATA:'evidence',EVID:'evidence',METHOD:'evidence'};
$('#cmdform').addEventListener('submit',e=>{e.preventDefault();const q=$('#cmd').value.trim();if(!q)return;const up=q.toUpperCase(),lq=q.toLowerCase();
 if(CODES[up]){switchView(CODES[up]);$('#cmd').value='';return;}
 const st=SITES.sites.find(s=>s.ab===up||s.name.toLowerCase()===lq)||SITES.sites.find(s=>s.name.toLowerCase().startsWith(lq));if(st){selectSite(st.ab);switchView('sites');$('#cmd').value='';return;}
 const pj=dev.projects.find(p=>p.name.toLowerCase().includes(lq));if(pj){openProject(pj.id);$('#cmd').value='';toast('Opened '+pj.name);return;}
 const as=dev.assets.find(x=>(x.name+' '+x.region+' '+x.type).toLowerCase().includes(lq));if(as){dev.assetId=as.id;renderDev();switchView('discover');$('#cmd').value='';toast('Opened '+as.name);return;}
 toast('No module, state, project or opportunity matches "'+q+'"');});
function setTheme(t){document.documentElement.dataset.theme=t;const b=$('#theme');if(b)b.textContent=t==='dark'?'Light':'Dark';try{localStorage.setItem('pp_theme',t);}catch{}}
try{setTheme(localStorage.getItem('pp_theme')||'light');}catch{setTheme('light');}
$('#theme').onclick=()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');
const _renderDev=renderDev;renderDev=function(){_renderDev();try{renderOverview();}catch(e){}};
const _renderFin=render;render=function(){_renderFin();try{renderOverview();if(!$('#sites').classList.contains('hide'))renderSites();}catch(e){}};
const _saveDev=saveDev;saveDev=function(){_saveDev();const el=$('#sbSaved');if(el)el.textContent='Saved locally '+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});};
function tick(){const el=$('#sbClock');if(el)el.textContent=new Date().toLocaleString([],{weekday:'short',hour:'2-digit',minute:'2-digit'});}
tick();setInterval(tick,30000);

/* v19.1 action routing: no duplicated navigation state */
function ppOpenStrategies(){switchView('decision');}
document.addEventListener('click',e=>{const b=e.target.closest('[data-pp-action]');if(!b)return;const a=b.dataset.ppAction;
 if(a==='strategies'){ppOpenStrategies();return;}
 if(a==='guide'){switchView('help');return;}
 if(a==='save-case'){document.querySelector('#save').click();return;}
 if(a==='new-project'){const btn=document.querySelector('#newGridProject');if(!btn)return;btn.click();switchView('connection');return;}
});

// v20 standalone connector workspace navigation
document.addEventListener("click", e=>{const b=e.target.closest("[data-tab=connectors]");if(b){setTimeout(()=>{try{PowerPathConnectors.render()}catch(err){console.error(err)}},0)}});
