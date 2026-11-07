from pathlib import Path
p=Path(__file__).parent/'workspace'/'underwrite25.js'
s=p.read_text()
needle=" const summary={financeabilityStatus:"
assert needle in s
insert=""" // Independent red-team assurance: an arithmetic answer is NOT a financeable investment case.
 // A lease-tail mismatch, covenant breach or unrestricted sponsor funding must remain visible
 // even when the modeled equity NPV is positive. These do not authenticate legal terms.
 const modelEnd=months;
 const allCohorts=[...cohortsByBuilding.values()].flat();
 const lastLeaseEnd=allCohorts.length?Math.max(...allCohorts.map(x=>x.start+Math.max(1,...a.buildings.filter(b=>cohortsByBuilding.get(b.name).includes(x)).map(b=>b.leaseTermMonths??180)))):null;
 const creditWarnings=[];
 if(defaulted)creditWarnings.push('Modeled financing default; outputs are downside sensitivities, not performing-project valuations');
 if(covenantBreaches.length)creditWarnings.push(covenantBreaches.length+' modeled DSCR covenant breach month(s); debt service is not covenant-compliant');
 if(a.sponsorCommitmentM===null)creditWarnings.push('Sponsor funding is uncapped and not evidenced; this is a sensitivity assumption');
 if(leaseAudits.some(x=>!x.reconciled))creditWarnings.push('Contractual revenue targets are missing or do not reconcile');
 if(leaseAudits.some(x=>!x.hasDocumentReference))creditWarnings.push('At least one lease has no source reference');
 if(lastLeaseEnd!==null&&lastLeaseEnd<modelEnd&&a.exitValueM>0)creditWarnings.push('Lease expiry precedes modeled exit while positive uncontracted asset exit value remains');
 if(rows.at(-1).onlineMW<1e-7&&a.exitValueM>0)creditWarnings.push('Positive terminal sale proceeds assumed despite zero contracted operating MW at exit');
 if(rows.at(-1).unfundedGapM>1e-8)creditWarnings.push('Unfunded cash or unpaid operating obligations remain at exit');
 creditWarnings.push('Fixed-rate transaction notes, utility service rights and lender-specific cash waterfalls are not contract-integrated');
 const screeningReadiness=(defaulted||covenantBreaches.length>0)?'BLOCKED — not a performing credit case':'CONDITIONAL — scenario screening only';
"""
s=s.replace(needle, insert+needle,1)
needle2="leaseAudits,leaseReconciliationBlocked:"
assert needle2 in s
s=s.replace(needle2,"leaseAudits,screeningReadiness,creditWarnings,lastLeaseEndMonth:lastLeaseEnd,leaseReconciliationBlocked:",1)
needle3="node.querySelector('#v251Output').innerHTML=`<h3>Contract-value reconciliation</h3>"
assert needle3 in s
s=s.replace(needle3,"node.querySelector('#v251Output').innerHTML=`<h3>Model assurance: ${escapeHtml(s.screeningReadiness)}</h3><p class=\"v21-muted\"><strong>Scenario analysis only.</strong> Outputs are not contract-verified project returns or debt capacity. ${s.creditWarnings.map(escapeHtml).join(' • ')}</p><h3>Contract-value reconciliation</h3>",1)
s=s.replace("['Levered NPV','$'+fmt(s.npvM)+'M']","['Scenario NPV (unverified)','$'+fmt(s.npvM)+'M']",1)
s=s.replace("['Levered IRR',s.leveredIRR", "['Scenario IRR (unverified)',s.leveredIRR",1)
p.write_text(s)
