/** WGS84 point plot in Web Mercator. No raster tiles, no geocoding and no invented coordinates. */
type Geocoded={id:string;name:string;latitude:number|null;longitude:number|null};
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]||x));
const merc=(lat:number)=>Math.log(Math.tan(Math.PI/4+Math.max(-85,Math.min(85,lat))*Math.PI/360));
export function realGeoMap(paths:Geocoded[],assets:Geocoded[],selectedPath:string|null,selectedAsset:string|null,tilesConsent:boolean){
 const points=[...assets.filter(x=>Number.isFinite(x.latitude)&&Number.isFinite(x.longitude)).map(x=>({...x,kind:'source'})),...paths.filter(x=>Number.isFinite(x.latitude)&&Number.isFinite(x.longitude)).map(x=>({...x,kind:'candidate'}))];
 if(!points.length)return `<div class="real-map no-coordinates"><div><b>Geographic intelligence</b><p>No source-backed map coordinates yet.</p><small>Import an EIA-860 plant file or enter a cited site coordinate. Schematic pins are not a substitute.</small></div></div>`;
 const lons=points.map(x=>x.longitude as number), ys=points.map(x=>merc(x.latitude as number));
 const centerX=(Math.min(...lons)+Math.max(...lons))/2,centerY=(Math.min(...ys)+Math.max(...ys))/2;
 const spreadX=Math.max(.20,Math.max(...lons)-Math.min(...lons)),spreadY=Math.max(.14,Math.max(...ys)-Math.min(...ys));
 const aspect=1.65;
 let xSpan=Math.max(spreadX*1.5,spreadY*aspect*1.5),ySpan=xSpan/aspect;
 const x0=centerX-xSpan/2,y0=centerY-ySpan/2;
 const coords=points.map(p=>({p,x:60+760*((p.longitude as number)-x0)/xSpan,y:50+460*(1-(merc(p.latitude as number)-y0)/ySpan)}));
 const grid=Array.from({length:7},(_,i)=>{const v=50+i*75;return `<line x1="50" x2="810" y1="${v}" y2="${v}"/><line y1="50" y2="510" x1="${50+i*(760/6)}" x2="${50+i*(760/6)}"/>`}).join('');
 const markers=coords.map(({p,x,y})=>p.kind==='source'?`<g class="geo-marker ${p.id===selectedAsset?'chosen':''}" data-geo="${esc(p.id)}" role="button" tabindex="0" aria-label="Inspect ${esc(p.name)}" transform="translate(${x.toFixed(2)} ${y.toFixed(2)})"><circle r="13" fill="#ffffff" stroke="#297f80" stroke-width="2"/><circle r="6" fill="#258179"/><title>${esc(p.name)} — source location, not available MW</title></g>`:`<g class="geo-marker candidate ${p.id===selectedPath?'chosen':''}" data-path="${esc(p.id)}" role="button" tabindex="0" aria-label="Inspect path ${esc(p.name)}" transform="translate(${x.toFixed(2)} ${y.toFixed(2)})"><path d="M0 -14 L13 0 L0 14 L-13 0 Z" fill="#c47d2a" stroke="white" stroke-width="2"/><title>${esc(p.name)} — analyst coordinate, not utility confirmed</title></g>`).join('');
 return `<div class="real-map"><div class="real-map-label">GEOREFERENCED • WGS84 / WEB MERCATOR</div><svg viewBox="0 0 860 560" role="img" aria-label="Geographic point map, accurately projected positions without a basemap"><rect width="860" height="560" fill="#e7f1ef"/><g class="geo-grid">${grid}</g>${markers}<text x="25" y="548" font-size="15" fill="#55777c">Survey vintage and source records shown in inspector • No confirmed grid capacity</text></svg></div>`;
}
