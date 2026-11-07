from playwright.sync_api import sync_playwright
from pathlib import Path
source=(Path(__file__).resolve().parent/'PowerPath.html').read_text()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True, executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for width,height in [(1440,900),(390,844)]:
  page=browser.new_page(viewport={'width':width,'height':height})
  errors=[]
  page.on('pageerror', lambda e:errors.append(str(e)))
  page.set_content(source,wait_until='load',timeout=120000)
  page.evaluate("""() => { const items=new Map(); Object.defineProperty(window, 'localStorage', { configurable:true, value:{ getItem(k){return items.has(k)?items.get(k):null}, setItem(k,v){items.set(k,String(v))}, removeItem(k){items.delete(k)},clear(){items.clear()} } }); }""")
  page.evaluate("switchView('project')")
  page.locator('[data-v21tab="Underwrite"]').click()
  title=page.locator('#v21Body').inner_text()
  assert 'v25.8' in title, title[:250]
  page.locator('[data-v25="tenantFundingLagMonths"]').fill('3')
  page.locator('#v257Sponsor').fill('75')
  page.locator('#v251Run').click()
  output=page.locator('#v251Output').inner_text()
  assert 'FUNDING DEFAULT' in output, output[-800:]
  assert 'Contract-value reconciliation' in output
  scroll=page.evaluate('document.documentElement.scrollWidth')
  assert scroll<=width+1,(width,scroll)
  assert not errors,errors
  print('BROWSER',width,'passed; overflow',scroll-width,'errors',len(errors))
  page.screenshot(path=str(Path(__file__).resolve().parent/f'preview_v258_{width}.png'),full_page=False)
  page.close()
 browser.close()
