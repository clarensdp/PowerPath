"""v26.8 real-browser demo: source-diff, approval and agent report UI."""
import os,sys,time,tempfile,subprocess
from pathlib import Path
import requests,urllib.request,urllib.error
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
PORT=8877
SRC='http://127.0.0.1:'+str(PORT)
TEMP=tempfile.TemporaryDirectory(prefix='pp_v268_browser_')
ENV={**os.environ,'POWERPATH_DATA_DIR':TEMP.name,'PYTHONDONTWRITEBYTECODE':'1'}
subprocess.run([sys.executable,'-m','server.seed_demo'],cwd=ROOT,env=ENV,check=True,capture_output=True)
server=subprocess.Popen([sys.executable,'-m','uvicorn','server.app:app','--host','127.0.0.1','--port',str(PORT)],cwd=ROOT,env=ENV,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)

try:
    for _ in range(60):
        try:
            if requests.get(SRC+'/api/health',timeout=1).ok:break
        except Exception:pass
        time.sleep(.2)
    else:raise RuntimeError('Server did not start')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ.get('POWERPATH_CHROMIUM') or None,args=['--no-sandbox','--disable-dev-shm-usage'])
        for width,height,name in [(1440,900,'desktop'),(1024,820,'tablet'),(390,844,'mobile')]:
            context=browser.new_context(viewport={'width':width,'height':height})
            page=context.new_page();errors=[];page.on('pageerror',lambda exc:errors.append(str(exc)))
            
            def bridge(url,method='GET',data=None):
                req=urllib.request.Request(SRC+url,data=data.encode() if data is not None else None,method=method,headers={'Content-Type':'application/json'})
                try:
                    with urllib.request.urlopen(req,timeout=35) as resp:return {'status':resp.status,'body':resp.read().decode(),'type':resp.headers.get('Content-Type','application/json')}
                except urllib.error.HTTPError as exc:return {'status':exc.code,'body':exc.read().decode(),'type':'application/json'}
            page.expose_function('apiBridge',bridge)
            style=(ROOT/'web/public/style.css').read_text()
            script=(ROOT/'web/public/app.js').read_text()
            page.set_content('<!doctype html><html><head><meta charset="utf-8"><style>'+style+'</style></head><body><div id="app"></div></body></html>')
            page.evaluate("""(() => {window.fetch=async (url,opts={})=>{const v=await window.apiBridge(String(url),opts.method||'GET',opts.body||null);return new Response(v.body,{status:v.status,headers:{'Content-Type':v.type}})};return true})()""")
            page.add_script_tag(content=script)
            page.get_by_role('heading',name='Your infrastructure decisions').wait_for()
            page.locator('[data-project="demo-campus-001"]').first.click()
            (page.locator('.hamburger').click() if width<650 else None)
            page.locator('aside [data-view="intelligence"]').first.click(force=True)
            assert page.get_by_text('Intelligence & Agent Council').count()>0
            assert page.get_by_text('SOURCE SNAPSHOTS', exact=True).count()>0
            if name=='desktop':
                csv1=ROOT/'examples/PJM_QUEUE__2026-10-01.csv';csv2=ROOT/'examples/PJM_QUEUE__2026-10-15.csv'
                for n,csv in enumerate((csv1,csv2)):
                    page.locator('#intel-source-key').select_option('PJM_QUEUE')
                    page.locator('#intel-import-form input[name="source_published_date"]').fill(('2026-10-01','2026-10-15')[n])
                    page.locator('#intel-import-form input[type="file"]').set_input_files(str(csv))
                    page.locator('#intel-import-form button[type="submit"]').click()
                    page.get_by_text('SOURCE SNAPSHOTS', exact=True).wait_for()
                    page.wait_for_timeout(350)
                page.locator('.intel-item-head').first.wait_for()
                form=page.locator('.intel-proposal-form').first
                form.locator('select[name="milestone_id"]').select_option(index=1)
                form.locator('input[name="proposed_delay_months"]').fill('14')
                form.locator('input[name="reason"]').fill('Illustrative row changed; analyst must verify applicability to load service.')
                form.locator('button').click()
                page.locator('[data-impact]').first.wait_for()
                page.on('dialog',lambda d:d.accept())
                page.locator('[data-impact]').first.click()
                page.locator('[data-proposal-decision="approve"]').first.click()
                page.locator('[data-action="run-agent-council"]').click()
                page.locator('[data-agent-meeting]').first.wait_for()
            else:
                assert page.locator('.intel-item-head').count()>=2
                assert page.locator('[data-agent-meeting]').first.count()>0
            assert not errors, errors
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 2'), 'overflow '+name
            if name in ('desktop','mobile'):
                page.evaluate('window.scrollTo(0,0)')
                page.screenshot(path=str(ROOT/'previews'/f'v268_source_watch_{name}.png'),full_page=True)
            print(name,'PASS','changes',page.locator('.intel-item-head').count(),'errors',len(errors))
            context.close()
        browser.close()
finally:
    server.terminate()
    try: server.wait(timeout=8)
    except subprocess.TimeoutExpired:server.kill()
    TEMP.cleanup()
