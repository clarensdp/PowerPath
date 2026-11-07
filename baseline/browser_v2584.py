from playwright.sync_api import sync_playwright
from pathlib import Path
source=(Path(__file__).resolve().parent/'PowerPath.html').read_text()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for w,h in [(1440,900),(390,844)]:
  page=browser.new_page(viewport={'width':w,'height':h});errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
  page.set_content(source,wait_until='load',timeout=120000)
  page.evaluate('''() => {let items={}; Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:k=>items[k]||null,setItem:(k,v)=>items[k]=String(v)}})}''')
  page.evaluate("switchView('project')")
  page.locator('[data-v21tab="Underwrite"]').click()
  assert page.locator('#v2584PowerMode').count()==1
  page.locator('#v2584PowerMode').select_option('reimbursed')
  page.locator('[data-v25="powerPassThroughPct"]').fill('100')
  page.locator('#v251Run').click()
  s=page.locator('#v251Output').inner_text()
  assert 'Power reimbursements' in s and 'Model assurance' in s, s[:200]
  page.locator('#v2584PowerMode').select_option('tenant_direct')
  page.locator('#v251Run').click()
  assert 'Net landlord power cost' in page.locator('#v251Output').inner_text()
  assert not errs, errs
  scroll=page.evaluate('document.documentElement.scrollWidth');assert scroll<=w+1,(w,scroll)
  page.screenshot(path=str(Path('/mnt/data')/f'PowerPath_v25_8_4_preview_{w}.png'),full_page=False)
  print('BROWSER',w,'errors=',len(errs),'overflow=',scroll-w)
  page.close()
 browser.close()
