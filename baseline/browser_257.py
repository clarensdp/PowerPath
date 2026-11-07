from playwright.sync_api import sync_playwright
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from functools import partial
source=Path('/mnt/data/powerpath_v25_7/PowerPath.html').read_text()
server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory='/mnt/data/powerpath_v25_7'))
Thread(target=server.serve_forever, daemon=True).start()
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    for width,height in [(1440,900),(390,844)]:
        page=browser.new_page(viewport={'width':width,'height':height})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(source,wait_until='load',timeout=120000)
        page.evaluate("""() => { const items=new Map(); Object.defineProperty(window, 'localStorage', { configurable:true, value:{ getItem(k){return items.has(k)?items.get(k):null}, setItem(k,v){items.set(k,String(v))}, removeItem(k){items.delete(k)},clear(){items.clear()} } }); }""")
        page.evaluate("switchView('project')")
        page.locator('[data-v21tab="Underwrite"]').click()
        title=page.locator('#v21Body').inner_text()
        assert 'v25.7' in title
        assert page.locator('#v257Sponsor').count()==1
        page.locator('#v257Sponsor').fill('75')
        page.locator('[data-v25="cashTaxRatePct"]').fill('19')
        page.locator('[data-v25="maintenanceCapexMWYearM"]').fill('0.10')
        page.locator('#v251Run').click()
        output=page.locator('#v251Output').inner_text()
        assert 'FUNDING DEFAULT' in output,output[:2000]
        assert 'Cumulative CFADS' in output
        assert 'Sponsor commitment' in output
        widthpage=page.evaluate('document.documentElement.scrollWidth')
        assert widthpage<=width+1,(width,widthpage)
        assert not errors,errors
        print('BROWSER',width,'no errors; view', 'Underwrite','overflow',widthpage-width,'funding status visible')
        page.screenshot(path=f'/mnt/data/PowerPath_v25_7_preview_{width}.png',full_page=False)
        page.close()
    browser.close()

server.shutdown()
