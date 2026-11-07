import json,sys
ref=json.load(open('ref.json'));
F=['grossRevenue','energy','ebitda','cfads','capex','tenantCashReceipt','draw','mezzDraw','capitalizedInterest','cashInterest','principal','mezzPrincipal','debt','mezzDebt','reserve','cash','sponsorContribution','distribution','dscr']
for lab,fn in [('PATCHED','js_patched.json'),('ORIGINAL v25.8','js_orig.json')]:
  js=json.load(open(fn));print('==',lab);tot=0
  for k in ref:
    if 'error' in js[k]: print(f'{k:34s} JS ERROR: {js[k]["error"]}');continue
    worst=(0,None,None);n=0
    for a,b in zip(js[k]['rows'],ref[k]['rows']):
      for f in F:
        x,y=a.get(f),b[f]
        if x is None and y is None: n+=1;continue
        if x is None or y is None: g=1e9
        else: g=abs(x-y)
        n+=1
        if g>worst[0]: worst=(g,a['month'],f)
    tot+=n
    print(f'{k:34s} checks {n:5d} maxgap {worst[0]:.3e} at m{worst[1]} {worst[2]}  NPV js {js[k]["npvM"]:10.3f} ref {ref[k]["npvM"]:10.3f}')
  print('total checks',tot)
