/* Uses the builder's input contract; never trusts a stale displayed calculation. */
(() => {
  const dialog = document.querySelector('#scmItemDialog');
  let pending = false;
  document.querySelector('#saveScmItem').addEventListener('click', () => {
    document.querySelector('#scmItemName').value = document.querySelector('#pathwayName').value || document.querySelector('#materialName').value;
    document.querySelector('#scmItemMessage').textContent = '';
    document.querySelector('#openScmRecipe').hidden = true;
    dialog.showModal();
  });
  document.querySelector('#closeScmItem').addEventListener('click', () => dialog.close());
  document.querySelector('#scmItemForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (pending) return;
    const button = document.querySelector('#confirmScmItem');
    const message = document.querySelector('#scmItemMessage');
    const payload = {name: document.querySelector('#scmItemName').value, density_kg_m3: document.querySelector('#scmItemDensity').value,
      pathway: collectPayload()};
    pending = true; button.disabled = true; message.textContent = 'Characterizing and saving the 1 kg snapshot…';
    try {
      const response = await fetch('/api/v1/scm-items', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      const item = await response.json();
      if (!response.ok) throw new Error(item.error || 'Material item could not be created');
      message.textContent = `Saved: ${item.name} · ${item.gwp_kg_co2e_kg.toPrecision(5)} kg CO₂e/kg SCM (conditional route GWP).`;
      const link = document.querySelector('#openScmRecipe');
      link.href = '/recipes?scm=' + encodeURIComponent(item.id); link.hidden = false;
      notify('A new SCM material snapshot was saved. It is ready for a recipe.');
    } catch (error) { message.textContent = error.message; }
    finally { pending = false; button.disabled = false; }
  });
})();
