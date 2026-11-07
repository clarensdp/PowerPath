from playwright.sync_api import sync_playwright
from pathlib import Path
html=Path('/mnt/data/powerpath_v25/PowerPath.html').read_text()
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for width in [1365,390]:
  page=browser.new_page(viewport={'width':width,'height':850});errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
  page.set_content(html,wait_until='load',timeout=120000)
  page.evaluate("switchView('project')")
  page.locator('[data-v21tab="Underwrite"]').click()
  page.locator('#v25Run').click()
  txt=page.locator('#v25Output').inner_text()
  assert 'Levered NPV' in txt,txt[:1000]
  page.locator('#v25Stress').click()
  assert '45-case deterministic stress grid' in page.locator('#v25Output').inner_text()
  overflow=page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
  print('BROWSER',width,'errors',errs,'overflow',overflow,'stress rows',page.locator('#v25Output tbody tr').count())
  assert not errs and not overflow
  page.screenshot(path=f'/mnt/data/PowerPath_v25_preview_{width}.png',full_page=False)
  page.close()
 browser.close()
