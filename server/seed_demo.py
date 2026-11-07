"""Create clearly labeled synthetic starter data in an empty local workspace."""
import json
import subprocess
from .app import ROOT, ENGINE, db, now, audit

def seed():
    with db() as con:
        if con.execute('SELECT COUNT(*) FROM projects').fetchone()[0]:return
        defaults=json.loads(subprocess.check_output(['node',str(ENGINE/'bridge.cjs'),'defaults'],input=b'{}',cwd=ROOT))
        project=defaults['project'];project['powerResponsibility']='tenant_direct';project['sponsorCommitmentM']=800
        project['engineVersion']='27.1.0'  # v27.1: new demo workspaces use the corrected cash-constrained engine
        config={'project':project,'facilities':defaults['facilities']}
        ts=now();pid='demo-campus-001'
        con.execute('''INSERT INTO projects VALUES (?,?,?,?,?,?,?,?)''',(pid,'Illustrative 150 MW Campus','Hypothetical US site',150,'Qualify','ILLUSTRATIVE EXAMPLE — No site has been identified, no utility capacity confirmed, no financing commitments, and no contractual lease economics.',ts,ts))
        con.execute('''INSERT INTO scenarios VALUES (?,?,?,?,?,?,?,?)''',('demo-base-001',pid,'Illustrative base case','underwrite',json.dumps(project),1,ts,ts))
        con.execute('''INSERT INTO scenarios VALUES (?,?,?,?,?,?,?,?)''',('demo-fac-001',pid,'Illustrative facility case','facilities',json.dumps(config),1,ts,ts))
        # These are deliberately fictional strategies and milestones, not geolocated grid assets.
        demo_paths=[
            ('demo-path-grid','Grid utility service','grid',150,32,9,0,0),
            ('demo-path-onsite','On-site bridge generation','onsite',150,23,4,22,12),
            ('demo-path-hybrid','Hybrid phased energization','hybrid',150,26,6,12,5),
        ]
        for path_id,name,strategy,capacity,power_month,delay,capex,energy in demo_paths:
            con.execute('INSERT INTO power_paths VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (path_id,pid,name,strategy,'hypothesis',capacity,power_month,None,None,delay,capex,energy,
                'Fictional illustration only. No utility, fuel, land or interconnection rights verified.',None,ts,ts))
        sample_permits=[
            ('demo-permit-study','System impact study','interconnection','awaiting_third_party','Illustrative utility liaison',28,7,'demo-path-grid'),
            ('demo-permit-air','Air permit screening','permit','working','Illustrative permitting lead',14,4,'demo-path-onsite'),
            ('demo-permit-esa','Electric service agreement','utility','blocked','Illustrative project lead',30,6,'demo-path-hybrid'),
        ]
        for permit_id,title,kind,status,owner,due,delay,path in sample_permits:
            con.execute('INSERT INTO permit_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (permit_id,pid,path,title,kind,status,owner,due,delay,None,
                 'SYNTHETIC DEMO: No regulator or utility has reviewed this requirement.',ts,ts))
        for j,(permit_id,title,is_done) in enumerate([
            ('demo-permit-study','Record utility application',1),('demo-permit-study','Obtain study scope',0),
            ('demo-permit-study','Review network upgrade estimates',0),('demo-permit-air','Identify jurisdiction',1),
            ('demo-permit-air','Compile emissions estimates',0),('demo-permit-esa','Obtain nonbinding tariff estimate',0)]):
            con.execute('INSERT INTO permit_steps VALUES (?,?,?,?,?)',(f'demo-step-{j}',permit_id,title,is_done,j))
        # Two real, third-party-transcribed EIA-860 2025 plant coordinate examples.
        # They have NO geographic relationship to this fictional campus and grant NO available power.
        for plant_id,plant_name,lat,lon,state,county in [
            ('64314','Dickinson',29.461255,-95.056987,'TX','Galveston'),
            ('64315','Loop 463',28.816475,-97.074867,'TX','Victoria')]:
            con.execute('INSERT INTO geographic_assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
              ('demo-geo-'+plant_id,pid,plant_name,'generation_plant',lat,lon,
               'EIA-860 2025 derivative sample',
               'https://askthegrid.com/catalog/eia860_plant_gas_declarations',
               plant_id,'2025','secondary_extract',
               json.dumps({'state':state,'county':county,'upstream_source':'https://www.eia.gov/electricity/data/eia860/',
                'disclaimer':'Third-party excerpt, verify against EIA file; NOT associated with fictional campus or available power'}),ts))
        # Example dependency chain: delays are deliberately analyst-entered / fictional.
        for mid,title,kind,status,path,permit,planned,delay,pred in [
            ('demo-ms-study','Complete system impact study','interconnection','awaiting','demo-path-grid','demo-permit-study',25,5,None),
            ('demo-ms-esa','Execute electric service agreement','utility','planned','demo-path-grid',None,30,4,'demo-ms-study'),
            ('demo-ms-air','Air permitting review','permitting','submitted','demo-path-onsite','demo-permit-air',18,4,None)]:
            con.execute('INSERT INTO delivery_milestones(id,project_id,path_id,permit_id,title,category,status,planned_month,delay_months,predecessor_id,source_url,source_note,evidence_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
              (mid,pid,path,permit,title,kind,status,planned,delay,pred,'',
               'FICTIONAL sample milestone — not an external agency status',None,ts,ts))
        audit(con,pid,'demo.seeded',pid,{'synthetic':True,'third_party_geo_examples':'two unverified EIA derivative coordinates'})
if __name__=='__main__':seed()
