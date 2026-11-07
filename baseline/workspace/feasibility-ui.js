/* v19: live screening overlay, without changing historical model outputs. */
(function(){
const FZ=PowerFeasibility;let evidence={grid:'Unverified',air:'Unverified',gas:'Unverified',equipment:'Unverified'};
let limits={carbonCap:400,maxUnservedMWh:0,maxDelayMonths:36};
const names={grid:'Grid only',onsite:'Onsite engines',hybrid:'Grid + engines + battery'};
const money=x=>!Number.isFinite(x)?'—':(x<0?'−':'')+'$'+(Math.abs(x)/1e6).toFixed(1)+'M';
function renderV19(){const host=document.querySelector('#model');if(!host)return;
let panel=document.querySelector('#v19Panel');if(!panel){panel=document.createElement('section');panel.id='v19Panel';panel.className='panel spacer';host.appendChild(panel);}
const p=dev.projects.find(x=>x.id===MPID);const sp=specFor(p.id);
panel.innerHTML=`<div class="ph"><h2>v19 · Deliverable power decision</h2><span class="small">Evidence-gated comparison · model screening, not permit approval</span></div>
<p class="small">Compare identical IT load, PUE, rent and hold assumptions. Regional prices retain v18’s scaled ERCOT shape. Unverified rights are never treated as approved. Energy dispatch uses a rotating 1-in-3 day screening sample.</p>
<div class="mgrid">${[['grid','Utility / interconnection'],['air','Air permit'],['gas','Firm gas supply'],['equipment','Engine delivery']].map(([k,l])=>`<label>${l}<select data-v19="${k}">${['Unverified','Confirmed','Denied'].map(q=>`<option ${evidence[k]===q?'selected':''}>${q}</option>`).join('')}</select></label>`).join('')}
<label>Carbon ceiling (kg CO₂/MWh)<input type="number" data-v19="carbonCap" min="0" max="2000" step="10" value="${limits.carbonCap}"></label>
<label>Allowed unmet energy (MWh)<input type="number" data-v19="maxUnservedMWh" min="0" step="100" value="${limits.maxUnservedMWh}"></label>
<label>Power deadline (month)<input type="number" data-v19="maxDelayMonths" min="0" max="240" value="${limits.maxDelayMonths}"></label></div>
<div id="v19Results"><p class="small">Evaluating alternatives…</p></div>
<p class="small"><b>Decision rule:</b> Blocked scenarios cannot win. Conditional scenarios are displayed for diligence, but are not recommended as executable. Only Feasible scenarios receive winners. An unverified permit or gas contract is not evidence of availability.</p>`;
const update=()=>{const box=panel.querySelector('#v19Results');try{const data=FZ.compare(PowerEngine,HOURLY,sp,evidence,limits,{stride:3}),w=FZ.winners(data);box.innerHTML=`<div class="table-wrap"><table><thead><tr><th>Strategy</th><th>Decision</th><th>First full-service</th><th>$/MWh</th><th>kg/MWh</th><th>NPV</th><th>Unserved GWh</th></tr></thead><tbody>${data.map(x=>`<tr><td><b>${names[x.kind]}</b></td><td><b class="${x.gate.status==='Feasible'?'positive':x.gate.status==='Blocked'?'negative':''}">${x.gate.status}</b></td><td>${x.fin.powerOn==null?'—':'M'+x.fin.powerOn}</td><td>${x.fin.cost==null?'—':'$'+x.fin.cost.toFixed(1)}</td><td>${x.fin.kg==null?'—':x.fin.kg.toFixed(0)}</td><td>${money(x.fin.npv)}</td><td>${(x.fin.unserved/1e6).toFixed(2)}</td></tr><tr><td colspan="7"><small>${x.gate.reason.join(' · ')||'All selected feasibility gates cleared (based solely on user-entered evidence)'}</small></td></tr>`).join('')}</tbody></table></div><p><b>Winners among feasible strategies:</b> Cheapest: ${w.cost?names[w.cost]:'None'} · Fastest: ${w.speed?names[w.speed]:'None'} · Cleanest: ${w.carbon?names[w.carbon]:'None'} · Highest NPV: ${w.npv?names[w.npv]:'None'}</p>`;}catch(err){box.textContent='Comparison error: '+err.message;}};
panel.querySelectorAll('[data-v19]').forEach(el=>el.addEventListener('change',()=>{const k=el.dataset.v19;if(k in evidence)evidence[k]=el.value;else limits[k]=Math.max(0,Number(el.value)||0);update();}));update();}
// Retained compatibility logic; v19.2 decision workspace is canonical.
// Do not render a second comparison in the financial model.
})();
