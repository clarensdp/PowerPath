from playwright.sync_api import sync_playwright
from pathlib import Path
pagefile=Path('/mnt/data/powerpath_v25_2/PowerPath.html')
with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  for w,h in [(1365,900),(390,844)]:
    page=browser.new_page(viewport={'width':w,'height':h})
    errors=[]
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.set_content(pagefile.read_text(),wait_until='load',timeout=120000)
    info=page.evaluate('''() => ({title:document.title,hasEngine:typeof PowerPathUnderwrite25 !== 'undefined',errors:[],width:document.documentElement.scrollWidth,inner:window.innerWidth})''')
    result=page.evaluate('''() => {let r=PowerPathUnderwrite25.evaluate({...PowerPathUnderwrite25.defaults(),tenantCapexPct:20,mezzLtcPct:10});return {npv:r.summary.npvM,refund:r.summary.refinanceSizing?.binding,residual:r.summary.sourcesUsesMaxResidual}}''')
    print(w,info,result,'PAGE_ERRORS',errors)
    assert info['hasEngine'] and not errors and info['width']<=info['inner']+1
    page.close()
  browser.close()
