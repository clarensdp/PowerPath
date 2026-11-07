const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();for(const w of [1440,390]){const p=await b.newPage({viewport:{width:w,height:900}});const errs=[];p.on('pageerror',e=>errs.push(e.message));await p.goto('file://'+process.argv[2]);await p.waitForTimeout(1500);
const ov=await p.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);const hasU=await p.evaluate(()=>!!(window.PowerPathUnderwrite25&&window.PowerPathUnderwrite25.evaluate({}).summary.fundingDefaultPolicy==='halt'));
console.log(w,'errors',errs.length,errs.slice(0,2),'hOverflow',ov,'patchedEngineInPage',hasU)}await b.close()})();
