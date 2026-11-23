"""Screening dispatch in two time blocks per month, with no solar firm capacity."""
from calendar import monthrange
from collections import defaultdict
from pydantic import BaseModel, ConfigDict, Field, model_validator
from server.providers.renewables.nrel import SolarSystem
from server.services.power_capacity import constrain, target_it, tranches


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Phase(Input):
    month: int = Field(ge=1, le=600)
    mw: float = Field(ge=0, le=100000)


class Grid(Input):
    phases: list[Phase] = Field(default_factory=list, max_length=100)
    price_mwh: float | None = Field(default=None, ge=0, le=10000)
    connection_cost_m: float = Field(default=0, ge=0, le=100000)
    emissions_kg_mwh: float | None = Field(default=None, ge=0, le=10000)
    use_utility_study: bool = False
    delay_months: int = Field(default=0, ge=0, le=120)


class Gas(Input):
    mw: float = Field(gt=0, le=100000)
    month: int = Field(ge=1, le=600)
    efficiency: float = Field(gt=.05, le=1)
    fuel_usd_mmbtu: float = Field(ge=0, le=10000)
    emissions_kg_mmbtu: float = Field(ge=0, le=1000)
    capex_m: float = Field(ge=0, le=100000)
    variable_opex_mwh: float = Field(ge=0, le=10000)
    fixed_opex_year_m: float = Field(default=0, ge=0, le=10000)


class Solar(Input):
    system: SolarSystem
    month: int = Field(ge=1, le=600)
    capex_m: float = Field(ge=0, le=100000)
    fixed_opex_year_m: float = Field(ge=0, le=10000)
    monthly_mwh: list[float] | None = Field(default=None, min_length=12, max_length=12)

    @model_validator(mode='after')
    def validate_profile(self):
        if self.monthly_mwh is not None:
            from math import isfinite
            if any(not isfinite(x) or not 0 <= x <= self.system.capacity_kw / 1200 * 31 * 12 for x in self.monthly_mwh):
                raise ValueError('Solar monthly energy exceeds daytime AC inverter limit or is invalid')
        return self


class PowerCase(Input):
    name: str = Field(min_length=2, max_length=120)
    scenario_id: str
    rationale: str = Field(min_length=10, max_length=3000)
    grid: Grid | None = None
    gas: Gas | None = None
    solar: Solar | None = None

    @model_validator(mode='after')
    def validate_sources(self):
        if not any((self.grid,self.gas,self.solar)):
            raise ValueError('Select at least one power technology')
        if self.grid:
            if self.grid.use_utility_study == bool(self.grid.phases):
                raise ValueError('Provide either grid phases or select a utility study')
            tranches([p.model_dump() for p in self.grid.phases], basis='gross')
        return self


def grid_inputs(grid, config, study):
    if not grid:
        return [],0,None
    if not grid['use_utility_study']:
        return [{**p,'month':p['month']+grid['delay_months']} for p in grid['phases']],grid['connection_cost_m'],None
    if not study or any(study.get(k) is None for k in ('capacity_mw','energization_date','connection_cost_usd')):
        raise ValueError('Selected study must document gross MW, connection cost and energization date')
    from datetime import date
    day=date.fromisoformat(study['energization_date'])
    # Mid-month delivery is credited from the following full month.
    month=max(1,(day.year-config.get('calendarStartYear',2026))*12+day.month-config.get('calendarStartMonth',1)+1+(day.day>1))
    return [{'month':month+grid['delay_months'],'mw':study['capacity_mw']}],study['connection_cost_usd']/1e6,study


def model(case, config, calculate, study=None, profile=None):
    grid,gas,solar=(case[k] for k in ('grid','gas','solar'))
    grid_phases,connection,selected_study=grid_inputs(grid,config,study)
    increments=defaultdict(float);previous=0
    for phase in grid_phases:
        increments[phase['month']]+=phase['mw']-previous;previous=phase['mw']
    if gas:increments[gas['month']]+=gas['mw']
    firm=0;phases=[]
    for month,increment in sorted(increments.items()):
        firm+=increment;phases.append({'month':month,'mw':firm})
    if any(p['month']>600 for p in phases):raise ValueError('Delivery exceeds 600 project months')
    # Source dates are absolute project months. Preserve legacy delays as building gates only.
    cfg=constrain(config,phases,'gross');delay=cfg.get('delayMonths',0)
    for b in cfg['buildings']:
        b['powerMonth']+=delay;b['leaseMonth']+=delay
    cfg['delayMonths']=0
    target=target_it(cfg);pue=cfg.get('pue',1.3)
    capex=connection+(gas['capex_m'] if gas else 0)+(solar['capex_m'] if solar else 0)
    if capex and (cfg.get('tenantCapexPct',0) or any(b.get('tenantCapexPct',0) for b in cfg['buildings'])):
        raise ValueError('Set tenant capital contributions to zero for this owner-funded power sensitivity')
    construction_mw=sum(b['itMW'] for b in cfg['buildings'])
    cfg['constructionCostMW']=cfg.get('constructionCostMW',7)+capex/(construction_mw*(1+cfg.get('overrunPct',0)/100))
    cfg['powerCostMWh']=0
    first=calculate('underwrite',cfg)
    rate=(grid['price_mwh'] if grid and grid['price_mwh'] is not None else config.get('powerCostMWh',85))
    profile=profile or ([0]*12 if not solar else None)
    if profile is None:raise ValueError('A PVWatts monthly profile or explicit monthly assumptions are required')

    def dispatch(rows):
        periods=[]
        for r in rows:
            m=r['month'];offset=cfg.get('calendarStartMonth',1)+m-2
            days=monthrange(cfg.get('calendarStartYear',2026)+offset//12,offset%12+1)[1];hours=days*24
            grid_mw=max((p['mw'] for p in grid_phases if p['month']<=m),default=0)
            gas_mw=gas['mw'] if gas and m>=gas['month'] else 0
            solar_active=solar and m>=solar['month']
            expected=min(profile[offset%12],solar['system']['capacity_kw']/1200*hours/2) if solar_active else 0
            demand=r['onlineMW']*pue;supplied=defaultdict(float)
            for daylight in (True,False):
                block_hours=hours/2;remaining=demand*block_hours
                for key,available in [('solar',expected if daylight else 0),('grid',grid_mw*block_hours),('gas',gas_mw*block_hours)]:
                    use=min(remaining,available);supplied[key]+=use;remaining-=use
            fuel=supplied['gas']*3.412141633/gas['efficiency'] if gas else 0
            direct=fuel*gas['emissions_kg_mmbtu']/1000 if gas else 0
            indirect=(supplied['grid']*grid['emissions_kg_mwh']/1000 if grid and grid['emissions_kg_mwh'] is not None else None if supplied['grid']>0 else 0)
            opex=supplied['grid']*rate+(fuel*gas['fuel_usd_mmbtu']+supplied['gas']*gas['variable_opex_mwh'] if gas else 0)
            fixed=((gas['fixed_opex_year_m'] if gas_mw else 0)+(solar['fixed_opex_year_m'] if solar_active else 0))*1e6/12
            periods.append({'month':m,'hours':hours,'firm_gross_mw':grid_mw+gas_mw,'operating_it_mw':r['onlineMW'],
                'unmet_target_gross_mw':max(0,target*pue-grid_mw-gas_mw),'unmet_target_mwh':max(0,(target*pue-grid_mw-gas_mw)*hours),
                'not_operating_target_it_mw':max(0,target-r['onlineMW']),'facility_load_mwh':demand*hours,
                'lease_revenue_m':r['leaseRevenue'],'cfads_m':r['cfads'],
                'energy_mwh':dict(supplied),'unused_solar_mwh':expected-supplied['solar'],'gas_fuel_mmbtu':fuel,
                'direct_co2_tonnes':direct,'grid_co2_tonnes':indirect,'opex_usd':opex+fixed})
        return periods

    periods=dispatch(first['rows'])
    # Financing stress may halt construction and change which capacity comes online.
    # Reweight against the resulting operating profile, with a bounded retry.
    converged=False
    for _ in range(4):
        mwh=sum(p['facility_load_mwh'] for p in periods)
        rate_used=sum(p['opex_usd'] for p in periods)/mwh if mwh else 0
        cfg['powerCostMWh']=rate_used
        final=calculate('underwrite',cfg)
        periods=dispatch(final['rows'])
        actual_mwh=sum(p['facility_load_mwh'] for p in periods)
        next_rate=sum(p['opex_usd'] for p in periods)/actual_mwh if actual_mwh else 0
        if abs(next_rate-rate_used)<1e-6:
            converged=True
            break
    warning='Dispatch O&M enters underwriting as a constant energy-weighted screening rate. Timing is approximated.'
    if not actual_mwh and any(p['opex_usd'] for p in periods):
        warning='No operating MWh. Dispatch O&M is shown separately and excluded from underwriting.'
    if not converged:
        warning+=' Financing feedback changed the operating profile. Operating costs do not reconcile to the weighted financial rate.'
    totals={key+'_mwh':sum(p['energy_mwh'][key] for p in periods) for key in ('grid','gas','solar')}
    totals.update(unmet_mwh=sum(p['unmet_target_mwh'] for p in periods),
                  direct_co2_tonnes=sum(p['direct_co2_tonnes'] for p in periods),
                  grid_co2_tonnes=None if any(p['grid_co2_tonnes'] is None for p in periods) else sum(p['grid_co2_tonnes'] for p in periods))
    return {'totals':totals,'model_version':'parcel-dispatch-1','target_it_mw':target,'pue':pue,'grid_price_mwh':rate,
            'power_capex_m':capex,'periods':periods,'opex_usd':sum(p['opex_usd'] for p in periods),
            'first_operation_month':next((p['month'] for p in periods if p['operating_it_mw']>0),None),
            'full_operation_month':next((p['month'] for p in periods if p['operating_it_mw']>=target-1e-7),None),
            'finance':final['summary'],'engine_inputs':cfg,'utility_study':selected_study,
            'limitations':[warning,'Solar has zero firm capacity. Each month uses 12-hour daylight/night blocks with solar, grid, then gas dispatch.',
                'Power capex uses the engine construction spend schedule. Unmet target assumes continuous full facility demand. No storage, redundancy, grid losses or gas outages modeled.']}
