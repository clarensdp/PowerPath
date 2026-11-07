/* boot: run after engine v2 and the model are loaded */
/* init */
try{setPersona(localStorage.getItem('pp_persona')||'investor');}catch{setPersona('investor');}
try{setLimits(localStorage.getItem('pp_limits')==='1');}catch{setLimits(false);}
try{localStorage.setItem('pp_snap',JSON.stringify(snapshot()));}catch{}
let startView='overview';try{const v=localStorage.getItem('pp_view');if(VIEWS_ALL.includes(v))startView=v;}catch{}
render();renderBT();updateSizeText();renderOverview();switchView(startView);
