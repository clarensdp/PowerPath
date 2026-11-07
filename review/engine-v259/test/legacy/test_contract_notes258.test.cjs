'use strict';
const assert=require('node:assert/strict');const {schedule,stepMonths}=require('../../src/notes.cjs');
const notes=require('../fixtures/note_terms_v258.json');const eq=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} vs ${b}`);
let n=0;
for(const t of notes){const s=schedule(t);eq(s.principalM,t.faceM);eq(s.endingM,0);eq(schedule({...t,firstPeriodAccrual:'regular'}).rows[0].couponM,t.faceM*t.couponPct/200);eq(s.rows[1].couponM,(t.faceM-s.rows[0].principalM)*t.couponPct/200);assert.equal(s.projectedContractualWaterfall,false);n++}
eq(schedule(notes[0]).issueDiscountM,70.5);// v25.8-CA: first coupons accrue from issue date on 30/360 (205, 183, 189 days)
eq(schedule(notes[0]).rows[0].couponM,2350*0.0925*205/360);
eq(schedule(notes[1]).rows[0].couponM,3507*0.09875*183/360);eq(schedule(notes[2]).rows[0].couponM,3300*0.0775*189/360);
eq(schedule(notes[2]).issueDiscountM,24.75);
const galaxy=schedule({...notes[1],firstAmortDate:'2029-02-01'});
eq(galaxy.rows.find(r=>r.date==='2029-02-01').scheduledPrincipalM,70.14);
const core=schedule({...notes[2],firstAmortDate:'2029-11-15'});
eq(core.rows.find(r=>r.date==='2029-11-15').scheduledPrincipalM,189.75);
assert.throws(()=>schedule({...notes[1],maturityDate:'2031-09-01'}),/Maturity/);
assert.equal(stepMonths('2027-08-31',6),'2028-02-29');
console.log('PASS',n,'public notes and 7 targeted coupon/OID/amort checks');
