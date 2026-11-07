from playwright.sync_api import sync_playwright
from pathlib import Path
f=Path(__file__).parent/'PowerPath.html'
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for w,h in [(1440,900),(390,844)]:
  page=browser.new_page(viewport={'width':w,'height':h});errors=[]
  page.on('pageerror',lambda e: errors.append(str(e)))
  page.set_content(f.read_text(),wait_until='load',timeout=120000)
  result=page.evaluate('''() => {
   const cache={};Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:(k)=>cache[k]||null,setItem:(k,v)=>cache[k]=v}});
   const node=document.createElement('section');node.style.padding='16px';document.body.append(node);
   PowerPathUnderwrite25.render(node,{id:'audit-smoke-2582'});
   const output=node.querySelector('#v251Output')?.textContent||'';
   const initial={ hasPolicy:!!node.querySelector('[data-v25s="refinanceTenorPolicy"]'),hasWarnings:output.includes('Model assurance'),hasScenario:output.includes('Scenario NPV'),hasErrors:output.includes('Cannot underwrite')};
   node.querySelector('[data-v25s="leaseExpiryPolicy"]').value='renew';
   node.querySelector('[data-v25s="exitValuePolicy"]').value='contracted';
   node.querySelector('[data-v25s="refinanceTenorPolicy"]').value='leaseTail';
   node.querySelector('#v251Run').click();
   return {...initial, after:node.querySelector('#v251Output')?.textContent.slice(0,250),xoverflow:document.documentElement.scrollWidth-window.innerWidth};
  }''')
  page.screenshot(path=f'/mnt/data/PowerPath_v25_8_2_preview_{w}.png',full_page=False)
  print(w,result,'errors=',errors)
  assert not errors and result['hasPolicy'] and result['hasWarnings'] and result['hasScenario'] and not result['hasErrors'] and result['xoverflow']<=1,result
  browser.close() if False else None
  page.close()
 browser.close()
