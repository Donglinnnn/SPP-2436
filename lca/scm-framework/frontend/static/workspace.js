const processOrder = [
  "Crushing",
  "Grinding",
  "Sieving",
  "Sorting",
  "Thermal activation",
  "Carbonation"
];

const templates = {
  "Crushing": [["Target product yield", "yield_fraction", "%"]],
  "Grinding": [
    ["Feed particle size F80", "F80_um", "um"],
    ["Product particle size P80", "P80_um", "um"],
    ["Bond work index Wi", "Wi_value", "kWh/t"],
    ["Fine K", "fine_K", "kWh·µm/t"],
    ["Target product yield", "yield_fraction", "%"]
  ],
  "Sieving": [
    ["Input mass", "input_mass_kg", "kg"],
    ["Output mass", "output_mass_kg", "kg"]
  ],
  "Sorting": [
    ["Input mass", "input_mass_kg", "kg"],
    ["Output mass", "output_mass_kg", "kg"]
  ],
  "Thermal activation": [
    ["Activation temperature", "activation_temperature_C", "deg C"],
    ["Holding time", "holding_time_h", "h"],
    ["TGA intervals table", "tga_intervals_table", "table/json/text"]
  ],
  "Carbonation": [
    ["CO2 uptake", "co2_uptake_kg", "kg/kg solid"],
    ["Process water input", "water_kg", "kg/kg solid"],
    ["Reaction time", "t_reaction_h", "h"],
    ["Reaction temperature", "t_reaction_C", "deg C"]
  ]
};


const iconPaths = {
  route:'<circle cx="5" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><path d="M7 5h7a4 4 0 0 1 0 8H9a4 4 0 0 0 0 8h8"/>',
  chart:'<path d="M4 4v16h16M8 16v-4m5 4V8m5 8V5"/>',
  folder:'<path d="M3 7V5h7l2 3h9v12H3z"/>',
  book:'<path d="M12 5v15M12 5C8 2 3 4 3 4v14s5-2 9 2c4-4 9-2 9-2V4s-5-2-9 1z"/>',
  external:'<path d="M14 3h7v7m0-7-11 11M10 3H3v18h18v-7"/>',
  file:'<path d="M5 3h9l5 5v13H5zM14 3v6h5M8 13h8m-8 4h5"/>',
  save:'<path d="M4 3h13l4 4v14H3V3h1m3 0v6h9V3M7 21v-8h10v8"/>',
  flask:'<path d="M9 3h6m-5 0v7l-6 9a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2l-6-9V3M7 15h10"/>',
  box:'<path d="m12 3 9 5v9l-9 5-9-5V8zM3 8l9 5 9-5m-9 5v9M7 5l9 5"/>',
  play:'<path d="m8 4 12 8-12 8z"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  refresh:'<path d="M20 7a9 9 0 1 0 1 8M20 3v5h-5"/>',
  close:'<path d="m5 5 14 14M5 19 19 5"/>',
  check:'<path d="m5 12 4 4 10-10"/>',
  crush:'<path d="M4 5h16l-4 7H8zM6 16l3 4m2-5 1 5m4-4 2 4M9 3v2m6-2v2"/>',
  grind:'<path d="M4 5h16M7 5v6a5 5 0 0 0 10 0V5M5 17h14M8 21h8M4 9h3m10 0h3M12 5v8m-3-3 3 3 3-3"/>',
  sieve:'<path d="M3 7h18v10H3zM7 7v10m5-10v10m5-10v10M3 12h18M6 4h12M6 20h12"/>',
  sort:'<path d="M12 3v5m0 0L5 13m7-5 7 5M3 14h4v6H3zm14 0h4v6h-4z"/>',
  heat:'<path d="M13 3c2 4-2 6 2 8 1-2 2-2 2-3 7 8 2 13-5 13-6 0-10-5-5-11 0 4 2 4 3 3-2-4 2-6 3-10z"/>',
  carbon:'<circle cx="12" cy="12" r="4"/><circle cx="4" cy="5" r="2"/><circle cx="20" cy="5" r="2"/><circle cx="12" cy="21" r="1.5"/><path d="m6 7 3 3m6 0 3-3m-6 9v3"/>',
  wash:'<path d="M12 3c-2 4-7 8-7 12a7 7 0 0 0 14 0c0-4-5-8-7-12zM8 14a4 4 0 0 0 4 4"/>',
  dry:'<path d="M5 21V3h4v18m-4-5h4m7-13c-4 4 4 6 0 10s4 5 0 8m5-18c-4 4 4 6 0 10s4 5 0 8"/>',
  blend:'<path d="M5 7h14l-2 14H7zM9 3l6 12M7 12h10M15 3l-3 5"/>'
};
const processIcons = {Crushing:'crush',Grinding:'grind',Sieving:'sieve',Screening:'sieve',Sorting:'sort','Thermal activation':'heat',Carbonation:'carbon'};
const icon = name => '<svg viewBox="0 0 24 24" aria-hidden="true">'+(iconPaths[name]||iconPaths.file)+'</svg>';
const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const toText = value => value == null ? '' : typeof value === 'object' ? JSON.stringify(value,null,2) : String(value);
const qs = selector => document.querySelector(selector);
const qsa = selector => [...document.querySelectorAll(selector)];
const storageKey = 'scm-framework-workspace-v2';
const feedstockBurdenRule = 'excluded waste burden';
const state = {selected:['Grinding'],current:'Grinding',parameters:{},materialType:'Waste',projectId:null,revision:0,referenceProduct:'SCM product',systemBoundary:'A1-A3',lcaSettings:{energy_scenario_version:ScmLca.pairedEnergyVersion,input_defaults_version:ScmLca.inputDefaultsVersion,electricity_scenario:'E0'}};
let schema = null, lastCalculation = null, lastCalculationRevision = -1, draftTimer = null, calculating = false;
function hydrateIcons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));}
function notify(message,error=false){const el=qs('#notification');el.textContent=message;el.classList.toggle('error',error);el.hidden=false;}
function ensureProcess(name){
  if(name==='Carbonation'){
    const rows=state.parameters[name]||[];
    if(!rows.some(row=>toText(row.value).trim()))useConditionInputs();
  }
  const existing=(state.parameters[name]||[]).map(row=>{
    const template=(templates[name]||[]).find(([,code])=>code===row.parameter_code);
    return {...row,parameter_label:row.parameter_label||template?.[0]||row.parameter_code.replaceAll('_',' '),unit:row.unit??template?.[2]??''};
  });
  const codes=new Set(existing.map(p=>p.parameter_code));
  state.parameters[name]=[...(templates[name]||[]).filter(([,code])=>!codes.has(code)).map(([label,code,unit])=>({parameter_code:code,parameter_label:label,value:'',unit,provenance:'ASM',source_note:''})),...existing];
}
function specsFor(name){
  return schema?.processes?.[name]?.parameters||{};
}
function saveForm(){
  syncTgaEditor();
  syncThermalSettingsEditor();
  syncCarbonationEditor();
  const rows=qsa('#paramForm [data-parameter-code]').map(row=>({
    ...(state.parameters[state.current]||[]).find(p=>p.parameter_code===row.dataset.parameterCode),
    parameter_code:row.dataset.parameterCode,parameter_label:row.dataset.parameterLabel,
    value:row.querySelector('[data-field="value"]').value,unit:row.querySelector('[data-field="unit"]').value
  }));
  if(rows.length){
    const updated=new Set(rows.map(p=>p.parameter_code));
    state.parameters[state.current]=[...(state.parameters[state.current]||[]).filter(p=>!updated.has(p.parameter_code)),...rows];
  }
  const library=qs('#grindingLibrary');
  if(state.current==='Grinding'&&library){
    const value=library.value==='__saved__'?'':library.value;
    state.parameters.Grinding=[...(state.parameters.Grinding||[]).filter(p=>p.parameter_code!=='grinding_library_key'),{parameter_code:'grinding_library_key',parameter_label:'Background material',value,unit:''}];
  }
}
const libraryOwnedGrinding = new Set(['Wi_value','material_key','fine_K','fine_n','transition_um','fine_target_um','fine_anchor_energy_kwh_per_tonne']);
const fixedProcessNames = ['Crushing','Sieving','Sorting'];
const recoveryCodes = ['coproduct_fraction','allocation_method','inventory_basis'];
function parameterValue(rows,code){return rows.find(row=>row.parameter_code===code)?.value??'';}
function hasSavedGrinding(rows){return ['Wi_value','material_key','fine_K','fine_anchor_energy_kwh_per_tonne'].some(code=>toText(parameterValue(rows,code)).trim()!=='');}
function parametersForRequest(name,rows){
  if(name==='Carbonation'&&parameterValue(rows,'carbonation_model')==='general_operating_v2')return rows.filter(row=>['carbonation_model','co2_uptake_kg','t_reaction_h','condition_inputs'].includes(row.parameter_code));
  if(fixedProcessNames.includes(name)){
    const allowed=new Set(['inventory_id',...recoveryCodes,...(templates[name]||[]).map(([,code])=>code)]);
    const selected=rows.filter(row=>allowed.has(row.parameter_code));
    if(!selected.some(row=>row.parameter_code==='inventory_id'))selected.push({parameter_code:'inventory_id',value:name==='Crushing'?'user-crushing-2026-09-22':'cycle2-'+name.toLowerCase()+'-v1',unit:''});
    return selected;
  }
  if(name==='Grinding'){
    const key=parameterValue(rows,'grinding_library_key');
    if(key==='__custom__')return rows.filter(row=>row.parameter_code!=='grinding_library_key'&&(!libraryOwnedGrinding.has(row.parameter_code)||['Wi_value','fine_K'].includes(row.parameter_code)));
    if(key)return rows.filter(row=>!libraryOwnedGrinding.has(row.parameter_code)||['Wi_value','fine_K'].includes(row.parameter_code));
  }
  return rows;
}
function getFlowSteps(){return [qs('#materialName').value||'Input material',...state.selected,'SCM product'];}
function collectPayload(){
  saveForm();
  return {
    product_type:'SCM',pathway_name:qs('#pathwayName').value,reference_product:state.referenceProduct,system_boundary:state.systemBoundary,
    project_id:state.projectId,functional_unit_kg:Number(qs('#functionalUnit').value),
    lca_settings:typeof ScmLca==='undefined'?state.lcaSettings:ScmLca.getSettings(),
    material:{material_type:state.materialType,material_name:qs('#materialName').value,location:qs('#locationName').value,feedstock_burden_rule:feedstockBurdenRule,note:qs('#materialNote').value},
    flow_chart:getFlowSteps(),processes:state.selected.map((name,i)=>({process_name:name,process_order:i+1,parameters:parametersForRequest(name,state.parameters[name]||[])}))
  };
}
function persistDraft(){
  try{localStorage.setItem(storageKey,JSON.stringify({payload:collectPayload(),allParameters:state.parameters,current:state.current}));}
  catch{}
}
function changed(){
  state.revision++;saveForm();renderFlow();renderCounts();clearTimeout(draftTimer);
  draftTimer=setTimeout(persistDraft,250);
  qs('#downloadResult').disabled=true;
  if(lastCalculation)qs('#resultCount').textContent='↻';
}
function renderCounts(){
  const count=state.selected.length;
  qs('#runLabel').textContent=count ? count+' '+(count===1?'process':'processes')+' selected' : 'Select a process';
}
function renderFlow(){
  qs('#projectFlow').innerHTML=getFlowSteps().map((name,i,all)=>(i?'<span class="flow-arrow" aria-hidden="true">→</span>':'')+'<span class="flow-step '+(i===0||i===all.length-1?'endpoint':'')+'">'+esc(name)+(i>0&&i<all.length-1?'<span class="flow-controls"><button type="button" data-move-process="'+esc(name)+'" data-direction="-1" aria-label="Move '+esc(name)+' earlier" '+(i===1?'disabled':'')+'>↑</button><button type="button" data-move-process="'+esc(name)+'" data-direction="1" aria-label="Move '+esc(name)+' later" '+(i===all.length-2?'disabled':'')+'>↓</button></span>':'')+'</span>').join('');
  qsa('[data-move-process]').forEach(button=>button.addEventListener('click',()=>moveProcess(button.dataset.moveProcess,Number(button.dataset.direction))));
}
function moveProcess(name,direction){
  const from=state.selected.indexOf(name),to=from+direction;
  if(from<0||to<0||to>=state.selected.length||![-1,1].includes(direction))return false;
  saveForm();[state.selected[from],state.selected[to]]=[state.selected[to],state.selected[from]];
  changed();persistDraft();return true;
}
function renderGrid(){
  if(typeof ScmLca!=='undefined')ScmLca.setCarbonationSelected(state.selected.includes('Carbonation'));
  qs('#processGrid').innerHTML=processOrder.map(name=>{
    const active=state.selected.includes(name);
    const current=name===state.current;
    return '<div class="process-node '+(active?'active ':'')+(current?'current':'')+'" data-process="'+esc(name)+'"><button class="process-toggle" aria-label="'+(active?'Exclude ':'Include ')+esc(name)+'" aria-pressed="'+active+'" data-toggle="'+esc(name)+'">'+icon('check')+'</button><button class="process-select" data-select="'+esc(name)+'" aria-label="Edit '+esc(name)+' inputs"><span class="process-icon">'+icon(processIcons[name])+'</span><strong>'+esc(name)+'</strong></button></div>';
  }).join('');
  qsa('[data-select]').forEach(el=>el.addEventListener('click',()=>{
    saveForm();state.current=el.dataset.select;const added=!state.selected.includes(state.current);
    if(added)state.selected.push(state.current);
    ensureProcess(state.current);renderGrid();renderForm();if(added)changed();else persistDraft();
  }));
  qsa('[data-toggle]').forEach(el=>el.addEventListener('click',()=>{
    saveForm();const name=el.dataset.toggle;
    state.selected=state.selected.includes(name)?state.selected.filter(x=>x!==name):[...state.selected,name];
    state.current=name;ensureProcess(name);renderGrid();renderForm();changed();
  }));
}
function fieldMarkup(row,spec={}){
  if(['yield_fraction','coproduct_fraction'].includes(row.parameter_code)&&(!row.unit||row.unit==='fraction')){
    const raw=toText(row.value);
    row={...row,unit:'%',value:raw.trim()&&Number.isFinite(Number(raw))?String(Number((Number(raw)*100).toPrecision(12))):raw};
  }
  if(row.parameter_code==='tga_intervals_table'){
    const editor=tgaEditorMarkup(row);
    if(editor!==null)return editor;
  }
  const code=row.parameter_code,label=row.parameter_label||code.replaceAll('_',' ');
  const value=toText(row.value), unit=row.unit??spec.unit??'';
  const attrs='data-field="value" aria-label="'+esc(label)+'"';
  let control;
  if(spec.choices?.length){
    const explicitDefault=['allocation_method','inventory_basis'].includes(code);
    const selectedValue=explicitDefault&&!value?spec.default:value;
    const choiceLabels={none:'All burdens to target (no allocation)',mass:'Mass allocation to recovered products',
      processed_input:'Per kg feed',target_output:'Per kg target product'};
    control='<select '+attrs+'>'+(explicitDefault?'':'<option value="">'+(spec.required?'Choose an option':'Use model default')+'</option>')+spec.choices.map(v=>'<option value="'+esc(v)+'" '+(v===selectedValue?'selected':'')+'>'+esc(choiceLabels[v]||v.replaceAll('_',' '))+'</option>').join('')+'</select>';
  }else if(spec.kind==='boolean'){
    control='<select '+attrs+'><option value="">Use model default</option><option value="true" '+(value==='true'?'selected':'')+'>True</option><option value="false" '+(value==='false'?'selected':'')+'>False</option></select>';
  }else if(unit.includes('table')||spec.kind==='json'){
    control='<textarea '+attrs+' rows="4">'+esc(value)+'</textarea>';
  }else{
    const convertedDefault=unit==='%'&&spec.unit==='fraction'?spec.default*100:spec.default;
    const defaultTitle=spec.default!=null?' title="Model default: '+esc(toText(convertedDefault))+'"':'';
    const placeholder=row.placeholder!=null?' placeholder="'+esc(row.placeholder)+'"':'';
    control='<input '+attrs+' value="'+esc(value)+'"'+defaultTitle+placeholder+' '+(spec.kind==='number'?'inputmode="decimal"':'')+'>';
  }
  const hideUnit=['allocation_method','inventory_basis'].includes(code);
  return '<div class="parameter-field" data-parameter-code="'+esc(code)+'" data-parameter-label="'+esc(label)+'"><span class="parameter-title">'+esc(label)+'</span><div class="parameter-value-row'+(hideUnit?' no-unit':'')+'">'+control+'<input '+(hideUnit?'type="hidden" ':'')+'data-field="unit" aria-label="'+esc(label)+' unit" value="'+esc(unit)+'" title="Unit"></div></div>';
}
function parseTgaRows(value){
  try{
    const rows=toText(value).trim()?JSON.parse(toText(value)):[];
    const allowed=new Set(['name','start_C','end_C','loss_fraction','h2o_share','co2_share','reaction_key']);
    return Array.isArray(rows)&&rows.every(row=>row&&typeof row==='object'&&!Array.isArray(row)&&Object.keys(row).every(key=>allowed.has(key)))?rows:null;
  }catch{return null;}
}
function tgaPercentText(fraction){
  return typeof fraction==='number'&&Number.isFinite(fraction)?String(Number((fraction*100).toPrecision(12))):toText(fraction);
}
function editedTgaRow(original,values){
  const read=value=>value.trim()===''?'':Number(value);
  const row={...original,start_C:read(values.start_C),end_C:read(values.end_C)};
  row.loss_fraction=values.loss_percent===tgaPercentText(original.loss_fraction)?original.loss_fraction:
    values.loss_percent.trim()===''?'':Number(values.loss_percent)/100;
  if(values.reaction_key){
    row.reaction_key=values.reaction_key;
    const selected=schema?.input_libraries?.thermal_reactions?.[values.reaction_key];
    if(selected){row.h2o_share=selected.h2o_share;row.co2_share=selected.co2_share;}
  }else delete row.reaction_key;
  return row;
}
function tgaEditorMarkup(parameter){
  const rows=parseTgaRows(parameter.value);
  if(rows===null)return null; // Keep malformed or future-format JSON editable, never discard it.
  const library=schema?.input_libraries?.thermal_reactions||{};
  const options=selected=>Object.entries(library).map(([key,item])=>{
    const label=item.label+' — '+item.equation+(item.reference_enthalpy_kj_per_kg_reactant!=null?' · ΔHr '+item.reference_enthalpy_kj_per_kg_reactant+' kJ/kg reactant':'');
    return '<option value="'+esc(key)+'" title="'+esc(label)+'" '+(key===selected?'selected':'')+'>'+esc(label)+'</option>';
  }).join('');
  const numeric=(index,field,label,value)=>'<label>'+label+'<input type="number" step="any" data-tga-field="'+field+'" aria-label="Interval '+(index+1)+' '+label+'" value="'+esc(value)+'"></label>';
  return '<div class="parameter-field tga-field" data-parameter-code="tga_intervals_table" data-parameter-label="TGA reaction intervals"><input type="hidden" data-field="value" value="'+esc(JSON.stringify(rows))+'"><input type="hidden" data-field="unit" value="'+esc(parameter.unit||'table/json/text')+'"><div id="tgaReactionEditor"><span class="parameter-title">TGA reactions &amp; mass loss</span>'+rows.map((row,index)=>{
    const selected=library[row.reaction_key];
    const preserved=!row.reaction_key?'<option value="" selected>Keep existing gas assignment</option>':!selected?'<option value="'+esc(row.reaction_key)+'" selected>'+esc(row.reaction_key)+' (loading / unavailable)</option>':'';
    const gas=selected?(selected.h2o_share===1?'H₂O':'CO₂'):'H₂O share: '+toText(row.h2o_share)+' · CO₂ share: '+toText(row.co2_share);
    const reference=selected?.start_C!=null&&selected?.end_C!=null?'Reference '+selected.start_C+'–'+selected.end_C+' °C · ':'';
    const start=row.start_C==null||row.start_C===''?selected?.start_C??'':row.start_C;
    const end=row.end_C==null||row.end_C===''?selected?.end_C??'':row.end_C;
    return '<section class="tga-reaction-row" data-tga-row="'+index+'"><div class="tga-row-heading"><strong>Interval '+(index+1)+'</strong><button type="button" class="text-button" data-remove-tga="'+index+'" aria-label="Remove TGA interval '+(index+1)+'">Remove</button></div><label>Reaction / process<select data-tga-field="reaction_key" aria-label="Interval '+(index+1)+' reaction">'+preserved+options(row.reaction_key)+'</select></label>'+(selected?'<p class="reaction-equation">'+esc(selected.equation)+'</p>':'')+'<div class="tga-numbers">'+numeric(index,'start_C','Start · °C',start)+numeric(index,'end_C','End · °C',end)+numeric(index,'loss_percent','Loss · % of initial dry sample',tgaPercentText(row.loss_fraction))+'</div><p class="tga-gas">'+esc(reference+gas)+'</p><details class="tga-source-note"><summary>Reaction basis</summary><p>'+(selected?esc(selected.note):'Saved gas shares retained; no reaction inferred.')+'</p>'+(selected?.enthalpy_source?'<p>'+esc(selected.enthalpy_source)+'</p>':'')+'</details></section>';
  }).join('')+'<div class="tga-add"><label for="newTgaReaction">Add a common reaction<select id="newTgaReaction" '+(!Object.keys(library).length?'disabled':'')+'><option value="">Choose a reaction…</option>'+options('')+'</select></label><button type="button" class="button" id="addTgaReaction" '+(!Object.keys(library).length?'disabled':'')+'>Add interval</button></div></div></div>';
}
function syncTgaEditor(){
  const editor=qs('#tgaReactionEditor');
  if(!editor)return;
  const hidden=editor.parentElement.querySelector('[data-field="value"]');
  const original=parseTgaRows(hidden.value);
  if(original===null)return;
  const rows=[...editor.querySelectorAll('[data-tga-row]')].map(element=>{
    const values=Object.fromEntries([...element.querySelectorAll('[data-tga-field]')].map(input=>[input.dataset.tgaField,input.type==='checkbox'?input.checked:input.value]));
    return editedTgaRow(original[Number(element.dataset.tgaRow)],values);
  });
  hidden.value=JSON.stringify(rows);
}
function setTgaRows(rows){
  const parameters=state.parameters['Thermal activation']||[];
  const old=parameters.find(row=>row.parameter_code==='tga_intervals_table')||{};
  state.parameters['Thermal activation']=[...parameters.filter(row=>row.parameter_code!=='tga_intervals_table'),{...old,parameter_code:'tga_intervals_table',parameter_label:'TGA reaction intervals',unit:old.unit||'table/json/text',value:JSON.stringify(rows)}];
}
function appendTgaReaction(rows,key){
  const record=schema?.input_libraries?.thermal_reactions?.[key];
  if(!record)return null;
  let count=1,name=key+'_'+count;
  while(rows.some(row=>row.name===name))name=key+'_'+(++count);
  return [...rows,{name,reaction_key:key,start_C:record.start_C??'',end_C:record.end_C??'',loss_fraction:'',h2o_share:record.h2o_share,co2_share:record.co2_share}];
}
function bindTgaEditor(){
  const editor=qs('#tgaReactionEditor');
  if(!editor)return;
  qs('#addTgaReaction').addEventListener('click',()=>{
    const key=qs('#newTgaReaction').value;
    if(!key){notify('Choose a reaction before adding an interval.',true);return;}
    saveForm();
    const rows=parseTgaRows(parameterValue(state.parameters['Thermal activation'],'tga_intervals_table'));
    const updated=rows&&appendTgaReaction(rows,key);
    if(!updated)return;
    setTgaRows(updated);renderForm();changed();
  });
  editor.querySelectorAll('[data-tga-field="reaction_key"]').forEach(select=>select.addEventListener('change',()=>{
    const index=Number(select.closest('[data-tga-row]').dataset.tgaRow);
    const selected=schema?.input_libraries?.thermal_reactions?.[select.value];
    saveForm();
    const rows=parseTgaRows(parameterValue(state.parameters['Thermal activation'],'tga_intervals_table'));
    if(rows&&selected){
      rows[index]={...rows[index],start_C:selected.start_C??'',end_C:selected.end_C??''};
      setTgaRows(rows);
    }
    renderForm();changed();
  }));
  editor.querySelectorAll('[data-remove-tga]').forEach(button=>button.addEventListener('click',()=>{
    saveForm();
    const rows=parseTgaRows(parameterValue(state.parameters['Thermal activation'],'tga_intervals_table'));
    if(rows===null)return;
    setTgaRows(rows.filter((_,index)=>index!==Number(button.dataset.removeTga)));renderForm();changed();
  }));
}
function recoveryMarkup(name,rows,specs){
  if(!['Grinding',...fixedProcessNames].includes(name))return '';
  const labels={coproduct_fraction:'Remaining solids recovered as coproduct',allocation_method:'Burden allocation',inventory_basis:'Inventory basis'};
  return '<details class="advanced"><summary>Other output &amp; allocation</summary>'+recoveryCodes.map(code=>{
    let row=rows.find(p=>p.parameter_code===code)||{parameter_code:code,value:'',unit:code==='coproduct_fraction'?'%':specs[code]?.unit};
    if(code==='coproduct_fraction'&&!toText(row.value).trim()&&specs[code]?.default!=null){
      row={...row,value:specs[code].default,unit:specs[code].unit};
    }
    return fieldMarkup({...row,parameter_label:labels[code]},specs[code]);
  }).join('')+'</details>';
}
function chooseGrindingLibrary(key){
  if(key==='__saved__')return;
  const record=schema?.input_libraries?.grinding?.[key];
  const remove=new Set([...libraryOwnedGrinding,'grinding_library_key']);
  state.parameters.Grinding=(state.parameters.Grinding||[]).filter(p=>!remove.has(p.parameter_code));
  state.parameters.Grinding.push({parameter_code:'grinding_library_key',value:key,unit:''});
  for(const [code,value] of Object.entries(record?.case_inputs||{})){
    state.parameters.Grinding=state.parameters.Grinding.filter(p=>p.parameter_code!==code);
    state.parameters.Grinding.push({parameter_code:code,value:String(value),unit:'um'});
  }
}
function grindingLibraryMarkup(rows){
  const records=schema?.input_libraries?.grinding||{},key=parameterValue(rows,'grinding_library_key');
  const savedCustom=!key&&hasSavedGrinding(rows);
  const choice=key||(savedCustom?'__custom__':'');
  const savedOnly=key&&key!=='__custom__'&&!records[key];
  const select='<label class="library-select" for="grindingLibrary">Background material<select id="grindingLibrary"><option value="" '+(!choice?'selected':'')+'>Choose a material…</option><option value="__custom__" '+(choice==='__custom__'?'selected':'')+'>Custom Wi / Fine K</option>'+(savedOnly?'<option value="'+esc(key)+'" selected>'+esc(key)+' · unavailable</option>':'')+Object.entries(records).map(([id,record])=>'<option value="'+esc(id)+'" '+(id===choice?'selected':'')+'>'+esc(record.label)+'</option>').join('')+'</select></label>';
  let detail='';
  const record=records[key];
  if(record){
    detail='<details class="advanced"><summary>Wi / Fine K defaults</summary><dl class="library-values"><div><dt>Bond work index Wi</dt><dd>'+esc(format(record.Wi_kWh_per_tonne))+' kWh/t</dd></div><div><dt>Fine K</dt><dd>'+(record.fine_K==null?'Not available':esc(format(record.fine_K))+' '+esc(record.fine_K_unit))+'</dd></div><div><dt>Fine regime</dt><dd>Below '+esc(record.transition_um)+' µm · n = '+esc(record.fine_n)+'</dd></div></dl></details>'+(record.fine_K==null?'<p class="input-note">Below '+esc(record.transition_um)+' µm: enter Custom Wi / Fine K.</p>':'');
    if(['Wi_value','fine_K'].some(code=>toText(parameterValue(rows,code)).trim()))detail+='<p class="library-warning">Saved Wi / Fine K overrides active. Reselect a material to reset.</p>';
  }else if(key&&key!=='__custom__'){detail='<p class="library-warning">This saved library entry is unavailable. Choose a listed material before calculating.</p>';}
  return '<section class="library-panel">'+select+detail+'</section>';
}
function grindingCustomMarkup(rows,specs){
  const key=parameterValue(rows,'grinding_library_key');
  if(key!=='__custom__'&&(key||!hasSavedGrinding(rows)))return '';
  return '<section class="grinding-custom" id="grindingCustom"><h3>Custom Wi / Fine K</h3>'+['Wi_value','fine_K'].map(code=>
    fieldMarkup(rows.find(r=>r.parameter_code===code),specs[code])).join('')+'</section>';
}
function thermalFeedMarkup(rows){
  const saved=parameterValue(rows,'feed_composition_table');
  if(!toText(saved).trim())return '';
  let warning='The original recipe is retained unchanged and remains in use.';
  try{
    const recipe=JSON.parse(toText(saved));
    if(!recipe||Array.isArray(recipe)||typeof recipe!=='object'||!Object.keys(recipe).length)throw new Error();
    if(Object.values(recipe).filter(mass=>Number(mass)>0).length>1)warning='Saved multi-material recipe retained. Chain totals still require explicit upstream mapping; it has not been replaced with a single material.';
  }catch{warning='Saved feed data is retained but is not a valid recipe object. It must be corrected before calculation.';}
  return '<details class="advanced"><summary>Saved feed data · read-only</summary><p>'+esc(warning)+'</p><pre>'+esc(toText(saved))+'</pre></details>';
}
const thermalSettingFields = [
  ['settings','ambient_temperature_C','Ambient temperature','Tₐₘᵦ','°C',-273.15],
  ['settings','cp_feed_kj_per_kg_k','Feed heat capacity','cp,feed','kJ/(kg·K)',0],
  ['settings','cp_liquid_water_kj_per_kg_k','Liquid water heat capacity','cp,H₂O(l)','kJ/(kg·K)',0],
  ['settings','free_water_evaporation_cutoff_C','Free-water evaporation cutoff','Tfree,H₂O','°C',-273.15],
  ['settings','latent_heat_h2o_kj_per_kg','Water latent heat','λH₂O','kJ/kg',0],
  ['settings','cp_h2o_steam_kj_per_kg_k','Water vapor heat capacity','cp,H₂O(g)','kJ/(kg·K)',0],
  ['settings','cp_co2_kj_per_kg_k','CO₂ heat capacity','cp,CO₂','kJ/(kg·K)',0],
  ['settings','thermal_factory_unit_per_kg_product_h','Plant use coefficient','cplant','unit/(kg dry product·h)',0],
  ['scenario','lambda_heatup','Heat-up loss factor','λheatup','× Qmin',1],
  ['scenario','hold_loss_kj_per_kg_h_per_deltaT100K','Holding heat-loss coefficient','qhold','kJ/(kg product·h·100 K)',0]
];
function thermalSettingsMarkup(rows){
  const defaults=schema?.input_libraries?.thermal_defaults;
  if(!defaults)return '<details class="advanced"><summary>Additional settings</summary><p>Loading defaults…</p></details>';
  const sections=[['settings','Heat & plant use'],['scenario','Practical heat']];
  return '<details class="advanced thermal-settings"><summary>Additional settings</summary><div id="thermalSettingsEditor">'+sections.map(([group,title])=>{
    const raw=toText(parameterValue(rows,group)).trim();
    let overrides={};
    try{overrides=raw?JSON.parse(raw):{};}catch{overrides=null;}
    if(!overrides||typeof overrides!=='object'||Array.isArray(overrides)){
      const existing=rows.find(row=>row.parameter_code===group)||{parameter_code:group,parameter_label:title,value:raw,unit:'table/json/text'};
      return '<p class="library-warning">Saved '+esc(group)+' data needs correction before using the controls below.</p>'+fieldMarkup(existing,{kind:'json',unit:'table/json/text'});
    }
    const fields=thermalSettingFields.filter(field=>field[0]===group);
    return '<section class="thermal-settings-group" data-parameter-code="'+group+'" data-parameter-label="'+esc(title)+'"><h3>'+esc(title)+'</h3><input type="hidden" data-field="value" value="'+esc(JSON.stringify(overrides))+'"><input type="hidden" data-field="unit" value="table/json/text"><div class="carbon-settings-grid">'+fields.map(([,key,label,,unit,minimum])=>{
      const baseline=defaults[group][key];
      const value=Object.prototype.hasOwnProperty.call(overrides,key)?overrides[key]:baseline;
      return '<label class="carbon-setting"><span><strong>'+esc(label)+' · '+esc(unit)+'</strong></span><input type="number" step="any" min="'+minimum+'" data-thermal-setting="'+key+'" data-thermal-default="'+esc(baseline)+'" aria-label="'+esc(label+' '+unit)+'" value="'+esc(value)+'"></label>';
    }).join('')+'</div></section>';
  }).join('')+'</div></details>';
}
function syncThermalSettingsEditor(){
  if(state.current!=='Thermal activation')return;
  qs('#thermalSettingsEditor')?.querySelectorAll('[data-parameter-code]').forEach(group=>{
    const hidden=group.querySelector('[data-field="value"]');
    if(!hidden)return;
    const overrides=JSON.parse(hidden.value);
    group.querySelectorAll('[data-thermal-setting]').forEach(input=>{
      const value=input.value.trim(), key=input.dataset.thermalSetting;
      if(!value||Number(value)===Number(input.dataset.thermalDefault))delete overrides[key];
      else overrides[key]=Number(value);
    });
    hidden.value=JSON.stringify(overrides);
  });
}
function defaultCarbonationConditions(){
  return {water_mode:'dry',water_powder_ratio:0,heat_up:false,target_temperature_C:'',pressurize:false,target_pressure_bar:'',gas_mode:'none',gas_flow_L_h:'',separation:false,drying:false};
}
function useConditionInputs(){
  const rows=state.parameters.Carbonation||[];
  if(rows.some(row=>toText(row.value).trim()))return;
  state.parameters.Carbonation=[...rows.filter(row=>!['carbonation_model','condition_inputs'].includes(row.parameter_code)),
    {parameter_code:'carbonation_model',value:schema?.ui_default_carbonation_variant||'general_operating_v2',unit:''},
    {parameter_code:'condition_inputs',value:JSON.stringify(defaultCarbonationConditions()),unit:'table/json/text'}];
}
function parseCarbonationConditions(value){
  try{const config=JSON.parse(toText(value));return config&&typeof config==='object'&&!Array.isArray(config)?config:null;}catch{return null;}
}
function editedCarbonationConditions(original,values){
  const result={...original,...values};
  if(Object.hasOwn(values,'gas_definition')){
    const definitions={
      none:['none','per_reactor'],
      flow_lab:['flow','lab_batch'],
      chamber:['chamber','per_reactor']
    };
    if(Object.hasOwn(definitions,values.gas_definition)){
      [result.gas_mode,result.gas_flow_basis]=definitions[values.gas_definition];
    }
    delete result.gas_definition;
  }
  // Only a transition into wet mode applies defaults. Manual unchecking persists.
  if(original.water_mode!=='wet'&&result.water_mode==='wet'){
    result.separation=true;result.drying=true;
  }
  if(result.water_mode==='dry'){result.water_powder_ratio=0;result.separation=false;result.drying=false;}
  else if(result.water_mode==='semi_dry')result.separation=false;
  if(result.water_mode==='wet')delete result.batch_loading_volume_basis;
  else result.batch_loading_volume_basis='total_reactor';
  return result;
}
function syncCarbonationEditor(){
  const editor=qs('#carbonationEditor');
  if(!editor||state.current!=='Carbonation')return;
  const hidden=editor.querySelector('[data-field="value"]');
  const original=parseCarbonationConditions(hidden.value);
  if(!original)return;
  const values={};
  editor.querySelectorAll('[data-carbon-field]').forEach(input=>{
    if(input.disabled)return;
    const key=input.dataset.carbonField;
    values[key]=input.type==='checkbox'?input.checked:input.type==='number'?(input.value.trim()===''?'':Number(input.value)):input.value;
  });
  const config=editedCarbonationConditions(original,values);
  const overrides={...(original.background_overrides||{})};
  editor.querySelectorAll('[data-background-field]').forEach(input=>{
    const key=input.dataset.backgroundField;
    const value=input.value.trim();
    // An explicitly saved case input stays explicit even if it equals today's
    // editable default; this protects snapshots when defaults change again.
    if(value===''||(Number(value)===Number(input.dataset.backgroundDefault)
        && !Object.hasOwn(original.background_overrides||{},key)))delete overrides[key];
    else overrides[key]=Number(value);
  });
  // The wet fill fraction and dry solids loading belong to different routes.
  // A hidden value from a previous route must not change the current one.
  if(config.water_mode==='wet')delete overrides.chamber_loading_kg_per_m3;
  else delete overrides.reactor_fill_fraction;
  // In chamber mode the displayed chamber volume is the reactor volume used
  // for both batch loading and chamber-control demand.
  if(config.gas_mode==='chamber'&&config.chamber_volume_m3!==''&&config.chamber_volume_m3!=null)
    overrides.reactor_volume_m3=Number(config.chamber_volume_m3);
  const reaction=editor.querySelector('[data-reaction-selection]');
  if(reaction){
    const choice=reaction.value;
    if(choice==='custom'){
      delete overrides.reaction_phase;
      const custom=editor.querySelector('[data-reaction-heat]')?.value.trim()||'';
      overrides.reaction_heat_kj_per_mol_co2=custom===''?0:Number(custom);
    }else if(choice==='none'){
      delete overrides.reaction_phase;
      delete overrides.reaction_heat_kj_per_mol_co2;
    }else{
      overrides.reaction_phase=choice;
      delete overrides.reaction_heat_kj_per_mol_co2;
    }
    if(choice==='none')delete overrides.reaction_heat_utilization_factor;
    else overrides.reaction_heat_utilization_factor=1;
  }
  config.background_overrides=overrides;
  // A select emits input before change. Mirror transition defaults immediately,
  // otherwise the second save reads stale semi-dry checkboxes and cancels drying.
  if(original.water_mode!==config.water_mode){
    editor.querySelectorAll('[data-carbon-field]').forEach(input=>{
      if(['separation','drying'].includes(input.dataset.carbonField))input.checked=config[input.dataset.carbonField];
      if(input.dataset.carbonField==='water_powder_ratio'&&config.water_mode==='dry')input.value='0';
    });
  }
  hidden.value=JSON.stringify(config);
}
function carbonationEditorMarkup(rows){
  let config=parseCarbonationConditions(parameterValue(rows,'condition_inputs'));
  if(!config)return '<p class="library-warning">Saved condition data needs correction; the original JSON is retained.</p>'+fieldMarkup(rows.find(row=>row.parameter_code==='condition_inputs'),{kind:'json'});
  if(config.gas_mode==='flow'&&config.gas_flow_basis!=='lab_batch')return '<p class="library-warning">This gas-flow definition is incompatible with the current model. Enter a new laboratory-flow input.</p>';
  const background=schema?.input_libraries?.carbonation_defaults;
  const c={...defaultCarbonationConditions(),gas_flow_basis:'per_reactor',...config};
  const wet=c.water_mode==='wet', water=['semi_dry','wet'].includes(c.water_mode);
  c.gas_definition=c.gas_mode==='flow'?'flow_lab':c.gas_mode;
  const separated=wet&&(config.separation??true), dried=water&&(config.drying??wet);
  const check=(key,label,checked,disabled=false)=>'<label class="carbon-check"><input type="checkbox" data-carbon-field="'+key+'" '+(checked?'checked ':'')+(disabled?'disabled ':'')+'><span>'+label+'</span></label>';
  const number=(key,label,unit,value,disabled=false)=>'<label class="carbon-number">'+esc(label)+' · '+esc(unit)+'<input type="number" step="any" data-carbon-field="'+key+'" aria-label="'+esc(label+' '+unit)+'" value="'+esc(value)+'" '+(disabled?'disabled':'')+'></label>';
  const select=(key,label,options)=>'<label class="carbon-select">'+label+'<select data-carbon-field="'+key+'">'+(c[key]===''?'<option value="" selected>Choose '+(key==='water_mode'?'water use':'a definition')+'…</option>':'')+options.map(([value,text])=>'<option value="'+value+'" '+(value===c[key]?'selected':'')+'>'+text+'</option>').join('')+'</select></label>';
  const baseBackground=Object.fromEntries(Object.entries(background?.parameters||{}).map(([key,spec])=>[key,spec.default]));
  const effectiveBackground={...baseBackground,...(config.background_overrides||{})};
  const backgroundNumber=(key,label,unit)=>{
    const spec=background?.parameters?.[key]||{};
    const minimum=spec.minimum==null?'':' min="'+esc(spec.exclusive_minimum&&spec.minimum===0?0.000001:spec.minimum)+'"';
    const maximum=spec.maximum==null?'':' max="'+esc(spec.maximum)+'"';
    return '<label class="carbon-number">'+esc(label)+' · '+esc(unit)+'<input type="number" step="any"'+minimum+maximum+' data-background-field="'+key+'" data-background-default="'+esc(baseBackground[key])+'" aria-label="'+esc(label+' '+unit)+'" value="'+esc(effectiveBackground[key])+'"></label>';
  };
  const heatLibrary=background?.reaction_heat_library||{};
  const customHeatSelected=Object.hasOwn(config.background_overrides||{},'reaction_heat_kj_per_mol_co2')
    || Number(effectiveBackground.reaction_heat_kj_per_mol_co2)>0;
  const reactionChoice=customHeatSelected?'custom':effectiveBackground.reaction_phase||'none';
  const reactionOptions=[['none','No reaction selected'],...Object.entries(heatLibrary).map(([key,entry])=>[key,entry.reaction||key]),['custom','Custom reaction heat']];
  const reactionMarkup=
    '<label class="carbon-select">Main carbonation reaction<select data-reaction-selection aria-label="Main carbonation reaction">'+reactionOptions.map(([key,label])=>'<option value="'+esc(key)+'" '+(reactionChoice===key?'selected':'')+'>'+esc(label)+'</option>').join('')+'</select></label>'+
    (reactionChoice==='custom'?'<label class="carbon-number">Custom reaction heat · kJ/mol CO₂ retained<input type="number" step="any" min="0.000001" required data-reaction-heat aria-label="Custom reaction heat kJ per mol CO2" value="'+esc(effectiveBackground.reaction_heat_kj_per_mol_co2||'')+'"></label>':'');
  const backgroundSettings=[
    ['reactor_volume_m3','Nominal reactor volume','Vreactor','m³'],
    ['reactor_fill_fraction','Wet slurry fill fraction','φfill','fraction'],
    ['initial_cake_moisture','Cake moisture before drying','wᵢ,cake','kg water/kg wet cake'],
    ['water_recycle_ratio','Filtrate recycle fraction','Rw','fraction'],
    ['final_product_moisture','Final product moisture after P6','wf,product','kg water/kg wet product'],
    ['co2_loss_fraction','External CO₂ loss fraction','λCO₂,loss','fraction'],
    ['chamber_loading_kg_per_m3','Dry-chamber solids loading','qdry','kg dry feed/m³'],
    ['eta_heating','Heating efficiency','ηheat','fraction'],
    ['hold_loss_kj_per_kg_h_per_deltaT100K','Holding-loss coefficient','hhold','kJ/(kg·h·100 K)'],
    ['compressor_efficiency','Compressor efficiency','ηcomp','fraction'],
    ['carbonation_factory_unit_per_kg_product_h','Plant use coefficient','cplant','unit/(kg dry product·h)'],
    ['drying_delta_t_K','Drying temperature rise','ΔTdry','K']
  ];
  const settingsMarkup=background?'<div class="carbon-settings-grid">'+backgroundSettings.filter(([key])=>
    !(c.gas_mode==='chamber'&&key==='reactor_volume_m3')
    && (key!=='reactor_fill_fraction'||wet)
    && (key!=='chamber_loading_kg_per_m3'||!wet)
    && (wet||!['initial_cake_moisture','water_recycle_ratio'].includes(key))).map(([key,label,,unit])=>{
    const spec=background.parameters[key], minimum=spec.minimum==null?'':' min="'+esc(spec.minimum)+'"', maximum=spec.maximum==null?'':' max="'+esc(spec.maximum)+'"';
    return '<label class="carbon-setting"><span><strong>'+esc(label)+' · '+esc(unit)+'</strong></span><input type="number" step="any"'+minimum+maximum+' data-background-field="'+key+'" data-background-default="'+esc(baseBackground[key])+'" aria-label="'+esc(label+' '+unit)+'" value="'+esc(effectiveBackground[key])+'"></label>';
  }).join('')+'</div>':'<p>Loading defaults…</p>';
  const gasDefinitions=[['none','Not included'],['flow_lab','Flow-through · laboratory flow'],['chamber','Chamber control']];
  const gasInput=c.gas_definition==='flow_lab'?number('gas_flow_L_h','Laboratory gas flow','L/h',c.gas_flow_L_h)
    :c.gas_definition==='chamber'?number('chamber_volume_m3','Chamber volume','m³',c.chamber_volume_m3??effectiveBackground.reactor_volume_m3??10)+number('chamber_co2_concentration_vol_pct','CO₂ concentration','vol%',c.chamber_co2_concentration_vol_pct):'';
  const specs=specsFor('Carbonation');
  const basics=['co2_uptake_kg','t_reaction_h'].map(code=>fieldMarkup(rows.find(row=>row.parameter_code===code),specs[code])).join('');
  return basics+
    '<div id="carbonationEditor" class="carbon-editor" data-parameter-code="condition_inputs" data-parameter-label="Operating conditions"><input type="hidden" data-field="value" value="'+esc(JSON.stringify(config))+'"><input type="hidden" data-field="unit" value="table/json/text">'+
    '<section class="carbon-section"><h3>Material</h3>'+backgroundNumber('solid_density_kg_per_m3','Solid density','kg/m³')+reactionMarkup+'</section>'+
    '<section class="carbon-section"><h3>Experimental batch</h3>'+number('gas_lab_feed_kg','Laboratory dry feed mass','kg',c.gas_lab_feed_kg)+'</section>'+
    '<section class="carbon-section"><h3>1 · Water</h3>'+select('water_mode','Water use',[['dry','No water · dry'],['semi_dry','Humidified / semi-dry'],['wet','Wet slurry']])+(water?number('water_powder_ratio','W/P ratio','kg water / kg dry feed',c.water_powder_ratio):'')+'</section>'+
    '<section class="carbon-section"><h3>2 · Temperature</h3>'+backgroundNumber('t0_C','Initial reactor temperature','°C')+check('heat_up','Heat up',c.heat_up)+(c.heat_up?number('target_temperature_C','Target temperature','°C',c.target_temperature_C):'')+'</section>'+
    '<section class="carbon-section"><h3>3 · Pressure</h3>'+check('pressurize','Pressurize',c.pressurize)+(c.pressurize?number('target_pressure_bar','Target pressure','bar absolute',c.target_pressure_bar):'')+'</section>'+
    '<section class="carbon-section"><h3>4 · Gas handling and batch loading</h3>'+select('gas_definition','Definition',gasDefinitions)+gasInput+'</section>'+
    '<section class="carbon-section"><h3>5 · Post-treatment</h3>'+check('separation','Solid–liquid separation',separated,!wet)+check('drying','Drying',dried,!water)+(water&&!separated&&dried?'<p class="library-warning">Without separation, drying removes water from the whole wet feed.</p>':'')+'</section>'+
    '<details class="advanced carbon-settings"><summary>Additional settings</summary>'+settingsMarkup+'</details></div>';
}
function bindCarbonationEditor(){
  qs('#carbonationEditor')?.addEventListener('change',event=>{
    const input=event.target;
    if(input.type==='checkbox'||input.tagName==='SELECT'){
      saveForm();renderForm();changed();
    }
  });
}
function renderForm(){
  const name=state.current;ensureProcess(name);
  qs('#paramTitle').textContent=name;qs('#paramStatus').textContent=state.selected.includes(name)?'Included':'Not included';qs('#paramStatus').classList.toggle('excluded',!state.selected.includes(name));
  const form=qs('#paramForm');
  if(!state.selected.includes(name)){form.innerHTML='<div class="inactive-note">Process excluded.</div>';return;}
  if(['Carbonation','Thermal activation'].includes(name)&&!schema){form.innerHTML='<p class="input-note">Loading process settings…</p>';return;}
  const specs=specsFor(name), rows=state.parameters[name], baseCodes=new Set(templates[name].map(x=>x[1]));
  if(name==='Carbonation'&&parameterValue(rows,'carbonation_model')!=='general_operating_v2'){
    form.innerHTML='<p class="library-warning">This Carbonation model is incompatible with the current framework. Start a new project.</p>';return;
  }
  const conditions=name==='Carbonation';
  if(conditions){
    form.innerHTML=carbonationEditorMarkup(rows)+'<div class="parameter-footer"><button class="button" id="saveLocalInputs">Keep these inputs</button></div>';
    qs('#saveLocalInputs').addEventListener('click',()=>{saveForm();persistDraft();notify('Carbonation inputs kept in your draft.');});
    bindCarbonationEditor();return;
  }
  const basic=templates[name].filter(([,code])=>name!=='Grinding'||!['Wi_value','fine_K'].includes(code)).map(([,code])=>rows.find(p=>p.parameter_code===code));
  const hiddenCodes=new Set([...(name==='Grinding'?['grinding_library_key',...[...libraryOwnedGrinding].filter(code=>!['Wi_value','fine_K'].includes(code))]:name==='Thermal activation'?['tga_basis','feed_composition_table','settings','scenario']:[]),...recoveryCodes]);
  const fixed=fixedProcessNames.includes(name);
  const extra=fixed?[]:rows.filter(p=>!baseCodes.has(p.parameter_code)&&!hiddenCodes.has(p.parameter_code));
  const present=new Set(rows.map(p=>p.parameter_code));
  Object.entries(specs).forEach(([code,spec])=>{
    if(!fixed&&!hiddenCodes.has(code)&&!present.has(code)&&code!=='carbonation_model')extra.push({parameter_code:code,parameter_label:code.replaceAll('_',' '),value:'',unit:spec.unit});
  });
  const required=extra.filter(row=>specs[row.parameter_code]?.required);
  const optional=extra.filter(row=>!specs[row.parameter_code]?.required);
  const hasInputBasisEquipment=toText(parameterValue(rows,'grinding_machine_kg_per_kg_processed')).trim()!=='';
  const grindingOptionalLabels={auxiliaries_factor:'Energy correction factor',
    grinding_machine_kg_per_kg_product:'Grinding equipment · per kg dry product',
    grinding_machine_kg_per_kg_processed:'Grinding equipment · per kg processed feed'};
  const visibleOptional=name==='Grinding'?optional.filter(row=>['auxiliaries_factor','grinding_machine_kg_per_kg_product'].includes(row.parameter_code)
      ||(row.parameter_code==='grinding_machine_kg_per_kg_processed'&&hasInputBasisEquipment)):
    name==='Thermal activation'?[]:optional;
  form.innerHTML=(name==='Grinding'?grindingLibraryMarkup(rows):'')+
    (name==='Grinding'?grindingCustomMarkup(rows,specs):'')+
    (name==='Thermal activation'?thermalFeedMarkup(rows):'')+
    basic.map(row=>{
      const record=name==='Grinding'?schema?.input_libraries?.grinding?.[parameterValue(rows,'grinding_library_key')]:null;
      const spec={...specs[row.parameter_code]};
      if(record&&['Wi_value','fine_K'].includes(row.parameter_code))spec.default=record[row.parameter_code==='Wi_value'?'Wi_kWh_per_tonne':'fine_K'];
      return fieldMarkup(row,spec);
    }).join('')+
    recoveryMarkup(name,rows,specs)+
    required.map(row=>fieldMarkup(row,specs[row.parameter_code])).join('')+
    (name==='Thermal activation'?thermalSettingsMarkup(rows):'')+
    (visibleOptional.length?'<details class="advanced"><summary>Additional settings</summary>'+visibleOptional.map(row=>fieldMarkup(name==='Grinding'?{...row,parameter_label:grindingOptionalLabels[row.parameter_code],
      placeholder:row.parameter_code==='grinding_machine_kg_per_kg_product'&&hasInputBasisEquipment?'':specs[row.parameter_code]?.default}:row,specs[row.parameter_code])).join('')+'</details>':'')+
    (schema&&!schema.processes?.[name]?'<p class="input-note">You can save these inputs. Calculation for this process is not yet connected.</p>':'')+
    '<div class="parameter-footer"><button class="button" id="saveLocalInputs">Keep these inputs</button></div>';
  qs('#saveLocalInputs').addEventListener('click',()=>{saveForm();persistDraft();notify(name+' inputs kept in your draft. Save project to add them to your library.');});
  qs('#grindingLibrary')?.addEventListener('change',()=>{saveForm();chooseGrindingLibrary(qs('#grindingLibrary').value);renderForm();changed();});
  bindTgaEditor();
}
async function fetchJSON(url,options){
  const response=await fetch(url,options);let result;
  try{result=await response.json();}catch{throw new Error('The server did not return a readable response.');}
  if(!response.ok&&!result.errors)throw new Error(result.error||'Request failed.');
  return {response,result};
}
function showView(view){
  saveForm();const views={builder:'Build your SCM pathway',results:'Your SCM climate footprint',projects:'Your project library'};
  if(!views[view])return;
  ['builder','results','projects'].forEach(name=>qs('#'+name+'View').hidden=name!==view);
  qsa('.main-nav [data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
  qs('#pageTitle').textContent=views[view];
  if(view==='projects')loadProjects();if(view==='results')renderResults();
  window.scrollTo({top:0,behavior:'instant'});
}
function assertCurrentCarbonation(rows){
  if(parameterValue(rows,'carbonation_model')!=='general_operating_v2')
    throw new Error('This saved Carbonation model is incompatible. Start a new project.');
  const config=parseCarbonationConditions(parameterValue(rows,'condition_inputs'));
  if(!config || (config.gas_mode==='flow'&&config.gas_flow_basis!=='lab_batch')
    || config.batch_loading_volume_basis==='active_slurry')
    throw new Error('This saved Carbonation input uses an incompatible batch or gas definition. Start a new project.');
}
function assertCurrentTga(rows){
  const basis=toText(parameterValue(rows,'tga_basis')).trim();
  if(basis&&basis!=='total_intervals')
    throw new Error('This saved TGA input uses separate gas channels. Enter nonoverlapping total-loss intervals in a new project.');
  const raw=toText(parameterValue(rows,'tga_intervals_table')).trim();
  if(!raw)return;
  let intervals;
  try{intervals=JSON.parse(raw);}catch{return;}
  if(Array.isArray(intervals)&&intervals.some(row=>row&&typeof row==='object'&&Object.hasOwn(row,'include_reaction_heat')))
    throw new Error('This saved TGA table uses an obsolete reaction-heat switch. Start a new project and enter current reaction intervals.');
}
function assertCurrentPayload(payload,keepAll){
  const burden=payload.material?.feedstock_burden_rule;
  if(burden!=null&&burden!==''&&burden!==feedstockBurdenRule)
    throw new Error('This saved route specifies unsupported upstream feedstock burdens. Create a new route using the waste cut-off boundary.');
  if(!ScmLca.isCurrentSettings(payload?.lca_settings))
    throw new Error('This saved route uses an incompatible model and cannot be opened. Start a new project.');
  if(Number(payload.lca_settings.transport?.waste_to_process?.moisture_percent || 0)>0)
    throw new Error('This saved route uses an incompatible transport moisture input. Start a new project.');
  for(const process of payload.processes||[]){
    if(!processOrder.includes(process.process_name))
      throw new Error('This saved route contains an unavailable process. Start a new project.');
    if(process.process_name==='Carbonation')assertCurrentCarbonation(process.parameters||[]);
    if(process.process_name==='Thermal activation')assertCurrentTga(process.parameters||[]);
  }
  if(keepAll?.Carbonation && !(payload.processes||[]).some(process=>process.process_name==='Carbonation')
    && keepAll.Carbonation.some(row=>toText(row.value).trim()))
    assertCurrentCarbonation(keepAll.Carbonation);
  if(keepAll?.['Thermal activation'])assertCurrentTga(keepAll['Thermal activation']);
}
function applyPayload(payload,{keepAll=null,current=null}={}){
  assertCurrentPayload(payload,keepAll);
  clearTimeout(draftTimer);
  qs('#pathwayName').value=payload.pathway_name||'Untitled SCM project';
  qs('#materialName').value=payload.material?.material_name||'';qs('#locationName').value=payload.material?.location||payload.location||'';
  qs('#materialNote').value=payload.material?.note||'';
  qs('#functionalUnit').value=payload.functional_unit_kg||1;
  // Material type is retained only as saved metadata; it has no calculation branch.
  state.materialType=payload.material?.material_type==='Others'?'Others':'Waste';
  state.projectId=Number.isInteger(payload.project_id)?payload.project_id:null;
  state.referenceProduct=payload.reference_product||'SCM product';
  state.systemBoundary=payload.system_boundary||'A1-A3';
  state.lcaSettings={...payload.lca_settings};
  state.selected=[];state.parameters=keepAll||{};
  for(const p of [...(payload.processes||[])].sort((a,b)=>a.process_order-b.process_order)){
    state.selected.push(p.process_name);
    const loaded=(p.parameters||[]).map(row=>({...row,value:toText(row.value)}));
    const codes=new Set(loaded.map(row=>row.parameter_code));
    state.parameters[p.process_name]=[...(state.parameters[p.process_name]||[]).filter(row=>!codes.has(row.parameter_code)),...loaded];
    if(p.process_name==='Grinding'&&parameterValue(loaded,'grinding_library_key')){
      // Inactive custom Wi/K fields must not become active overrides.
      state.parameters.Grinding=state.parameters.Grinding.filter(row=>!['Wi_value','fine_K'].includes(row.parameter_code)||codes.has(row.parameter_code));
    }
    ensureProcess(p.process_name);
  }
  if(typeof ScmLca!=='undefined')ScmLca.setSettings(state.lcaSettings);
  state.current=current&&processOrder.includes(current)?current:state.selected[0]||'Grinding';
  state.revision++;lastCalculation=null;qs('#resultCount').textContent='—';qs('#downloadResult').disabled=true;
  renderGrid();renderForm();renderCounts();renderFlow();
}
async function submitProject(){
  if(!ScmLca.isCurrentSettings(state.lcaSettings)){notify('Energy settings are unavailable. Reload the page to restore the current model.',true);return;}
  const payload=collectPayload();const button=qs('#submitProject');button.disabled=true;
  try{
    const {response,result}=await fetchJSON('/api/v1/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(!response.ok)throw new Error(result.error||'Project could not be saved.');
    state.projectId=result.id;persistDraft();
    notify('Project #'+result.id+' saved. Your input set is available in Saved projects.');
  }catch(error){notify(error.message,true);}finally{button.disabled=false;}
}
async function calculateProject(){
  if(!ScmLca.isCurrentSettings(state.lcaSettings)){notify('Energy settings are unavailable. Reload the page to restore the current model.',true);return;}
  if(calculating)return;
  const payload=collectPayload();
  const carbonation=state.selected.includes('Carbonation')
    ? parseCarbonationConditions(parameterValue(state.parameters.Carbonation||[],'condition_inputs')) : null;
  const customHeat=carbonation?.background_overrides?.reaction_heat_kj_per_mol_co2;
  if(carbonation&&Object.hasOwn(carbonation.background_overrides||{},'reaction_heat_kj_per_mol_co2')
      &&(!Number.isFinite(Number(customHeat))||Number(customHeat)<=0)){
    showView('builder');
    if(state.current!=='Carbonation'){state.current='Carbonation';renderGrid();renderForm();}
    qs('#carbonationEditor [data-reaction-heat]')?.focus();
    notify('Enter a positive custom reaction heat in kJ/mol CO₂ before calculating.',true);
    return;
  }
  const revision=state.revision;calculating=true;qs('#calculateProject').disabled=true;qs('#calculateProject').textContent='Calculating…';
  try{
    if(!Number.isFinite(payload.functional_unit_kg)||payload.functional_unit_kg<=0)throw new Error('Enter a final dry-product mass greater than zero.');
    const {result}=await fetchJSON('/api/v1/lca/calculate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    lastCalculation={request:payload,response:result,calculated_at:new Date().toISOString()};lastCalculationRevision=revision;
    qs('#resultCount').textContent=result.ok?'1':'!';
    showView('results');
  }catch(error){lastCalculation={request:payload,response:{ok:false,errors:[error.message]},calculated_at:new Date().toISOString()};lastCalculationRevision=revision;qs('#resultCount').textContent='!';showView('results');}
  finally{calculating=false;qs('#calculateProject').disabled=false;qs('#calculateProject').innerHTML=icon('play')+'Calculate LCA';}
}
const format = number => typeof number==='number'&&Number.isFinite(number)?new Intl.NumberFormat('en',{maximumSignificantDigits:6}).format(number):'—';
function renderResults(){
  if(!lastCalculation){
    qs('#downloadResult').disabled=true;
    qs('#calculationResults').innerHTML='<div class="card empty-state">'+icon('chart')+'<h2>No result yet</h2><button class="button" data-view="builder">Back to pathway</button></div>';
    return;
  }
  const result=lastCalculation.response,stale=lastCalculationRevision!==state.revision;
  qs('#downloadResult').disabled=stale||!result.ok;
  const host=qs('#calculationResults');
  let html=stale?'<div class="result-warning">These results belong to earlier inputs. Calculate again to update them.</div>':'';
  if(!result.ok){
    html+='<div class="result-warning"><strong>Calculation could not be completed</strong><ul>'+(result.errors||[]).map(e=>'<li>'+esc(e)+'</li>').join('')+'</ul><button class="button" data-view="builder">Review inputs</button></div>';
    if((result.errors||[]).some(e=>e.includes('Carbonation')))html+='<p><button class="button" data-review-process="Carbonation">Review Carbonation model →</button></p>';
  }else{
    if(result.lca)html+=renderLcaResults(result);
    else html+='<div class="result-warning">No characterized LCA result is available. Recalculate with the background database available.</div>';
  }
  host.innerHTML=html;
}
async function loadProjects(){
  const host=qs('#savedProjects');host.innerHTML='<div class="card empty-state"><p>Loading saved projects…</p></div>';
  try{
    const {result}=await fetchJSON('/api/v1/projects');
    if(!Array.isArray(result))throw new Error('Project list could not be read.');
    host.innerHTML=result.length?result.map(project=>'<article class="card project-card"><div><h2>'+esc(project.pathway_name)+' · #'+esc(project.id)+'</h2></div><button class="button" data-open-project="'+project.id+'">Open project '+icon('external')+'</button></article>').join(''):'<div class="card empty-state">'+icon('folder')+'<h2>No saved projects yet</h2><button class="button" data-view="builder">Build a pathway</button></div>';
  }catch(error){host.innerHTML='<div class="result-warning">'+esc(error.message)+'</div>';}
}
async function openProject(id){
  try{const {result}=await fetchJSON('/api/v1/projects/'+id);applyPayload({...result.pathway,project_id:Number(id),material:{...result.material,location:result.pathway.location},processes:result.processes});showView('builder');persistDraft();notify('Saved project #'+id+' loaded with its inputs. Save project creates a new library entry, leaving the original unchanged.');}
  catch(error){notify(error.message,true);}
}
function downloadResult(){
  if(!lastCalculation||lastCalculationRevision!==state.revision||!lastCalculation.response.ok)return;
  const blob=new Blob([JSON.stringify(lastCalculation,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='scm-lca-result.json';a.hidden=true;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
}
function openExport(){
  if(!lastCalculation||lastCalculationRevision!==state.revision||!lastCalculation.response.ok)return;
  qs('#exportJson').value=JSON.stringify(lastCalculation,null,2);qs('#exportDialog').showModal();
}
document.addEventListener('click',event=>{
  const review=event.target.closest('[data-review-process]');if(review&&state.selected.includes(review.dataset.reviewProcess)){saveForm();state.current=review.dataset.reviewProcess;showView('builder');renderForm();}
  const view=event.target.closest('[data-view]');if(view)showView(view.dataset.view);
  const project=event.target.closest('[data-open-project]');if(project)openProject(project.dataset.openProject);
});
qs('#paramForm').addEventListener('input',changed);
qs('#paramForm').addEventListener('change',changed);
['#pathwayName','#materialName','#locationName','#materialNote','#functionalUnit'].forEach(s=>qs(s).addEventListener('input',changed));
qs('#submitProject').addEventListener('click',submitProject);
qs('#calculateProject').addEventListener('click',calculateProject);
qs('#refreshProjects').addEventListener('click',loadProjects);
qs('#downloadResult').addEventListener('click',openExport);
qs('#downloadExport').addEventListener('click',downloadResult);
qs('#closeExport').addEventListener('click',()=>qs('#exportDialog').close());
qs('#selectExport').addEventListener('click',()=>{qs('#exportJson').focus();qs('#exportJson').select();});
async function initialize(){
  hydrateIcons();ensureProcess('Grinding');renderGrid();renderForm();renderCounts();renderFlow();
  if(typeof ScmLca!=='undefined')ScmLca.setSettings(state.lcaSettings);
  try{
    const draft=JSON.parse(localStorage.getItem(storageKey)||'null');
    if(draft?.payload&&Array.isArray(draft.payload.processes)){
      applyPayload(draft.payload,{keepAll:draft.allParameters,current:draft.current});
    }
  }catch(error){notify(error.message||'The previous browser draft could not be restored. Saved projects are still available.',true);}
  if(typeof ScmLca!=='undefined')void ScmLca.init(changed);
  try{const {result}=await fetchJSON('/api/v1/calculation-schema');saveForm();schema=result;
    state.selected.forEach(ensureProcess);renderForm();persistDraft();
  }
  catch{notify('Calculation settings are unavailable. Your saved inputs are retained; reload to restore the operating controls.',true);}
  const historyProject=new URLSearchParams(location.search).get('project');
  if(historyProject && /^[1-9]\d*$/.test(historyProject)) await openProject(historyProject);
}
initialize();
