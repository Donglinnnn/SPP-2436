/* Background selections belong to the pathway, not to individual process forms. */
const ScmLca = (() => {
  const $ = id => document.getElementById(id);
  const keys = ['waste_to_process'];
  const pairedEnergyVersion = 'paired-energy-2026-10-v2';
  const inputDefaultsVersion = 'carbonation-route-specific-fill-2026-10-v5';
  let catalogue = null, settings = {}, onChange = () => {}, started = false, carbonationSelected = false;
  const clone = value => JSON.parse(JSON.stringify(value));
  const option = (text, value) => new Option(text, value);
  function sourceLabel(r) { return `${r.name} · ${r.location}`; }
  const hasIndependentEnergySettings = value => ['electricity_code','heat_code','electricity_source','heat_source','heat_market']
    .some(key => Object.hasOwn(value || {}, key));
  const isCurrentSettings = value => value?.energy_scenario_version === pairedEnergyVersion
    && value?.input_defaults_version === inputDefaultsVersion
    && ['E0','E1','E2'].includes(value?.electricity_scenario || 'E0')
    && ['C0','C1','C2'].includes(value?.co2_source || 'C0')
    && !Object.hasOwn(value, 'co2_supply_factor')
    && !Object.hasOwn(value?.transport || {}, 'scm_to_mix')
    && !hasIndependentEnergySettings(value);
  function fillSources() {
    if (!catalogue) return;
    const scenarios = catalogue.energy_scenarios || catalogue.electricity_scenarios || [];
    const selected = scenarios.some(r => r.code === settings.electricity_scenario)
      ? settings.electricity_scenario : 'E0';
    const shortLabels = {
      E0: 'E0 · Grid electricity + natural-gas heat',
      E1: 'E1 · Lignite electricity + non-natural-gas heat',
      E2: 'E2 · Renewable electricity + future heat'
    };
    $('electricitySource').replaceChildren(...scenarios.map(r => option(shortLabels[r.code] || r.label, r.code)));
    $('electricitySource').value = selected;
    $('electricitySource').disabled = false;
    keys.forEach(key => {
      const field = $(key + 'Source');
      const transportCode = settings.transport?.[key]?.activity_code ?? catalogue.defaults.transport_code;
      field.replaceChildren(...catalogue.transport.map(r => option(sourceLabel(r), r.code)));
      if (!catalogue.transport.some(r => r.code === transportCode)) field.prepend(option('Saved freight unavailable — choose again', transportCode));
      field.value = transportCode; field.disabled = false;
    });
  }
  function render() {
    $('lcaCo2SourceField').hidden = !carbonationSelected;
    $('lcaCo2Source').value = settings.co2_source || 'C0';
    keys.forEach(key => {
      const leg = settings.transport?.[key] || {};
      $(key + 'Enabled').checked = leg.enabled === true;
      $(key + 'Fields').hidden = !leg.enabled;
      $(key + 'Distance').value = leg.distance_km ?? '';
      document.querySelector(`[data-transport="${key}"]`).classList.toggle('included', !!leg.enabled);
    });
    fillSources();
    if (catalogue) $('lcaCatalogueStatus').hidden = true;
  }
  function setSettings(value) {
    if (!isCurrentSettings(value)) throw new Error('This saved route uses an incompatible model. Start a new project.');
    settings = clone(value || {});
    if (started) render();
  }
  function setCarbonationSelected(selected) {
    carbonationSelected = !!selected;
    render();
  }
  function getSettings() {
    const value = clone(settings);
    delete value.model_version;
    if (!value.electricity_scenario) value.electricity_scenario = 'E0';
    if (carbonationSelected) {
      if (!value.co2_source) value.co2_source = 'C0';
    } else {
      delete value.co2_source;
    }
    return value;
  }
  function readInputs() {
    settings.transport ||= {};
    keys.forEach(key => {
      const previous = settings.transport[key] || {};
      settings.transport[key] = {enabled: $(key + 'Enabled').checked,
        distance_km: $(key + 'Distance').value, moisture_percent: 0,
        activity_code: $(key + 'Source').value || previous.activity_code || catalogue?.defaults.transport_code};
    });
  }
  async function init(callback) {
    onChange = callback; started = true; render();
    $('electricitySource').addEventListener('change', () => {
      const choice = $('electricitySource').value;
      settings.electricity_scenario = choice;
      render(); onChange();
    });
    $('lcaCo2Source').addEventListener('change', () => {
      settings.co2_source = $('lcaCo2Source').value;
      onChange();
    });
    keys.forEach(key => {
      $(key + 'Enabled').addEventListener('change', () => { readInputs(); render(); onChange(); });
      $(key + 'Distance').addEventListener('input', () => { readInputs(); onChange(); });
      $(key + 'Source').addEventListener('change', () => { readInputs(); onChange(); });
    });
    try {
      const response = await fetch('/api/v1/lca-schema'); const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Background catalogue unavailable');
      catalogue = data; render();
    } catch (error) {
      $('lcaCatalogueStatus').hidden = false;
      $('lcaCatalogueStatus').textContent = error.message + ' No placeholder impact factors will be used.';
    }
  }
  return {init, setSettings, setCarbonationSelected, getSettings,
          isCurrentSettings, hasIndependentEnergySettings, pairedEnergyVersion, inputDefaultsVersion};
})();
