/* Flow order is physical; signed climate contributions are shown separately. */
function renderLcaResults(result) {
  const lca = result.lca, fu = lca.functional_unit_kg;
  const gwpFormat = x => Number.isFinite(x) ? (Number(x.toFixed(4)) || 0).toFixed(4) : '—';
  const n = x => gwpFormat(x * fu);
  const signed = x => {
    const value = n(x);
    return (x > 0 && value !== '0.0000' && value !== '—' ? '+' : '') + value;
  };
  const contributions = lca.contributions.filter(r => r.gwp !== 0);
  const positive = contributions.reduce((s,r) => s + Math.max(0,r.gwp),0);
  const negative = contributions.reduce((s,r) => s + Math.min(0,r.gwp),0);
  const transport = lca.transport || [];
  const labels = {electricity_kwh:'Equipment electricity',heat_kwh:'Process heat',water_input_kg:'Water supply',
    wastewater_treatment_kg:'Wastewater treatment',diesel_burned_mj:'Diesel combustion',heavy_machine_kg:'Machinery',
    grinding_machine_kg:'Grinding equipment',hydraulic_digger_m3:'Excavation',sorting_facility_unit:'Sorting facility',
    thermal_factory_unit:'Thermal activation plant',carbonation_factory_unit:'Carbonation plant',
    co2_emitted_kg:'Direct CO₂ released',co2_stored_kg:'Retained CO₂ · conditional credit',co2_makeup_kg:'CO₂ supply',
    waste_to_process:'Inbound waste transport'};
  const stages = [];
  const inbound = transport.find(r => r.key === 'waste_to_process');
  if (inbound) stages.push({label:inbound.label,kind:'transport',gwp:inbound.gwp});
  lca.process_contributions.forEach(p => stages.push({label:p.process_name,kind:'process',gwp:p.gwp}));
  const max = Math.max(...contributions.map(r => Math.abs(r.gwp)), 1e-15);
  return `<section class="lca-hero"><div><h2>SCM at processing gate</h2><div class="lca-total">${gwpFormat(lca.gwp_kg_co2e)} <span>kg CO₂e</span></div><p><strong>${format(fu)} kg dry SCM</strong> · ${gwpFormat(lca.gwp_kg_co2e_kg)} kg CO₂e/kg</p></div><a class="lca-hero-action" href="/recipes">Build a mix →</a></section>
  <div class="lca-metrics"><article class="card"><span>Positive contributions</span><strong>+${n(positive)}</strong><small>kg CO₂e</small></article><article class="card credit"><span>Negative contributions</span><strong>${n(negative)}</strong><small>kg CO₂e</small></article><article class="card"><span>Transport included</span><strong>${n(transport.reduce((s,r)=>s+r.gwp,0))}</strong><small>kg CO₂e</small></article></div>
  <section class="card lca-flow-card"><div class="card-heading"><h2>LCA pathway</h2><span class="quiet-badge">kg CO₂e / ${format(fu)} kg SCM</span></div><div class="lca-flow-scroll" tabindex="0" role="region" aria-label="Climate impact contributions in process order"><ol class="lca-flow lca-flow-labelled">${stages.map(s=>`<li class="lca-flow-node ${s.kind}" aria-label="${esc(s.label)}"><strong>${esc(s.label)}</strong><b class="${s.gwp<0?'negative':''}">${signed(s.gwp)}</b></li>`).join('')}<li class="lca-flow-end finish"><strong>Total</strong><b>${gwpFormat(lca.gwp_kg_co2e)}</b></li></ol></div></section>
  <section class="card lca-contribution-card"><div class="card-heading"><h2>GWP contributions</h2><span class="quiet-badge">kg CO₂e / ${format(fu)} kg SCM</span></div><div class="lca-bars">${[...contributions].sort((a,b)=>Math.abs(b.gwp)-Math.abs(a.gwp)).map(r=>`<div class="lca-bar-row"><span>${esc(labels[r.flow]||r.flow)}</span><div class="lca-bar-track" aria-hidden="true"><i class="${r.gwp<0?'negative':'positive'}" style="width:${Math.abs(r.gwp)/max*50}%"></i></div><strong>${signed(r.gwp)}</strong></div>`).join('')}</div>${lca.co2_source?'<p class="lca-footnote">Retained CO₂: conditional −1 credit. Negative GWP is not verified removal.</p>':''}</section>`;
}
