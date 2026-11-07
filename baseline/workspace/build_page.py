from pathlib import Path
p=Path(__file__).resolve().parent
s=(p/'shell.html').read_text()
for key,name in [('CSS','style.css'),('PROFILES','profiles.json'),('FINANCE','finance.js'),('VALUATION','valuation.js'),('APP','app.js'),('OPPORTUNITIES','opportunities.json'),('DEVELOPMENT','development.js'),('DEVELOPMENT_UI','development-ui.js'),('OVERVIEW','overview.js'),('SITES','sites.json'),('PLANTS','plants.json'),('INTEL','intel.js'),('HOURLY','hourly.json'),('REGIONS','regions.json'),('CALIB','calibration.json'),('ENGINE2','engine2.js'),('MODEL','model.js'),('FEASIBILITY','feasibility.js'),('FEASIBILITY_UI','feasibility-ui.js'),('BOOT','boot.js'),('DECISION_UI','decision-ui.js'),('CONNECTORS','data-connectors.js'),('MARKET_DATA','market-data.js'),('PROJECT21','project21.js'),('DELIVERY24','delivery24.js'),('DILIGENCE22','diligence22.js'),('UNDERWRITE25','underwrite25.js'),('FACILITIES259','facility_waterfall259.js')]:
    s=s.replace('__'+key+'__',(p/name).read_text())
s=s.replace('__CSS259__',(p/'institutional259.css').read_text())
(p.parent/'PowerPath.html').write_text(s)
(p.parent/'dist').mkdir(exist_ok=True)
(p.parent/'dist/index.html').write_text(s)
print('Built PowerPath.html (self-contained, no network or installation required)')
