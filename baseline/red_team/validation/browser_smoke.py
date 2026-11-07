from playwright.sync_api import sync_playwright
from pathlib import Path
html=Path(__file__).resolve().parents[2]/'PowerPath.html'
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 for width in [1440,390]:
  page=browser.new_page(viewport={'width':width,'height':900})
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content(html.read_text(),wait_until='load',timeout=100000)
  output=page.evaluate('''() => {const engine=window.PowerPathUnderwrite25;const s=engine?.evaluate({})?.summary;return {title:document.title,ready:!!engine,assurance:s?.screeningReadiness,warnings:s?.creditWarnings?.length,overflow:document.documentElement.scrollWidth>innerWidth+1}}''')
  print(width,output,'errors',errors[:3])
  assert output['ready'] and output['warnings'] >= 2 and not output['overflow'] and not errors
  page.close()
 browser.close()
