from playwright.sync_api import sync_playwright
from pathlib import Path
import os
import urllib.request, urllib.error
root=Path(__file__).resolve().parent.parent
BASE=os.environ.get('POWERPATH_BROWSER_BASE','http://127.0.0.1:8768')
out=root/'previews';out.mkdir(exist_ok=True)
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('POWERPATH_CHROMIUM') or None,args=['--no-sandbox'])
 for name,w,h in [('desktop',1440,900),('tablet',1024,820),('mobile',390,844)]:
  page=browser.new_page(viewport={'width':w,'height':h})
  errs=[];page.on('pageerror',lambda e: errs.append(str(e)))
  def bridge(url,method='GET',data=None):
   req=urllib.request.Request(BASE+url,data=data.encode() if data is not None else None,method=method,headers={'Content-Type':'application/json'})
   try:
    with urllib.request.urlopen(req,timeout=25) as r: return {'status':r.status,'body':r.read().decode(),'type':r.headers.get('Content-Type','application/json')}
   except urllib.error.HTTPError as e: return {'status':e.code,'body':e.read().decode(),'type':'application/json'}
  page.expose_function('apiBridge',bridge)
  style=(root/'web/public/style.css').read_text();script=(root/'web/public/app.js').read_text()
  page.set_content('<!doctype html><html><head><meta charset="utf-8"><style>'+style+'</style></head><body><div id="app"></div></body></html>')
  page.evaluate("""(() => {window.fetch=async (url,opts={}) => {const v=await window.apiBridge(String(url),opts.method||'GET',opts.body||null);return new Response(v.body,{status:v.status,headers:{'Content-Type':v.type}})};return true})()""")
  page.add_script_tag(content=script)
  page.wait_for_selector('h1',timeout=16000)
  assert page.get_by_role('heading',name='Your infrastructure decisions').count()==1
  page.locator('[data-project="demo-campus-001"]').click()
  page.get_by_role('heading',name='Illustrative 150 MW Campus').wait_for(timeout=16000)
  page.locator('.spatial-canvas').wait_for()
  page.screenshot(path=str(out/f'v262_decision_{name}.png'),full_page=True)
  assert page.locator('.path-table tbody tr').count()==3
  assert 'Transaction valuation: BLOCKED' in page.locator('.decision-risk').inner_text()
  if w==1440:
   page.get_by_role('button',name='Create versioned sensitivity').click()
   page.get_by_role('heading',name='Economics & underwriting').wait_for(timeout=18000)
   assert page.locator('.result-kpis').count()==1
   page.screenshot(path=str(out/'v262_sensitivity_desktop.png'),full_page=True)
   page.locator('[data-view="execution"]').first.click()
   page.get_by_role('heading',name='Critical path & approvals').wait_for()
   assert page.locator('.permit-queue-row').count()>=3
   page.screenshot(path=str(out/'v262_permitiq_desktop.png'),full_page=True)
   page.locator('#permit-step-form input').fill('Obtain revised load letter')
   page.locator('#permit-step-form button').click()
   page.wait_for_timeout(300)
   assert page.get_by_text('Obtain revised load letter').count()>0
   page.locator('[data-action="new-permit"]').click()
   page.locator('#permit-form input[name="title"]').fill('Environmental docket review')
   page.locator('#permit-form select[name="kind"]').select_option('permit')
   page.locator('#permit-form button[type="submit"]').click()
   page.wait_for_timeout(300)
   assert page.get_by_text('Environmental docket review').count()>=1
  elif w==390:
   page.locator('.hamburger').click();page.locator('aside [data-view="execution"]').click(force=True)
   page.get_by_role('heading',name='Critical path & approvals').wait_for()
   page.screenshot(path=str(out/'v262_permitiq_mobile.png'),full_page=True)
   assert page.locator('.decision-risk').is_visible()
  print(name, 'main scroll width',page.evaluate('document.documentElement.scrollWidth'), 'viewport',w,'errors',errs)
  assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth'),f'OVERFLOW {name}'
  assert not errs,errs
  page.close()
 browser.close()
print('V26.2 BROWSER SUCCESS')
