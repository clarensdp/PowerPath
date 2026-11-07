from playwright.sync_api import sync_playwright
from pathlib import Path
import os
import json
import urllib.request, urllib.error

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'previews';OUT.mkdir(exist_ok=True)
BASE=os.environ.get('POWERPATH_BROWSER_BASE','http://127.0.0.1:8768')
style=(ROOT/'web/public/style.css').read_text()
script=(ROOT/'web/public/app.js').read_text()

with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path=os.environ.get('POWERPATH_CHROMIUM') or None,args=['--no-sandbox'])
 for width,height,label in [(1440,900,'desktop'),(1000,800,'tablet'),(390,844,'mobile')]:
  page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
  def bridge(url, method='GET', data=None):
   target=BASE+url if url.startswith('/') else url
   request=urllib.request.Request(target, data=data.encode('utf-8') if data is not None else None,method=method,headers={'Content-Type':'application/json'})
   try:
    with urllib.request.urlopen(request,timeout=30) as r:
     return {'status':r.status,'body':r.read().decode('utf-8'),'type':r.headers.get('Content-Type','application/json')}
   except urllib.error.HTTPError as err:return {'status':err.code,'body':err.read().decode('utf-8'),'type':'application/json'}
  page.expose_function('apiBridge',bridge)
  errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
  page.set_content('<!doctype html><html><head><meta charset=\"utf-8\"><style>'+style+'</style></head><body><div id=\"app\"></div></body></html>')
  page.evaluate('''(()=>{window.fetch = async (url,opts={}) => {const v=await window.apiBridge(String(url),opts.method||'GET',opts.body||null);return new Response(v.body,{status:v.status,headers:{'Content-Type':v.type}})};return true})()''')
  page.add_script_tag(content=script)
  page.wait_for_selector('h1',timeout=15000)
  page.screenshot(path=str(OUT/f'portfolio_{label}.png'),full_page=True)
  print(label,'portfolio',page.locator('h1').first.text_content(), 'overflow', page.evaluate('document.documentElement.scrollWidth > innerWidth'), 'errors',errors)
  assert page.locator('h1').first.inner_text().find('Your infrastructure decisions')>=0
  assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
  if width==1440:
   page.locator('[data-project="demo-campus-001"]').click()
   page.wait_for_selector('h1:text("Illustrative 150 MW Campus")')
   page.screenshot(path=str(OUT/'overview_desktop.png'),full_page=True)
   page.locator('[data-view="model"]').first.click()
   page.wait_for_selector('h1:text("Economics & underwriting")')
   page.screenshot(path=str(OUT/'underwrite_desktop.png'),full_page=True)
   # choose demo base case; first auto-selected often facility, so target
   opt=page.locator('#scenario-select option',has_text='Illustrative base case')
   opt_val=opt.get_attribute('value')
   page.locator('#scenario-select').select_option(opt_val)
   page.locator('#f-rentPerKwMonth').fill('182')
   page.locator('#f-rentPerKwMonth').dispatch_event('change')
   page.locator('[data-action="save-run"]').first.click()
   page.wait_for_timeout(950)
   print('after run', page.locator('.result-kpis').count(), page.locator('.toast').all_text_contents(), page.locator('.warning-list').count())
   page.screenshot(path=str(OUT/'underwrite_result_desktop.png'),full_page=True)
   assert page.locator('.result-kpis').count()==1
   page.locator('[data-view="facilities"]').first.click()
   page.wait_for_selector('h1:text("Debt facilities")')
   page.screenshot(path=str(OUT/'facilities_desktop.png'),full_page=True)
   page.locator('[data-action="new-facility-scenario"]').first.click()
   page.wait_for_selector('#facility-face',timeout=15000)
   page.locator('[data-action="save-run"]').first.click()
   page.wait_for_timeout(800)
   page.wait_for_selector('.facility-risk-strip',timeout=5000)
   assert 'BLOCKED' in page.locator('.facility-risk-strip').first.inner_text()
   assert 'BLOCKED' in page.locator('.result-kpis').first.inner_text() or page.locator('.facility-risk-strip').count()==1
   page.screenshot(path=str(OUT/'notes_v259_desktop.png'),full_page=True)
   page.locator('[data-view="evidence"]').first.click()
   page.wait_for_selector('h1:text("Evidence & documents")')
   page.screenshot(path=str(OUT/'evidence_desktop.png'),full_page=True)
   page.locator('[data-action="new-evidence"]').first.click()
   page.locator('#evidence-form input[name="title"]').fill('QA Synthetic Term Sheet')
   page.locator('#evidence-form input[name="citation"]').fill('TEST ONLY – NO EXECUTED TERMS')
   page.locator('#evidence-form button[type="submit"]').click()
   page.wait_for_timeout(250)
   print('evidence',page.locator('.evidence-row').count())
   assert page.locator('.evidence-row').count()>=1
   page.locator('[data-view="history"]').first.click()
   page.wait_for_selector('h1:text("Run history")')
   print('history',page.locator('.history-row').count())
   assert page.locator('.history-row').count()>=1
   page.screenshot(path=str(OUT/'history_desktop.png'),full_page=True)
  elif width==390:
   # v26.2 project-first mobile navigation: select project before using sidebar.
   page.locator('[data-project="demo-campus-001"]').click()
   page.wait_for_selector('h1:text("Illustrative 150 MW Campus")')
   page.screenshot(path=str(OUT/'v262_decision_mobile.png'),full_page=True)
   page.locator('.hamburger').click()
   page.locator('aside [data-view="model"]').click(force=True)
   page.wait_for_selector('h1:text("Economics & underwriting")')
   page.screenshot(path=str(OUT/'underwrite_mobile.png'),full_page=True)
   print('mobile model overflow',page.evaluate('document.documentElement.scrollWidth > innerWidth'))
   assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
  assert not errors,errors
  page.close()
 browser.close()
print('BROWSER ACCEPTANCE OK')
