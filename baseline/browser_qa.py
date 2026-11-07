from pathlib import Path
from playwright.sync_api import sync_playwright
import json
html=Path('/mnt/data/PowerPath_v25_9_preview/source/PowerPath.html').read_text()
checks=[]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for width in (1440,1024,390):
  page=b.new_page(viewport={'width':width,'height':900})
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(html,wait_until='load',timeout=120000)
  theme=page.evaluate('document.documentElement.dataset.theme')
  assert theme=='light',theme
  page.evaluate("switchView('overview')");assert page.locator('#overview').is_visible()
  page.screenshot(path=f'/mnt/data/PowerPath_v25_9_preview/overview_{width}.png',animations='disabled')
  page.evaluate("switchView('finance259')")
  assert page.locator('#finance259').is_visible();assert 'UNVERIFIED SCENARIO' in page.locator('#finStats').inner_text()
  assert 'N/A — default' in page.locator('#finStats').inner_text(),page.locator('#finStats').inner_text()[:1000]
  page.locator('#finFace').fill('220');page.locator('#finCoupon').fill('10');page.locator('#finApply').click()
  assert page.locator('#finFace').input_value()=='220'
  assert page.locator('#finFacilities').count()==1
  page.locator('.fin-details summary').click(); assert page.locator('#finInput').is_visible()
  page.screenshot(path=f'/mnt/data/PowerPath_v25_9_preview/facility_{width}.png',animations='disabled')
  page.evaluate("switchView('project')");assert page.locator('#project').is_visible()
  assert page.locator('.ctx-status').count()==1
  overflow=page.evaluate('document.documentElement.scrollWidth')-width
  assert overflow<=1,(width,overflow)
  assert not errors,errors
  checks.append({'viewport':width,'status':'PASS','theme':theme,'finance_interaction':'PASS','overflow_px':overflow,'javascript_errors':errors})
  page.close()
 b.close()
Path('/mnt/data/PowerPath_v25_9_preview/BROWSER_QA.json').write_text(json.dumps(checks,indent=2))
print(json.dumps(checks,indent=2))
