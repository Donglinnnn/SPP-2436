'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (value, digits=3) => value == null ? '—' : Number(value).toLocaleString('en-GB', {maximumFractionDigits:digits});
  const roles = ['cement','scm','sand','aggregate','recycled_fine','recycled_coarse','water'];
  const labels = {cement:'Cement',scm:'Your SCM',sand:'Natural sand',aggregate:'Natural coarse aggregate',recycled_fine:'Recycled fines / fine aggregate',recycled_coarse:'Recycled coarse aggregate',water:'Recipe water'};
  let schema, materials=[], projects=[], revision=0, busy=false, calculation=null;
  let directSources=[], directMaterials=[], directSerial=0, searchSerial=0;
  let historyProjectId=null, packaging=false;
  const notice = (text,error=false) => { $('recipeNotice').textContent=text; $('recipeNotice').classList.toggle('error',error); $('recipeNotice').hidden=!text; };
  async function api(path, payload) {
    const response = await fetch('/api/v1/'+path, payload===undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Request failed; inputs have been kept.');
    return result;
  }
  function applicable(role) {
    const kind=$('specimenClass').value;
    return !((kind==='paste' && ['sand','aggregate','recycled_fine','recycled_coarse'].includes(role)) ||
      (kind==='mortar' && ['aggregate','recycled_coarse'].includes(role)));
  }
  function invalidate() {
    revision++; calculation=null; $('exportRecipe').disabled=true;
    $('recipeResultBody').className='card empty-state';
    $('recipeResultBody').innerHTML='<h2>Inputs changed</h2>';
  }
  function syncReference() {
    const field=$('referenceConcreteCode'), previous=field.value;
    const concrete=$('specimenClass').value==='concrete';
    const strength=Number($('strengthMpa').value);
    const matches=concrete && $('strengthMpa').value!==''
      ? schema.concrete_references.filter(item=>Math.abs(item.strength_mpa-strength)<1e-6) : [];
    const mixing=$('preparationMode').value==='mixing';
    const scm=materials.find(item=>item.id===$('scmItem').value);
    const outdatedScm=Number($('mass_scm').value)>0 && scm && scm.background_fingerprint!==schema.background_fingerprint;
    const ready=concrete && mixing && !outdatedScm && Number($('strengthAge').value)===28 && $('strengthMatched').checked;
    const prompt=!concrete?'Select Concrete as specimen class':!mixing?'Select Mixing inventory first':outdatedScm?'Recalculate the saved SCM first':
      !$('strengthMpa').value?'Enter measured strength first':!ready?'Confirm 28-day strength first':
      matches.length?'Select a matching production activity':'No exact ecoinvent MPa class';
    field.innerHTML=`<option value="">${prompt}</option>`+matches.map(item=>{
      const description=item.name.replace(/^concrete production,\s*\d+(?:\.\d+)?MPa,?\s*/, '');
      return `<option value="${esc(item.code)}">${esc(item.location+' · '+description)}${item.age_days===28?' · 28 d':''}</option>`;
    }).join('');
    field.value=ready && matches.some(item=>item.code===previous)?previous:'';
    field.disabled=!ready || !matches.length;
  }
  function syncFields(clearDisallowed=false) {
    roles.forEach(role=>{
      const visible=applicable(role);
      $('row_'+role).hidden=!visible; $('rhoLabel_'+role).hidden=!visible;
      if (!visible && clearDisallowed) $('mass_'+role).value=0;
      $('mass_'+role).disabled=!visible;
    });
    const batch=$('recipeBasis').value==='batch';
    $('massUnit').textContent=batch?'Mass · kg/batch':'Mass · kg/m³';
    document.querySelectorAll('.direct-unit').forEach(node=>node.textContent=batch?'kg/batch':'kg/m³');
    $('batchControls').hidden=!batch;
    $('measuredVolumeLabel').hidden=$('volumeMode').value!=='measured';
    $('measuredVolume').required=batch && $('volumeMode').value==='measured';
    $('recycledControls').hidden=!(Number($('mass_recycled_fine').value)+Number($('mass_recycled_coarse').value));
    const foam=$('specimenClass').value==='foam_concrete';
    $('preparationMode').querySelector('option[value="mixing"]').disabled=foam || !schema.preparation.available;
    $('preparationMode').querySelector('option[value="foam"]').disabled=!foam;
    if(!foam && $('preparationMode').value==='foam') $('preparationMode').value=schema.preparation.available?'mixing':'none';
    $('foamPreparationFields').hidden=$('preparationMode').value!=='foam';
    syncReference();
    syncHistorySelection();
    syncDelivery();
  }
  function selectItem(id, changeDensity=true) {
    $('scmItem').value=id;
    $('strengthMatched').checked=false;
    const item=materials.find(m=>m.id===id);
    if (item && changeDensity) $('rho_scm').value=item.density_kg_m3;
    if (!item && changeDensity) $('rho_scm').value='';
    if (!id) $('mass_scm').value=0;
    setDelivery(deliveryDefaults(item));
    syncFields(); invalidate();
  }
  function deliveryDefaults(item) {
    return item?.recipe_transport || {enabled:false};
  }
  function setDelivery(config={enabled:false}) {
    $('scmTransportEnabled').checked=config.enabled===true;
    $('scmTransportDistance').value=config.distance_km??'';
    const code=config.activity_code??schema.default_freight_code;
    $('scmTransportSource').innerHTML=schema.freight.map(r=>`<option value="${esc(r.code)}">${esc(r.name)} · ${esc(r.location)}</option>`).join('');
    if(!schema.freight.some(r=>r.code===code)) $('scmTransportSource').insertAdjacentHTML('afterbegin',`<option value="${esc(code)}">Saved freight unavailable — choose another dataset</option>`);
    $('scmTransportSource').value=code;
  }
  function deliveryPayload() {
    return {enabled:$('scmTransportEnabled').checked&&!$('scmTransportEnabled').disabled,
      distance_km:$('scmTransportDistance').value,moisture_percent:0,activity_code:$('scmTransportSource').value};
  }
  function syncDelivery() {
    const item=materials.find(m=>m.id===$('scmItem').value);
    const available=!!item&&Number($('mass_scm').value)>0;
    $('scmTransportEnabled').disabled=!available;
    const on=available&&$('scmTransportEnabled').checked;
    $('scmTransportFields').hidden=!on;
    ['Distance','Source'].forEach(suffix=>$('scmTransport'+suffix).disabled=!on);
    $('scmTransportDistance').required=on;
  }
  const selectedProject = () => projects.find(p=>'project:'+p.id===$('scmItem').value);
  function syncHistorySelection() {
    const project=selectedProject();
    $('prepareHistoryScm').hidden=!project?.ready_to_package;
    $('reviewHistoryScm').hidden=!project;
    if (project) $('reviewHistoryScm').href='/?project='+encodeURIComponent(project.id);
    $('scmSelectionSummary').hidden=!project;
    $('scmHistoryHelp').hidden=!project || project.ready_to_package;
    if(project){
      $('scmSelectionSummary').textContent=project.process_names.join(' → ') || 'Saved SCM process inputs';
      $('scmHistoryHelp').textContent=project.ready_to_package ? '' : 'Complete this route: '+project.issues.join('; ');
    }else{
      $('scmSelectionSummary').textContent='';
      $('scmHistoryHelp').textContent='';
    }
  }
  function renderHistory() {
    const previous=$('scmItem').value;
    $('scmItem').innerHTML='<option value="">Choose from SCM history / no SCM</option>'+
      (materials.length?'<optgroup label="Saved SCM materials">'+materials.map(m=>`<option value="${esc(m.id)}">${esc(m.name)} · ${esc(m.created_at.slice(0,10))}</option>`).join('')+'</optgroup>':'')+
      (projects.length?'<optgroup label="Saved SCM projects — reuse process inputs">'+projects.map(p=>`<option value="project:${p.id}">${esc(p.name)} · ${esc(p.created_at.slice(0,10))} · ${p.ready_to_package?'prepare material':'needs inputs'}</option>`).join('')+'</optgroup>':'');
    if(materials.some(m=>m.id===previous)||projects.some(p=>'project:'+p.id===previous)) $('scmItem').value=previous;
  }
  async function refreshHistory() {
    const previous=$('scmItem').value;
    const data=await api('scm-history');materials=data.materials;projects=data.projects;renderHistory();
    if(previous!==$('scmItem').value) selectItem($('scmItem').value);
    else syncHistorySelection();
  }
  function prepareHistoryScm() {
    const project=selectedProject();
    if(!project?.ready_to_package)return;
    historyProjectId=project.id;
    $('historyScmName').value=project.name;
    $('historyScmRoute').textContent=project.name+' · '+project.process_names.join(' → ');
    $('historyScmDensity').value='';$('historyScmMessage').textContent='';
    $('historyScmDialog').showModal();
  }
  async function packageHistory(event) {
    event.preventDefault();if(packaging||historyProjectId===null)return;
    packaging=true;$('confirmHistoryScm').disabled=true;
    const atRevision=revision;
    $('historyScmMessage').textContent='Calculating the saved SCM inputs…';
    try{
      const item=await api('scm-items/from-project/'+historyProjectId,{name:$('historyScmName').value,
        density_kg_m3:$('historyScmDensity').value});
      materials.unshift(item);renderHistory();
      const applyCurrent=revision===atRevision;
      if(applyCurrent) selectItem(item.id);
      else syncHistorySelection();
      $('historyScmDialog').close();notice(applyCurrent?'Saved SCM is selected. Enter its mass in this mix.':'SCM material saved to history. Your current mix selection was kept.');
    }catch(error){$('historyScmMessage').textContent=error.message;}
    finally{packaging=false;$('confirmHistoryScm').disabled=false;}
  }
  function cementOptions() {
    const chosen=$('cementCode').value || schema.providers.cement.code;
    $('cementCode').innerHTML=schema.cements.map(c=>`<option value="${esc(c.code)}">${esc(c.name)} — ${esc(c.location)}</option>`).join('');
    $('cementCode').value=chosen;
  }
  function renderDirectMaterials() {
    $('directMaterialRows').innerHTML=directMaterials.map(item=>`<div class="direct-material-row" data-direct-id="${item.id}"><div class="direct-material-title"><strong>${esc(item.source.name)} · ${esc(item.source.location)}</strong></div><label>Role in mixture<select data-direct-field="category"><option value="binder" ${item.category==='binder'?'selected':''}>Binder</option><option value="aggregate" ${item.category==='aggregate'?'selected':''}>Aggregate</option><option value="other" ${item.category==='other'?'selected':''}>Other material / admixture</option></select></label><label>Mass · <span class="direct-unit">${$('recipeBasis').value==='batch'?'kg/batch':'kg/m³'}</span><input data-direct-field="mass_kg" type="number" min="0.000001" step="any" required value="${esc(item.mass_kg)}"></label><label>Particle density · kg/m³<input data-direct-field="density_kg_m3" type="number" min="0.000001" step="any" value="${esc(item.density_kg_m3??'')}"></label><button class="text-button" type="button" data-remove-direct="${item.id}">Remove</button></div>`).join('');
  }
  async function searchDirectMaterials() {
    const query=$('directSearch').value.trim(), serial=++searchSerial, results=$('directSearchResults');
    directSources=[];results.hidden=true;results.innerHTML='';
    if(query.length<2)return;
    try{
      const result=await api('recipe-materials?q='+encodeURIComponent(query));
      if(serial!==searchSerial)return;
      directSources=result.items;
      results.innerHTML=directSources.length?'<option value="">Select a material</option>'+directSources.map(r=>`<option value="${esc(r.code)}">${esc(r.name)} · ${esc(r.location)}</option>`).join(''):'<option value="">No matching materials</option>';
      results.hidden=false;
    }catch(error){if(serial===searchSerial)notice(error.message,true);}
  }
  function addDirectMaterial(source, values={}) {
    if(directMaterials.some(item=>item.source.code===source.code)){notice('This ecoinvent activity is already in the mix. Edit its mass in the row below.',true);return false;}
    directMaterials.push({id:++directSerial,source,category:values.category||'other',mass_kg:values.mass_kg??'',density_kg_m3:values.density_kg_m3??''});
    renderDirectMaterials();invalidate();
    return true;
  }
  function directPayload() {
    return directMaterials.map(item=>({activity_code:item.source.code,category:item.category,mass_kg:item.mass_kg,density_kg_m3:item.density_kg_m3}));
  }
  function payload() {
    const amounts={}, densities={};
    roles.forEach(role=>{ amounts[role]=$('mass_'+role).value; if(applicable(role)&&$('rho_'+role).value!=='') densities[role]=$('rho_'+role).value; });
    return {name:$('recipeName').value,specimen_class:$('specimenClass').value,basis:$('recipeBasis').value,
      scm_item_id:materials.some(m=>m.id===$('scmItem').value)?$('scmItem').value:null,cement_code:$('cementCode').value,amounts,densities,
      volume_mode:$('volumeMode').value,measured_volume_m3:$('measuredVolume').value,air_percent:$('airPercent').value,
      recycled_yield_fraction:Number($('recycledYield').value)/100,direct_materials:directPayload(),
      preparation_mode:$('preparationMode').value,foam_reference_mass_kg:$('foamReferenceMass').value,
      foam_machine_kg_per_unit:$('foamMachineKgPerUnit').value,
      scm_transport:deliveryPayload(),
      strength_mpa:$('strengthMpa').value,strength_age_days:$('strengthAge').value,strength_matches_recipe:$('strengthMatched').checked,
      reference_concrete_code:$('referenceConcreteCode').value};
  }
  function showResult(result,input,saved=null) {
    calculation={input,result,saved_recipe_id:saved?.id||null}; $('exportRecipe').disabled=false;
    const p=result.performance, prep=result.preparation;
    const delivery=result.scm_transport;
    const deliveryRow=delivery?`<tr><td><strong>SCM → mixing plant</strong><small>${delivery.included?esc(delivery.provider.name+' · '+delivery.provider.location)+' · '+fmt(delivery.ton_km_m3,5)+' tonne-km/m³ · '+fmt(delivery.factor_kg_co2e_tkm,6)+' kg CO₂e/tonne-km':'Not included'}</small></td><td class="numeric">—</td><td class="numeric">—</td><td class="numeric">${fmt(delivery.gwp_kg_co2e_m3,4)}</td></tr>`:'';
    const source=row=>row.source.item_id ? `${row.source.name} · saved SCM` : `${row.source.name}${row.source.location?' · '+row.source.location:''}`;
    const className=result.specimen_class.replaceAll('_',' ');
    const prepName=prep.mode==='foam'?'Foam-concrete mixing':prep.included?'Mixing':'Mixing excluded';
    const prepDetail=prep.mode==='foam'?`Provisional · ${fmt(prep.electricity_kwh_m3,4)} kWh + ${fmt(prep.machine_kg_m3,6)} kg machine/m³`:prep.included?'':'Constituent-only result';
    const ref=result.reference_concrete;
    const changeLabel=ref?.reduction_percent>0?'Indicative GWP reduction':ref?.reduction_percent<0?'Indicative GWP increase':'Indicative GWP change';
    const referenceHtml=ref?`<section class="card reference-result"><div class="card-heading"><h2>Reference concrete · ${fmt(ref.strength_mpa,0)} MPa · ${esc(ref.source.location)}</h2><span class="quiet-badge">${ref.reference_age_days===28?'28-day strength documented':'Reference age unstated'}</span></div><div class="reference-metrics"><div><span>Reference GWP100</span><strong>${fmt(ref.gwp_kg_co2e_m3,2)}</strong><small>kg CO₂e/m³</small></div><div><span>Current recipe</span><strong>${fmt(result.gwp_kg_co2e_m3,2)}</strong><small>kg CO₂e/m³</small></div><div class="reference-delta ${ref.reduction_percent<0?'is-increase':''}"><span>${changeLabel}</span><strong>${fmt(Math.abs(ref.reduction_percent),1)}%</strong></div></div><details><summary>Reference source</summary><p>${esc(ref.source.name)} · ${esc(ref.source.location)} · ${esc(ref.source.database)}</p><p>${esc(ref.age_note)}</p><p>${esc(ref.boundary_note)}</p></details></section>`:'';
    $('recipeResultBody').className='';
    $('recipeResultBody').innerHTML=`<div class="recipe-metrics"><div class="card"><span class="metric-label">Mixture GWP100</span><strong>${fmt(result.gwp_kg_co2e_m3,2)}</strong><small>kg CO₂e per m³ fresh ${esc(className)}</small></div><div class="card"><span class="metric-label">28-day performance index</span><strong>${fmt(p.index_kg_co2e_m3_mpa,3)}</strong><small>kg CO₂e / (m³ · MPa)</small></div><div class="card"><span class="metric-label">Saved SCM share of binder</span><strong>${fmt(result.scm_replacement_fraction*100,1)}%</strong><small>Water / binder = ${fmt(result.water_binder_ratio,3)}</small></div></div>${referenceHtml}
    <div class="card"><div class="card-heading"><h2>GWP breakdown</h2><span class="quiet-badge">${esc(className)} · 1 m³</span></div><div class="table-wrap"><table><thead><tr><th>Ingredient / inventory</th><th class="numeric">kg/m³</th><th class="numeric">kg CO₂e/kg</th><th class="numeric">kg CO₂e/m³</th></tr></thead><tbody>${result.ingredients.map(r=>`<tr><td><strong>${esc(r.ingredient==='direct'?r.source.reference_product:labels[r.ingredient])}</strong><small>${esc(source(r))}${r.ingredient==='direct'?' · '+esc(r.category):''}</small></td><td class="numeric">${fmt(r.mass_kg_m3,3)}</td><td class="numeric">${fmt(r.factor_kg_co2e_kg,6)}</td><td class="numeric">${fmt(r.gwp_kg_co2e_m3,4)}</td></tr>`).join('')}${deliveryRow}<tr><td><strong>${esc(prepName)}</strong>${prepDetail?`<small>${esc(prepDetail)}</small>`:''}</td><td class="numeric">—</td><td class="numeric">—</td><td class="numeric">${fmt(prep.gwp_kg_co2e_m3,4)}</td></tr><tr><td><strong>Total GWP100</strong></td><td></td><td></td><td class="numeric"><strong>${fmt(result.gwp_kg_co2e_m3,4)}</strong></td></tr></tbody></table></div><p class="result-summary">Volume ${fmt(result.batch_volume_m3,7)} m³ · Density ${fmt(result.fresh_density_kg_m3,1)} kg/m³ · Binder ${fmt(result.binder_kg_m3,2)} kg/m³</p>${p.strength_mpa!=null?`<p><strong>Performance:</strong> ${esc(p.note)}</p>`:''}<details class="result-assumptions"><summary>Assumptions &amp; limits</summary><p>${esc(result.volume_note)}</p><ul class="result-notes">${result.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}<li>Negative SCM GWP is conditional, not verified removal.</li></ul><p class="muted">EF v3.1 no LT · GWP100</p></details></div>`;
  }
  async function calculate(save) {
    if(busy || !$('recipeForm').reportValidity()) return;
    if(Number($('mass_scm').value)>0&&!materials.some(m=>m.id===$('scmItem').value)){
      notice(selectedProject()?'Prepare the selected saved SCM first, or open its route to complete the missing inputs.':'Choose a saved SCM from history before entering its mass.',true);return;
    }
    const input=payload(), atRevision=revision;
    busy=true; $('calculateRecipe').disabled=true; $('saveRecipe').disabled=true;
    notice(save?'Calculating and saving an immutable recipe snapshot…':'Calculating GWP from the selected inventories…');
    try {
      const data=await api(save?'recipes':'recipes/calculate',input);
      if(save) await refreshRecipes();
      if(revision!==atRevision) {notice(save?'The submitted recipe was saved, but the form has since changed. Recalculate the current inputs.':'Inputs changed during calculation; recalculate the current recipe.');return;}
      showResult(save?data.result:data,input,save?data:null);
      notice(save?'Recipe snapshot saved. Subsequent edits create a new entry.':'Recipe calculated. GWP and performance are shown below.');
      $('recipeResults').scrollIntoView({behavior:'smooth',block:'start'});
    } catch(error){notice(error.message,true);}
    finally{busy=false;$('calculateRecipe').disabled=false;$('saveRecipe').disabled=false;}
  }
  async function refreshRecipes(){
    const {items}=await api('recipes');
    $('savedRecipeList').innerHTML=items.length?items.map(r=>`<div class="saved-recipe"><div><strong>${esc(r.name)} · ${esc(r.created_at)} UTC</strong></div><button type="button" class="button" data-recipe="${esc(r.id)}">Open snapshot</button></div>`).join(''):'<p>No saved recipes yet.</p>';
    document.querySelectorAll('[data-recipe]').forEach(button=>button.addEventListener('click',()=>openRecipe(button.dataset.recipe)));
  }
  async function openRecipe(id){
    const atRevision=revision;
    try{
      const record=await api('recipes/'+id);
      if(revision!==atRevision){notice('The form changed while loading. Click Open snapshot again to replace it.');return;}
      const p=record.payload;
      $('recipeName').value=p.name;$('specimenClass').value=p.specimen_class;$('recipeBasis').value=p.basis??schema.input_defaults.basis;
      cementOptions();$('cementCode').value=p.cement_code||schema.providers.cement.code;
      $('scmItem').value=p.scm_item_id||'';
      roles.forEach(role=>{$('mass_'+role).value=p.amounts[role]||0;$('rho_'+role).value=p.densities?.[role]||schema.default_densities[role]||materials.find(m=>m.id===p.scm_item_id)?.density_kg_m3||'';});
      $('volumeMode').value=p.volume_mode||schema.input_defaults.volume_mode;$('measuredVolume').value=p.measured_volume_m3||'';$('airPercent').value=p.air_percent??schema.input_defaults.air_percent;
      $('recycledYield').value=(p.recycled_yield_fraction??schema.input_defaults.recycled_yield_fraction)*100;
      $('preparationMode').value=p.preparation_mode==='common'?'mixing':(p.preparation_mode||(p.include_preparation===false?'none':schema.input_defaults.preparation_mode));
      $('foamReferenceMass').value=p.foam_reference_mass_kg??schema.input_defaults.foam_reference_mass_kg;
      $('foamMachineKgPerUnit').value=p.foam_machine_kg_per_unit??schema.input_defaults.foam_machine_kg_per_unit;
      directMaterials=[];
      (p.direct_materials||[]).forEach((entry,index)=>{
        const source=record.result.ingredients.filter(row=>row.ingredient==='direct')[index]?.source;
        if(source) directMaterials.push({id:++directSerial,source,category:entry.category||'other',mass_kg:entry.mass_kg,density_kg_m3:entry.density_kg_m3??''});
      });
      renderDirectMaterials();
      setDelivery(p.scm_transport??deliveryDefaults(materials.find(m=>m.id===p.scm_item_id)));
      $('strengthMpa').value=p.strength_mpa??'';$('strengthAge').value=p.strength_age_days??28;$('strengthMatched').checked=!!p.strength_matches_recipe;
      syncFields();$('referenceConcreteCode').value=p.reference_concrete_code||'';revision++;
      showResult(record.result,p,record);
      notice(Number(p.scm_transport?.moisture_percent||0)>0
        ? 'This saved result used moist cargo. New calculations use dry SCM mass for delivery.'
        : 'Opened the saved inputs and result snapshot. Recalculate to use today’s background factors.');
    }catch(error){notice(error.message,true);}
  }
  async function init(){
    try {
      const [s,h]=await Promise.all([api('recipe-schema'),api('scm-history')]);schema=s;materials=h.materials;projects=h.projects;
      $('recipeName').value=s.form_defaults.name;$('specimenClass').value=s.form_defaults.specimen_class;
      $('recipeBasis').value=s.input_defaults.basis;$('volumeMode').value=s.input_defaults.volume_mode;
      $('airPercent').value=s.input_defaults.air_percent;
      $('recycledYield').value=s.input_defaults.recycled_yield_fraction*100;
      $('preparationMode').value=s.input_defaults.preparation_mode;
      $('foamReferenceMass').value=s.input_defaults.foam_reference_mass_kg;
      $('foamMachineKgPerUnit').value=s.input_defaults.foam_machine_kg_per_unit;
      $('recycledDefaultYield').textContent=fmt(s.input_defaults.recycled_yield_fraction*100);
      $('foamDefaultsSource').textContent=`${fmt(s.foam_inventory.electricity_kwh,6)} kWh + ${Number(s.foam_inventory.machine_unit).toExponential(2)} machine unit per reference mass. The ${fmt(s.input_defaults.foam_reference_mass_kg/1000)} tonne basis is provisional; confirm the ${fmt(s.input_defaults.foam_machine_kg_per_unit)} kg/unit machine conversion before final LCA reporting.`;
      $('ingredientRows').innerHTML=roles.map(role=>{
        if(role==='scm')return `<div class="ingredient-row scm-history-row" id="row_scm"><div><label for="scmItem"><strong>Your SCM</strong></label><select id="scmItem" aria-label="Your SCM from history"></select></div><label>SCM mass<input id="mass_scm" aria-label="Your SCM mass" type="number" min="0" step="any" required value="${s.form_defaults.amounts.scm}"></label><div class="scm-history-detail"><strong id="scmSelectionSummary" hidden></strong><p id="scmHistoryHelp" hidden></p><div class="scm-history-actions"><button type="button" class="button primary" id="prepareHistoryScm" hidden>Use this saved SCM</button><a class="button" id="reviewHistoryScm" href="/" target="_blank" rel="noopener" hidden>Open SCM route ↗</a><button type="button" class="text-button" id="refreshMaterials">Refresh history</button><a class="text-button" href="/">Build a new SCM →</a></div></div></div>`;
        return `<div class="ingredient-row" id="row_${role}"><div><label for="mass_${role}"><strong>${labels[role]}</strong></label></div><input id="mass_${role}" aria-label="${labels[role]} mass" type="number" min="0" step="any" required value="${s.form_defaults.amounts[role]}"></div>`;
      }).join('');
      $('densityFields').innerHTML=roles.map(role=>`<label id="rhoLabel_${role}" for="rho_${role}">${labels[role]} · kg/m³<input id="rho_${role}" type="number" min="0.001" step="any" value="${s.default_densities[role]||''}"></label>`).join('');
      cementOptions();renderHistory();setDelivery();syncFields();
      $('directSearch').addEventListener('input',searchDirectMaterials);
      $('directSearch').addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();if(!$('directSearchResults').hidden)$('directSearchResults').focus();}});
      $('directSearchResults').addEventListener('change',()=>{
        const source=directSources.find(r=>r.code===$('directSearchResults').value);
        if(!source)return;
        $('directSearchResults').value='';
        if(addDirectMaterial(source)){
          searchSerial++;directSources=[];$('directSearch').value='';$('directSearchResults').hidden=true;$('directSearchResults').innerHTML='';
        }
      });
      $('directMaterialRows').addEventListener('click',event=>{
        const id=Number(event.target.dataset.removeDirect);
        if(!id)return;
        directMaterials=directMaterials.filter(item=>item.id!==id);renderDirectMaterials();invalidate();
      });
      $('prepareHistoryScm').addEventListener('click',prepareHistoryScm);
      $('refreshMaterials').addEventListener('click',()=>refreshHistory().catch(e=>notice(e.message,true)));
      const mixingOption=$('preparationMode').querySelector('option[value="mixing"]');
      mixingOption.disabled=!s.preparation.available;
      if(!s.preparation.available) mixingOption.textContent='Mixing · unavailable';
      if(!s.preparation.available) $('preparationMode').value='none';
      $('mixingInventoryBasis').hidden=!s.preparation.available;
      $('prepSource').textContent=s.preparation.available
        ? `${fmt(s.preparation.electricity_kwh_m3,3)} kWh electricity · ${fmt(s.preparation.gwp_kg_co2e_m3,4)} kg CO₂e/m³ for the full mixing inventory.`
        : `${s.preparation.reason} Select no mixing inventory or foam mixing.`;
      const selected=new URLSearchParams(location.search).get('scm');
      if(selected && materials.some(m=>m.id===selected)) selectItem(selected);
      $('recipeFields').disabled=false;
      await refreshRecipes();
    }catch(error){notice(error.message,true);}
  }
  $('recipeForm').addEventListener('input',event=>{
    if(event.target.id==='directSearch')return;
    const directRow=event.target.closest('[data-direct-id]');
    if(directRow&&event.target.dataset.directField){
      const item=directMaterials.find(row=>row.id===Number(directRow.dataset.directId));
      if(item)item[event.target.dataset.directField]=event.target.value;
    }
    // Editing composition or conversion invalidates the prior strength match.
    if(['strengthMpa','strengthAge'].includes(event.target.id)
        || (!event.target.id.startsWith('scmTransport')&&!['recipeName','strengthMatched','preparationMode','referenceConcreteCode'].includes(event.target.id))) $('strengthMatched').checked=false;
    if(event.target.id==='specimenClass') {
      $('preparationMode').value=$('specimenClass').value==='foam_concrete'?'foam':schema.preparation.available?'mixing':'none';
      syncFields(true);
    }
    else if(event.target.id==='scmItem') {selectItem($('scmItem').value);return;}
    else syncFields();
    invalidate();
  });
  $('recipeForm').addEventListener('submit',event=>{event.preventDefault();calculate(false);});
  $('saveRecipe').addEventListener('click',()=>calculate(true));
  $('refreshRecipes').addEventListener('click',()=>refreshRecipes().catch(e=>notice(e.message,true)));
  $('historyScmForm').addEventListener('submit',packageHistory);
  $('closeHistoryScm').addEventListener('click',()=>$('historyScmDialog').close());
  $('exportRecipe').addEventListener('click',()=>{if(calculation){$('recipeExportText').value=JSON.stringify(calculation,null,2);$('recipeExportDialog').showModal();}});
  $('closeRecipeExport').addEventListener('click',()=>$('recipeExportDialog').close());
  $('downloadRecipeJson').addEventListener('click',()=>{if(!calculation)return;const link=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(calculation,null,2)],{type:'application/json'}));link.href=url;link.download='mixture-recipe.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  init();
})();
