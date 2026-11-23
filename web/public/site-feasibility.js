const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = value => value == null ? '—' : Number(value).toLocaleString(undefined,{maximumFractionDigits:2});
const field = (label,name,value='',type='number') => `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" ${type==='number'?'step="any"':''}></label>`;
const source = (url,label) => /^https?:\/\//i.test(url || '') ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label || url)}</a>` : esc(label || 'Source unavailable');
const month = value => value == null ? 'Outside model horizon' : 'M'+value;

export function createSiteFeasibility({api,selection,onChange}) {
  let layer, layerMap, request = 0;
  const projectPath = pid => '/projects/'+encodeURIComponent(pid)+'/site-feasibility';
  const parcelPath = (pid,parcel) => '/projects/'+encodeURIComponent(pid)+'/parcels28/'+encodeURIComponent(parcel)+'/feasibility';
  function clear() {
    if(layer && layerMap) layerMap.removeLayer(layer);
    layer = layerMap = null;
  }
  function draw(map,summary) {
    clear();
    if(!map || !summary || !window.L) return;
    const features = ['excluded_geometry','residual_geometry'].filter(k=>summary[k]).map(k=>({
      type:'Feature',geometry:summary[k],properties:{kind:k}
    }));
    layerMap=map;
    layer=L.geoJSON({type:'FeatureCollection',features},{
      interactive:false,style:f=>({color:f.properties.kind==='excluded_geometry'?'#a34227':'#25845c',fillOpacity:.28,weight:2})
    }).addTo(map);
  }
  function markup() {
    return '<section class="panel panelpad" id="connected-parcel"><h2>Parcel feasibility</h2><p>Loading saved analysis…</p></section>';
  }
  function landSummary(land) {
    if(!land) return '<p>No land assessment saved.</p>';
    const r=land.body,s=r.summary;
    return `<p><strong>${num(s.potentially_usable_acres)} ac residual</strong> of ${num(r.parcel.area_acres)} ac · ${num(s.largest_contiguous_acres)} ac largest contiguous · ${num(s.intersecting_supplied_constraints_acres)} ac excluded.</p>
      <p>${s.assessment_complete?'Full extent declared by input sources.':'Incomplete coverage. Residual is an upper bound.'} ${esc(s.incomplete_constraint_kinds.join(', '))}</p>
      <p class="nodata">Assessment v${land.version} · ${esc(land.created_at)} · green residual, rust exclusions. Preliminary GIS estimate.</p>
      <ul>${r.layers.map(l=>`<li>${source(l.source.url,l.source.title)} · ${esc(l.kind)} · ${num(l.intersection_acres)} ac · ${esc(l.coverage_status)} · ${esc(l.source.published_at || l.source.retrieved_at || 'source date unknown')}</li>`).join('')}</ul>`;
  }
  function infraSummary(infra,study) {
    return `<p>${infra?'Infrastructure captured '+esc(infra.created_at):'No infrastructure snapshot saved.'}</p>
      ${Object.entries(infra?.body.grid_infrastructure || {}).map(([kind,r])=>`<p>${esc(kind)} · ${esc(r.status)} · ${source(r.source_url,r.provider)} ${esc(r.error || '')}</p><ul>${r.features.slice(0,10).map(f=>`<li>${esc(f.properties.name)} · ${num(f.properties.distance_km)} km · ${esc(f.properties.effective_date || 'source date unknown')}${kind==='service_territory'?' · candidate provider':''}</li>`).join('')}</ul>`).join('')}
      ${study?`<p>Utility evidence · ${esc(study.issuer || 'issuer unspecified')} · ${study.source_kind==='analyst_attested_utility_confirmation'?'analyst attests utility confirmation':'documented study'} · ${source(study.source_url,study.source_date)} · ${num(study.capacity_mw)} gross MW · ${esc(study.energization_date || 'date unknown')} · $${num(study.connection_cost_usd)} connection. ${esc(study.notes)} ${esc(study.verification)}</p>`:''}`;
  }
  function caseForm(scenarios) {
    return `<form id="connected-case" class="formgrid">
      ${field('Case name','name','','text')}
      <label>Base underwriting scenario<select name="scenario_id" required>${scenarios.map(s=>`<option value="${esc(s.id)}">${esc(s.name)} v${s.version}</option>`).join('')}</select></label>
      <label class="span2">Assumption rationale<input name="rationale" required minlength="10"></label>
      <fieldset class="span2"><legend><label><input type="checkbox" name="grid" checked> Grid</label></legend><div class="formgrid">
        <label>Cumulative gross MW (month, MW per line)<textarea name="phases" placeholder="20,32.5&#10;30,65&#10;36,97.5"></textarea></label>
        <label><input type="checkbox" name="study"> Use attached utility-study capacity, cost and date</label>
        ${field('Grid price USD/MWh (blank uses saved scenario)','price')}
        ${field('Connection and upgrade cost $M','connection',0)}
        ${field('Grid emissions kg CO₂/MWh (optional)','gridco2')}
        ${field('Extra delivery delay in months','grid_delay',0)}
      </div></fieldset>
      <fieldset class="span2"><legend><label><input type="checkbox" name="gas"> Onsite gas</label></legend><div class="formgrid">
        ${field('Net installed gross MW','gas_mw')}${field('Commissioning month','gas_month')}
        ${field('Net efficiency (fraction)','efficiency')}${field('Fuel USD/MMBtu','fuel')}
        ${field('Combustion kg CO₂/MMBtu','gasco2')}${field('Gas capital cost $M','gas_capex')}
        ${field('Gas variable O&M USD/MWh','gas_variable')}${field('Gas fixed O&M $M/year','gas_fixed',0)}
      </div></fieldset>
      <fieldset class="span2"><legend><label><input type="checkbox" name="solar"> Solar</label></legend><div class="formgrid">
        ${field('Installed DC kW','solar_kw')}${field('Commissioning month','solar_month')}
        ${field('Solar capital cost $M','solar_capex')}${field('Solar fixed O&M $M/year','solar_fixed')}
        ${field('Tilt degrees','tilt',20)}${field('Azimuth degrees','azimuth',180)}${field('Losses %','losses',14)}
        <label>Jan–Dec MWh (comma separated, blank requests PVWatts)<textarea name="solar_profile"></textarea></label>
      </div></fieldset>
      <button class="primary" ${scenarios.length?'':'disabled'}>Save and calculate case</button><button type="button" id="case-new" hidden>Cancel edit</button>
    </form>`;
  }
  function payload(form) {
    const d=Object.fromEntries(new FormData(form));
    const number=k=>d[k]==='' ? null : Number(d[k]);
    const phases=d.phases.trim().split(/\n/).filter(Boolean).map(line=>{
      const parts=line.split(',');
      if(parts.length!==2 || parts.some(x=>!x.trim())) throw Error('Enter one month, MW pair per line.');
      return {month:Number(parts[0]),mw:Number(parts[1])};
    });
    return {name:d.name,scenario_id:d.scenario_id,rationale:d.rationale,
      grid:d.grid?{phases:d.study?[]:phases,use_utility_study:!!d.study,price_mwh:number('price'),connection_cost_m:number('connection'),
        emissions_kg_mwh:number('gridco2'),delay_months:number('grid_delay')}:null,
      gas:d.gas?{mw:number('gas_mw'),month:number('gas_month'),efficiency:number('efficiency'),fuel_usd_mmbtu:number('fuel'),
        emissions_kg_mmbtu:number('gasco2'),capex_m:number('gas_capex'),variable_opex_mwh:number('gas_variable'),fixed_opex_year_m:number('gas_fixed')}:null,
      solar:d.solar?{system:{capacity_kw:number('solar_kw'),tilt:number('tilt'),azimuth:number('azimuth'),losses_pct:number('losses')},
        month:number('solar_month'),capex_m:number('solar_capex'),fixed_opex_year_m:number('solar_fixed'),
        monthly_mwh:d.solar_profile.trim()?d.solar_profile.split(',').map(x=>x.trim()?Number(x):NaN):null}:null};
  }
  function fill(form,c) {
    const b=c.body,g=b.grid,a=b.gas,s=b.solar;
    const fields={name:b.name,scenario_id:b.scenario_id,rationale:b.rationale,grid:!!g,study:!!g?.use_utility_study,
      phases:g?.phases.map(p=>p.month+','+p.mw).join('\n'),price:g?.price_mwh,connection:g?.connection_cost_m,
      gridco2:g?.emissions_kg_mwh,grid_delay:g?.delay_months,gas:!!a,gas_mw:a?.mw,gas_month:a?.month,
      efficiency:a?.efficiency,fuel:a?.fuel_usd_mmbtu,gasco2:a?.emissions_kg_mmbtu,gas_capex:a?.capex_m,
      gas_variable:a?.variable_opex_mwh,gas_fixed:a?.fixed_opex_year_m,solar:!!s,solar_kw:s?.system.capacity_kw,
      solar_month:s?.month,solar_capex:s?.capex_m,solar_fixed:s?.fixed_opex_year_m,tilt:s?.system.tilt??20,
      azimuth:s?.system.azimuth??180,losses:s?.system.losses_pct??14,solar_profile:s?.monthly_mwh?.join(',')};
    for(const [key,value] of Object.entries(fields)){
      const el=form.elements[key];
      if(el.type==='checkbox')el.checked=value;
      else el.value=value??'';
    }
  }
  function caseSummary(c, detailed=false) {
    const r=c.result;
    return `<article class="case-result"><h4>${esc(c.body.name)} · ${esc(c.status)}</h4><p>${['grid','gas','solar'].filter(k=>c.body[k]).join(' + ')} · ${esc(c.body.rationale)}</p>
      ${r?`<p>Operations ${month(r.first_operation_month)} / full ${month(r.full_operation_month)} · NPV $${num(r.finance.npvM)}M · IRR ${num(r.finance.leveredIRR==null?null:r.finance.leveredIRR*100)}% · min DSCR ${num(r.finance.minDSCR)} · power capex $${num(r.power_capex_m)}M · power O&M $${num(r.opex_usd)}.</p>
      <p>Target ${num(r.target_it_mw)} IT MW · PUE ${num(r.pue)} · grid price $${num(r.grid_price_mwh)}/MWh · calculated ${esc(c.run_date)}.</p>
      ${r.totals?`<p>Grid ${num(r.totals.grid_mwh)} MWh · gas ${num(r.totals.gas_mwh)} MWh · solar ${num(r.totals.solar_mwh)} MWh · unmet full-target demand ${num(r.totals.unmet_mwh)} MWh · direct CO₂ ${num(r.totals.direct_co2_tonnes)} t · grid CO₂ ${r.totals.grid_co2_tonnes==null?'unknown':num(r.totals.grid_co2_tonnes)+' t'}.</p>`:''}
      <p class="nodata">${esc(r.limitations.join(' '))}</p>`:''}
      ${detailed && r?`<p>Firm gross MW by project month: ${r.engine_inputs.powerCapacityAssumptions.phases.map(p=>`M${p.month} · ${num(p.mw)} MW`).join(', ') || 'none'}.</p>
      <ul>${Object.entries(c.body).filter(([k,v])=>['grid','gas','solar'].includes(k)&&v).map(([k,v])=>`<li>${k} assumptions · ${esc(JSON.stringify(v))}</li>`).join('')}</ul>
      <p>Solar source · ${source(r.solar_source?.source_url,r.solar_source?.provider || r.solar_source?.status)} ${esc(r.solar_source?.retrieved_at || '')}. Base scenario version ${r.inputs.base_version}.</p>`:''}</article>`;
  }
  function periodTable(result) {
    if(!result?.periods)return '';
    return `<details><summary>Monthly capacity and dispatch</summary><div class="tablewrap"><table>
      <thead><tr><th>Month</th><th>Firm gross MW</th><th>Operating IT MW</th><th>Unmet target MWh</th><th>Grid MWh</th><th>Gas MWh</th><th>Solar MWh</th></tr></thead>
      <tbody>${result.periods.map(r=>`<tr><td>${r.month}</td><td>${num(r.firm_gross_mw)}</td><td>${num(r.operating_it_mw)}</td><td>${num(r.unmet_target_mwh)}</td><td>${num(r.energy_mwh.grid)}</td><td>${num(r.energy_mwh.gas)}</td><td>${num(r.energy_mwh.solar)}</td></tr>`).join('')}</tbody></table></div></details>`;
  }
  async function parcel(map) {
    const host=document.querySelector('#connected-parcel');
    if(!host)return;
    const {pid,parcel:parcelId}=selection(),id=++request,base=parcelPath(pid,parcelId);
    let editing;
    const active=()=>request===id && host.isConnected && selection().pid===pid && selection().parcel===parcelId;
    const showError=e=>{if(active())host.querySelector('[role=status]').textContent=e.message;};
    try {
      const [comparison,scenarios]=await Promise.all([api(base+'/comparison'),api('/projects/'+encodeURIComponent(pid)+'/scenarios')]);
      if(!active())return;
      const selected=comparison.parcels.find(p=>p.parcel_id===parcelId);
      if(!selected)throw Error('Shortlist this parcel before saving feasibility work.');
      draw(map,selected.land?.body.summary);
      host.innerHTML=`<h2>Parcel feasibility</h2><p role="status"></p>${landSummary(selected.land)}
        <form id="connected-land" class="formgrid"><label>Constraint layers JSON (optional)<input type="file" accept=".json,.geojson,application/json"></label>
        <label><input type="checkbox" name="official"> Include public GIS. Sends the parcel bounds and terrain sample coordinates to government GIS services.</label>
        ${field('Slope exclusion threshold %','slope',15)}<button>Save land assessment</button></form>
        <details><summary>Infrastructure evidence</summary>${infraSummary(selected.infrastructure,selected.utility_study)}</details>
        <button id="connected-infra">Capture infrastructure snapshot</button>
        <h3>Power cases for this parcel</h3>${selected.cases.map((c,i)=>caseSummary(c)+periodTable(c.result)+`<div class="actions"><button data-case-edit="${i}">Edit</button><button data-case-run="${i}">Calculate</button></div>`).join('')}
        ${caseForm(scenarios.filter(s=>s.mode==='underwrite' && s.config.engineVersion==='27.1.0' && !s.config.powerPathLink && !s.config.powerTranches?.length))}`;
      const action=(el,handler,event='click')=>el.addEventListener(event,async e=>{
        e.preventDefault();const button=e.submitter||el;button.disabled=true;
        try{await handler();if(active()){await onChange();if(active())await parcel(map);}}
        catch(error){showError(error);}
        finally{button.disabled=false;}
      });
      const form=host.querySelector('#connected-case');
      host.querySelectorAll('[data-case-edit]').forEach(b=>b.onclick=()=>{
        editing=selected.cases[Number(b.dataset.caseEdit)];fill(form,editing);form.querySelector('#case-new').hidden=false;form.scrollIntoView({block:'nearest'});
      });
      form.querySelector('#case-new').onclick=()=>{editing=null;form.reset();form.querySelector('#case-new').hidden=true;};
      host.querySelectorAll('[data-case-run]').forEach(b=>action(b,()=>api(base+'/power-cases/'+selected.cases[Number(b.dataset.caseRun)].id+'/run','POST',{})));
      action(form,async()=>{
        const body=payload(form);
        const saved=await api(base+'/power-cases'+(editing?'/'+editing.id+'?expected_version='+editing.version:''),editing?'PUT':'POST',body);
        editing=saved;
        try{await api(base+'/power-cases/'+saved.id+'/run','POST',{});}
        catch(e){form.querySelector('#case-new').hidden=false;throw Error('Case saved. Calculation needs attention. '+e.message);}
      },'submit');
      const land=host.querySelector('#connected-land');
      action(land,async()=>{
        const file=land.querySelector('[type=file]').files[0];
        if(file?.size>3_000_000)throw Error('Constraint input exceeds 3 MB.');
        const layers=file?JSON.parse(await file.text()):[];
        const official=land.elements.official.checked;
        await api(base+'/land','POST',{layers,official,consent_remote:official,slope_threshold_pct:Number(land.elements.slope.value)});
      },'submit');
      action(host.querySelector('#connected-infra'),()=>api(base+'/infrastructure','POST',{}));
    } catch(e) { if(active())host.innerHTML=`<h2>Parcel feasibility</h2><p role="status">${esc(e.message)}</p>`; }
  }

  function comparisonContent(snapshot,detailed=false) {
    return snapshot.parcels.map(p=>{
      const prop=p.feature.properties;
      return `<section class="connected-report-parcel"><h3>Parcel ${esc(prop.parcelnumb || prop.PA_MCPI || p.parcel_id)}</h3>
        <p>${source(prop.source_url,prop.source_agency || prop.source_id || 'Parcel source')} · version ${esc(p.source_version)} · source date ${esc(prop.source_document_date || 'unknown')} · retrieved ${esc(prop.retrieved_at || 'unknown')}.</p>
        <p>Analyst score ${num(p.manual_assessment.score)} · ${p.manual_assessment.coverage_pct}% coverage · ${esc(p.manual_assessment.status)} · missing factors ${esc(p.manual_assessment.missing_factors.join(', ')) || 'none'}.</p>
        <p>Outstanding evidence · ${esc(p.missing_evidence.join(' · ')) || 'none flagged'}</p>
        ${landSummary(p.land)}${infraSummary(p.infrastructure,p.utility_study)}
        ${detailed?`<ul>${p.analyst_factors.map(f=>`<li>${esc(f.factor)} · ${esc(f.gate)} · ${source(f.source_url,f.source_date)} · ${esc(f.notes)}</li>`).join('')}</ul>`:''}
        ${p.cases.map(c=>caseSummary(c,detailed)).join('')}</section>`;
    }).join('') || '<p>Shortlist parcels to begin the comparison.</p>';
  }
  function comparisonTable(snapshot) {
    if(!snapshot.parcels.length)return '';
    return `<div class="tablewrap"><table><thead><tr><th>Parcel</th><th>Usable acres / largest</th><th>Analyst score</th><th>Power case</th><th>First / full operation</th><th>NPV</th><th>Outstanding evidence</th></tr></thead>
      <tbody>${snapshot.parcels.flatMap(p=>{
        const prop=p.feature.properties,s=p.land?.body.summary;
        const cases=p.cases.length?p.cases:[null];
        return cases.map(c=>`<tr><td>${esc(prop.parcelnumb || prop.PA_MCPI || p.parcel_id)}</td>
          <td>${s?`${num(s.potentially_usable_acres)} / ${num(s.largest_contiguous_acres)}${s.assessment_complete?'':' · incomplete'}`:'Unknown'}</td>
          <td>${num(p.manual_assessment.score)} · ${p.manual_assessment.coverage_pct}% coverage</td>
          <td>${c?esc(c.body.name)+' · '+esc(c.status):'None'}</td>
          <td>${c?.result?`${month(c.result.first_operation_month)} / ${month(c.result.full_operation_month)}`:'—'}</td>
          <td>${c?.result?'$'+num(c.result.finance.npvM)+'M':'—'}</td>
          <td>${esc(p.missing_evidence.join(' · ')) || 'None flagged'}</td></tr>`);
      }).join('')}</tbody></table></div>`;
  }
  async function comparison({report=false}={}) {
    const host=document.querySelector('#connected-comparison');
    if(!host)return;
    const {pid}=selection(),base=projectPath(pid);
    const active=()=>host.isConnected && selection().pid===pid;
    try {
      const [current,reports]=await Promise.all([api(base),report?api(base+'/reports'):[]]);
      if(!active())return;
      host.innerHTML=`<h2>${report?'Parcel feasibility reports':'Parcel feasibility comparison'}</h2><p role="status"></p>
        ${report?`<div class="actions"><button id="connected-save">Save current report</button><label>Saved report<select id="connected-history"><option value="">Select a saved version</option>${reports.map(r=>`<option value="${esc(r.id)}">v${r.version} · ${esc(r.created_at)}</option>`).join('')}</select></label></div><div id="connected-snapshot"></div>`:''}
        <div class="connected-current">${comparisonTable(current)}${comparisonContent(current)}</div>`;
      const msg=host.querySelector('[role=status]');
      const show=r=>{
        if(!active())return;
        host.querySelector('#connected-snapshot').innerHTML=`<article class="report" id="connected-print"><h2>${esc(r.snapshot.project.name)} · ${num(r.snapshot.project.target_mw)} IT MW</h2><p>Report v${r.version} · ${esc(r.created_at)} · ${r.current?'Current at retrieval':'Historical snapshot — project inputs changed'}</p>
          <p>${esc(r.snapshot.limitations.join(' '))}</p>${comparisonTable(r.snapshot)}${comparisonContent(r.snapshot,true)}</article><div class="actions connected-export"><button id="connected-json">Download JSON</button><button id="connected-pdf">Print / save PDF</button></div>`;
        host.querySelector('#connected-json').onclick=()=>download(r);
        host.querySelector('#connected-pdf').onclick=()=>{
          document.body.classList.add('print-connected');
          try{window.print();}finally{document.body.classList.remove('print-connected');}
        };
      };
      const lookup=host.querySelector('#connected-history');
      if(lookup)lookup.onchange=async()=>{
        const id=lookup.value;
        if(!id){host.querySelector('#connected-snapshot').replaceChildren();return;}
        try{const r=await api(base+'/reports/'+id);if(lookup.value===id)show(r);}catch(e){msg.textContent=e.message;}
      };
      const save=host.querySelector('#connected-save');
      if(save)save.onclick=async()=>{
        save.disabled=true;
        try{
          const r=await api(base+'/reports','POST',{});
          if(active()){lookup.add(new Option('v'+r.version+' · '+r.created_at,r.id),1);lookup.value=r.id;show(r);}
        }catch(e){msg.textContent=e.message;}
        finally{save.disabled=false;}
      };
    } catch(e) { if(active())host.innerHTML=`<p role="status">${esc(e.message)}</p>`; }
  }
  function download(report) {
    const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='PowerPath_Feasibility_v'+report.version+'.json';a.click();
    setTimeout(()=>URL.revokeObjectURL(url),10000);
  }
  return {markup,parcel,comparison,clear};
}
