'use strict';
// A stateless process boundary: input is JSON over stdin; output is JSON over stdout.
// Frozen v25.8.5 and v25.9-alpha financial modules are loaded unchanged.
const fs=require('node:fs');
const underwrite=require('./underwrite25.js');
// v27.1: corrected cash-constrained waterfall as a separately versioned engine. underwrite25.js stays frozen.
const underwrite27=require('./underwrite27.js');
const fixedNote27=require('./fixed_note27.cjs');
globalThis.PowerPathUnderwrite25=underwrite;
const facilities=require('./facility_waterfall259.js');
const verifiedNotes=require('./v259_verified/src/underwrite.cjs');
const risk=require('./v259_verified/src/assurance.cjs');
function sampleNotes(){
 const d=verifiedNotes.defaults();
 return {...d, ltc:0, mezzLtcPct:0, sponsorCommitmentM:3000,
  facilities:[{id:'SYNTHETIC-NOTE',name:'Illustrative Senior Note',type:'fixed_note',faceM:250,couponPct:7.5,issuePricePct:98,feePct:0,issueMonth:1,firstPaymentMonth:7,maturityMonth:115,buildings:['Building A'],priority:1,amortization:{type:'none'},dsra:{type:'fixed',amountM:15},lockupDscr:1.25,evidence:{faceM:{label:'Assumption'},couponPct:{label:'Assumption'},amortization:{label:'Assumption'}}}]};
}
const mode=process.argv[2]||'underwrite';
try{
  const input=JSON.parse(fs.readFileSync(0,'utf8'));
  let result;
  if(mode==='underwrite')result=underwrite.evaluate(input);
  else if(mode==='underwrite27')result=underwrite27.evaluate(input);
  else if(mode==='fixed_note27')result=fixedNote27.evaluate(input);
  else if(mode==='facilities')result=facilities.evaluate(input);
  else if(mode==='notes_v259'){
    // Source-preserved, regression-tested mathematics; Risk is evaluated by the server with NO self-asserted executed evidence.
    // Run payload cannot unlock lender assurance, even if it contains forged evidence/review keys.
    result=verifiedNotes.evaluate(input);
    const assessment=risk.assess(result,{terms:{},documents:{},reconciliation:{}},'25.9.0-risk1');
    assessment.uses.transactionValuation='BLOCKED';
    assessment.uses.lenderCertification='BLOCKED';
    // Risk's credit-blocked screening convention must agree with the engine's facility DSCR finding.
    if(result.summary.defaulted || (result.summary.breachMonths||[]).length || (result.summary.facilityDscrBreachMonths||[]).length){
      assessment.uses.screening='BLOCKED — not a performing credit case';
      if((result.summary.facilityDscrBreachMonths||[]).length && !result.summary.defaulted){
        result.summary.financeabilityStatus='FACILITY DSCR BREACH — not a performing credit case';
      }
    }
    result.summary.risk=assessment;
    result.summary.assuranceStatus=assessment.uses.screening;
  }
  else if(mode==='defaults27')result={project:{...underwrite27.defaults(),engineVersion:'27.1.0'}};
  else if(mode==='defaults')result={project:underwrite.defaults(),facilities:facilities.sample().facilities,notes:sampleNotes()};
  else throw Error('Unknown calculation mode');
  // NaN / +/-Infinity are not valid persisted financial outputs.
  const json=JSON.stringify(result,(k,v)=>typeof v==='number'&&!Number.isFinite(v)?null:v);
  process.stdout.write(json+'\n');
}catch(err){process.stderr.write(JSON.stringify({error:err.message})+'\n');process.exitCode=2;}
