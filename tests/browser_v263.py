"""v26.3 real browser: source-location map, source CSV, milestone and saved model path."""
import os
from pathlib import Path
import urllib.request,urllib.error
from playwright.sync_api import sync_playwright
BASE=os.environ.get('POWERPATH_BROWSER_BASE','http://127.0.0.1:8768')
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'previews';OUT.mkdir(exist_ok=True)
with sync_playwright() as playwright:
 browser=playwright.chromium.launch(headless=True,executable_path=os.environ.get('POWERPATH_CHROMIUM') or None,args=['--no-sandbox'])
 for label,width,height in [('desktop',1440,900),('tablet',1024,820),('mobile',390,844)]:
  page=browser.new_page(viewport={'width':width,'height':height})
  errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
  def bridge(url,method='GET',data=None):
   req=urllib.request.Request(BASE+url,data=data.encode() if data is not None else None,method=method,headers={'Content-Type':'application/json'})
   try:
    with urllib.request.urlopen(req,timeout=30) as r:return {'status':r.status,'body':r.read().decode(),'type':r.headers.get('Content-Type','application/json')}
   except urllib.error.HTTPError as e:return {'status':e.code,'body':e.read().decode(),'type':'application/json'}
  page.expose_function('apiBridge',bridge)
  style=(ROOT/'web/public/style.css').read_text();script=(ROOT/'web/public/app.js').read_text()
  page.set_content('<!doctype html><html><head><meta charset="utf-8"><style>'+style+'</style></head><body><div id="app"></div></body></html>')
  page.evaluate("""(() => {window.fetch=async (url,opts={}) => {const v=await window.apiBridge(String(url),opts.method||'GET',opts.body||null);return new Response(v.body,{status:v.status,headers:{'Content-Type':v.type}})};return true})()""")
  page.add_script_tag(content=script)
  page.get_by_role('heading',name='Your infrastructure decisions').wait_for()
  page.locator('[data-project="demo-campus-001"]').click()
  page.get_by_role('heading',name='Illustrative 150 MW Campus').wait_for()
  page.locator('.real-map').first.wait_for()
  assert page.locator('.real-map .geo-marker').count()>=2
  assert 'not utility connection' in page.locator('.geo-source-caption').inner_text().lower()
  page.screenshot(path=str(OUT/f'v263_decision_{label}.png'),full_page=True)
  if width<650:
   page.locator('.hamburger').click();page.locator('aside [data-view="power"]').click(force=True)
  else:page.locator('[data-view="power"]').first.click()
  page.get_by_role('heading',name='Power paths & candidates').wait_for()
  assert 'Geographic & utility intelligence' in page.locator('main').inner_text()
  assert 'NO VERIFIED AVAILABLE MW' in page.locator('main').inner_text()
  assert page.locator('[data-geo]').count()>=2
  page.screenshot(path=str(OUT/f'v263_geo_{label}.png'),full_page=True)
  if label=='desktop':
   page.locator('details.geo-import summary').click()
   frm=page.locator('#geo-import-form')
   frm.locator('input[type="file"]').set_input_files({'name':'plant_source.csv','mimeType':'text/csv','buffer':b'Plant Code,Plant Name,Latitude,Longitude,State\n90051,Public demo plant,30.45,-94.20,TX\n'})
   frm.get_by_role('button',name='Import source points').click()
   page.locator('.geo-asset-row').filter(has_text='Public demo plant').wait_for(timeout=15000)
   assert page.locator('.geo-marker').count()>=3
   page.locator('[data-geo]').last.click(force=True)
   page.locator('.geo-selected').wait_for()
  if width<650:
   page.locator('.hamburger').click();page.locator('aside [data-view="execution"]').click(force=True)
  else:page.locator('[data-view="execution"]').first.click()
  page.get_by_role('heading',name='Critical path & approvals').wait_for()
  assert page.get_by_role('heading',name='Linked energization critical path').count()==1
  page.screenshot(path=str(OUT/f'v263_milestones_{label}.png'),full_page=True)
  if label=='desktop':
   frm=page.locator('#milestone-form')
   frm.locator('[name="title"]').fill('New network upgrade estimate')
   frm.locator('[name="delay_months"]').fill('13')
   frm.get_by_role('button',name='Save milestone').click()
   page.locator('.milestone-row b').filter(has_text='New network upgrade estimate').first.wait_for(timeout=15000)
   page.locator('[data-action="new-critical-sensitivity"]').click()
   page.get_by_role('heading',name='Economics & underwriting').wait_for(timeout=15000)
   assert page.locator('.result-kpis').count()==1
   page.screenshot(path=str(OUT/'v263_saved_sensitivity_desktop.png'),full_page=True)
  assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),f'Overflow {label}'
  assert not errs,errs
  print('PASS',label,'map, milestone screens, no overflow, no exceptions')
  page.close()
 browser.close()
