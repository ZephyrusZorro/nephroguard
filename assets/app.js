'use strict';

const $ = id => document.getElementById(id);
function el(tag, text = '', className = '') {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
}

const state = { cases: [], formulary: [], active: null, view: 'review', busy: false };
const statusLabels = {
  CONTRAINDICATED: 'Contraindication flag',
  DOSE_REDUCTION_REQUIRED: 'Adjustment flag',
  MONITOR_CLOSELY: 'Monitoring flag',
  OPTIMAL: 'No dosing flag',
};

async function api(path, payload) {
  const options = payload === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  };
  const response = await fetch('/api/' + path, options);
  if (!response.headers.get('content-type')?.includes('application/json')) {
    throw new Error('The local server returned an unexpected response.');
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The local request failed.');
  return result;
}

function message(id, text, isError = false) {
  const node = $(id);
  node.textContent = text;
  node.hidden = !text;
  node.classList.toggle('error', isError);
}

function source(parent, item) {
  try {
    const url = new URL(item.source_url);
    if (url.protocol !== 'https:') return;
    const link = el('a', item.source_title || 'Engine reference');
    link.href = url.href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    parent.append(link);
  } catch {
    // Some bundled entries have no valid reference link.
  }
}

function show(view, focus = false) {
  state.view = view;
  for (const button of document.querySelectorAll('[data-view]')) {
    const active = button.dataset.view === view;
    button.setAttribute('aria-pressed', active);
    $(button.dataset.view).hidden = !active;
  }
  if (view === 'handoff') {
    renderHandoff();
    void loadHandoffs();
  } else if (view === 'formulary') renderFormulary();
  if (focus) {
    const heading = $(view + '-title');
    heading.tabIndex = -1;
    heading.focus();
  }
}

function renderCases() {
  const query = $('case-search').value.trim().toLowerCase();
  const filtered = state.cases.filter(({ patient_record: p }) =>
    [p.name, p.room, p.primary_diagnosis].some(value => String(value).toLowerCase().includes(query)));
  $('case-count').textContent = filtered.length + ' / ' + state.cases.length;
  const list = $('case-list');
  list.replaceChildren();
  for (const item of filtered) {
    const { patient_record: p, evaluation } = item;
    const button = el('button', '', 'case-button');
    button.setAttribute('aria-current', String(state.active === item));
    const flags = evaluation?.drug_evaluations.filter(d => d.status !== 'OPTIMAL').length;
    button.append(el('strong', p.name),
      el('small', (p.room || 'Training ward') + ' · ' + (flags === undefined ? 'Review inputs' : flags + (flags === 1 ? ' medication flag' : ' medication flags'))));
    button.addEventListener('click', () => {
      state.active = item;
      for (const other of list.querySelectorAll('button')) other.setAttribute('aria-current', String(other === button));
      renderCase();
      if (matchMedia('(max-width: 760px)').matches) $('case-title').focus();
    });
    list.append(button);
  }
  if (!filtered.length) list.append(el('p', query ? 'No cases match this search.' : 'No saved cases. Create a training case to start.', 'empty'));
}

function metric(label, value, unit) {
  const node = el('div', '', 'metric');
  node.append(el('small', label), el('strong', value ?? '—'), el('span', value == null ? '' : ' ' + unit));
  return node;
}

function renderCase() {
  const item = state.active;
  $('empty-case').hidden = !!item;
  $('case-detail').hidden = !item;
  if (!item) return;
  const { patient_record: p, evaluation: result } = item;
  $('case-title').textContent = p.name || 'Unnamed training case';
  $('case-meta').textContent = (item.draft ? 'UNSAVED PREVIEW' : 'SAVED CASE') + ' / ' + (p.room || 'TRAINING WARD');
  $('case-diagnosis').textContent = p.primary_diagnosis || 'Training scenario';
  $('case-handoff').disabled = !result;
  message('case-error', item.error || '', true);
  const metrics = $('metrics');
  const out = $('case-results');
  metrics.replaceChildren();
  out.replaceChildren();
  metrics.hidden = !result;
  if (!result) return;

  const k = result.kinetics;
  metrics.append(metric('Cockcroft–Gault CrCl', k.crcl_selected, 'mL/min'),
    metric('CKD-EPI eGFR · indexed', k.egfr_indexed, 'mL/min/1.73 m²'),
    metric('Engine dosing clearance', k.effective_dosing_crcl, 'mL/min'));
  const basis = el('details', '', 'basis');
  basis.append(el('summary', 'Inputs and calculation basis'),
    el('p', [k.age + ' years', k.sex, k.weight_kg + ' kg', k.height_cm + ' cm',
      'Creatinine ' + k.scr_mg_dl + ' mg/dL', 'Potassium ' + k.potassium_meq_l + ' mEq/L',
      'RRT ' + k.rrt_modality.toUpperCase()].join(' · ')),
    el('p', 'Engine-selected weight ' + k.selected_weight_kg + ' kg (' + k.selected_weight_basis + '). ' + k.weight_rationale),
    el('p', k.aki_stage + ' · Engine kidney function category ' + k.kdigo_stage));
  if (k.egfr_cr_cys_indexed != null) basis.append(el('p', 'Combined creatinine–cystatin C eGFR ' + k.egfr_cr_cys_indexed + ' mL/min/1.73 m²'));
  out.append(basis);

  if (result.syndromes.length) {
    out.append(el('h3', 'Combined medication flags'));
    for (const item of result.syndromes) {
      const alert = el('div', '', 'alert');
      alert.append(el('strong', item.title), el('p', 'Engine flag · ' + item.severity), el('p', item.mechanism));
      source(alert, item);
      out.append(alert);
    }
  }
  out.append(el('h3', 'Medication review · ' + result.drug_evaluations.length));
  if (!result.drug_evaluations.length) out.append(el('p', 'This case has no medications.', 'empty'));
  const medications = [...result.drug_evaluations].sort((a, b) => b.severity_score - a.severity_score);
  for (const med of medications) {
    const details = el('details', '', 'med-row');
    const summary = el('summary', med.name);
    summary.append(el('span', statusLabels[med.status] || med.status, 'badge status' + (med.status === 'OPTIMAL' ? '' : ' flagged')));
    details.append(summary, el('p', 'Entered regimen · ' + (med.current_dose || 'Unspecified')),
      el('p', 'Engine suggestion · ' + med.recommended_regimen),
      el('p', med.clinical_rationale));
    source(details, med);
    out.append(details);
  }
}

function renderFormulary() {
  const term = $('drug-search').value.trim().toLowerCase();
  const rows = state.formulary.filter(drug => (drug.name + ' ' + drug.category).toLowerCase().includes(term));
  $('drug-count').textContent = rows.length + (rows.length === 1 ? ' entry' : ' entries');
  const list = $('drug-list');
  list.replaceChildren();
  for (const drug of rows) {
    const row = el('div', '', 'reference-row');
    row.append(el('h3', drug.name), el('p', drug.category + ' · ' + drug.index_metric));
    source(row, drug);
    list.append(row);
  }
  if (!rows.length) list.append(el('p', 'No medications match this search.', 'empty'));
}

function renderHandoff() {
  const item = state.active;
  const result = item?.evaluation;
  $('handoff-content').hidden = !result;
  $('handoff-subtitle').textContent = result ? (item.patient_record.name || 'Training case') + (item.draft ? ' · Unsaved preview' : ' · Training example') : 'Select an evaluated case in the review desk.';
  $('log-handoff').disabled = !!item?.draft || state.busy;
  message('log-status', item?.draft ? 'Save the training case to log a draft.' : '');
  if (!result) return;
  const target = $('ipass-content');
  target.replaceChildren();
  const handoff = result.ipass;
  for (const [heading, content] of [
    ['I · Illness severity', handoff.illness_severity],
    ['P · Case summary', handoff.patient_summary],
    ['A · Action list', handoff.action_list],
    ['S · Situation and contingency', handoff.contingency_planning],
    ['S · Synthesis by receiver', handoff.synthesis_by_receiver],
  ]) {
    target.append(el('h3', heading));
    if (Array.isArray(content)) {
      const list = el('ul');
      for (const entry of content) list.append(el('li', entry));
      target.append(list);
    } else target.append(el('p', content));
  }
  $('handout-text').textContent = result.patient_handout[$('language').value];
}

async function loadHandoffs() {
  const list = $('handoff-log');
  list.replaceChildren(el('p', 'Loading drafts…', 'empty'));
  try {
    const { handoff_logs: rows } = await api('handoffs');
    list.replaceChildren();
    for (const row of rows) {
      const entry = el('div', '', 'reference-row');
      entry.append(el('strong', row.patient_name),
        el('p', new Date(row.created_at * 1000).toLocaleString() + ' · ' + row.signed_by));
      list.append(entry);
    }
    if (!rows.length) list.append(el('p', 'No drafts have been logged.', 'empty'));
  } catch (error) {
    list.replaceChildren(el('p', error.message, 'empty'));
  }
}

function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = el('a');
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const fieldSpecs = [
  ['name', 'Case label', 'text'], ['room', 'Ward label', 'text'], ['primary_diagnosis', 'Scenario', 'text'],
  ['age', 'Age (years)', 'number'], ['sex', 'Sex used by equation', [['Female','Female'],['Male','Male']]],
  ['weight_kg', 'Weight (kg)', 'number'], ['height_cm', 'Height (cm)', 'number'],
  ['scr_value', 'Creatinine', 'number'], ['scr_unit', 'Creatinine unit', [['mg_dl','mg/dL'],['umol_l','µmol/L']]],
  ['baseline_scr_mg_dl', 'Baseline creatinine (mg/dL)', 'optional'],
  ['delta_hours', 'Time since baseline (hours)', 'number'],
  ['cystatin_c_mg_l', 'Cystatin C (mg/L)', 'optional'], ['potassium_meq_l', 'Potassium (mEq/L)', 'number'],
  ['weight_override', 'Weight basis', [['auto','Automatic'],['ABW','Actual'],['IBW','Ideal'],['AdjBW','Adjusted']]],
  ['rrt_modality', 'Renal replacement therapy', [['none','None'],['ihd','Intermittent hemodialysis'],['pd','Peritoneal dialysis'],['crrt','Continuous RRT']]],
  ['crrt_effluent_ml_kg_h', 'CRRT effluent (mL/kg/h)', 'number'],
];

let editingId;
function addMedication(med = {}) {
  const line = el('div', '', 'med-fields');
  const drug = el('select');
  drug.name = 'drug_id';
  drug.required = true;
  for (const [key, name] of [['','Choose a medication'], ...state.formulary.map(d => [d.id, d.name])]) {
    drug.add(new Option(name, key));
  }
  drug.value = med.drug_id || '';
  const dose = el('input');
  dose.name = 'current_dose';
  dose.maxLength = 300;
  dose.value = med.current_dose || '';
  dose.placeholder = 'Dose and frequency';
  const drugLabel = el('label', 'Medication');
  const doseLabel = el('label', 'Entered regimen');
  drugLabel.append(drug);
  doseLabel.append(dose);
  const remove = el('button', 'Remove', 'quiet');
  remove.type = 'button';
  remove.setAttribute('aria-label', 'Remove medication row');
  remove.addEventListener('click', () => { line.remove(); $('add-med').focus(); });
  line.append(drugLabel, doseLabel, remove);
  $('med-fields').append(line);
  return drug;
}

function edit(item) {
  const p = item?.patient_record ?? {
    name: 'New training case', sex: 'Female', scr_unit: 'mg_dl', weight_override: 'auto',
    rrt_modality: 'none', delta_hours: 24, potassium_meq_l: 4.2, crrt_effluent_ml_kg_h: 25,
  };
  editingId = p.id;
  $('editor-title').textContent = item ? 'Edit training inputs' : 'New training case';
  message('form-error', '');
  $('fields').replaceChildren();
  $('med-fields').replaceChildren();
  for (const [key, label, type] of fieldSpecs) {
    const field = el('label', label);
    const input = el(Array.isArray(type) ? 'select' : 'input');
    input.name = key;
    if (input instanceof HTMLSelectElement) {
      for (const [value, title] of type) input.add(new Option(title, value));
      const current = String(p[key] ?? '');
      const alias = { f: 'Female', m: 'Male', 'mg/dl': 'mg_dl', 'umol/l': 'umol_l' }[current.toLowerCase()];
      const option = [...input.options].find(option => option.value.toLowerCase() === current.toLowerCase());
      input.value = alias ?? option?.value ?? '';
      input.required = true;
    } else {
      input.type = type === 'text' ? 'text' : 'number';
      input.value = p[key] ?? '';
      input.required = type === 'number' || key === 'name';
      if (input.type === 'number') input.step = 'any';
      else input.maxLength = 300;
    }
    field.append(input);
    $('fields').append(field);
  }
  for (const medication of p.medications || []) addMedication(medication);
  $('editor').showModal();
}

$('case-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (state.busy) return;
  const save = event.submitter?.value !== 'preview';
  const data = new FormData(event.currentTarget);
  const payload = { medications: [] };
  if (editingId) payload.id = editingId;
  for (const [key, , type] of fieldSpecs) {
    const value = data.get(key);
    payload[key] = type === 'number' || type === 'optional' ? (value === '' ? null : Number(value)) : value;
  }
  for (const line of $('med-fields').children) {
    payload.medications.push({ drug_id: line.querySelector('select').value, current_dose: line.querySelector('input').value });
  }
  const buttons = [...$('case-form').querySelectorAll('button[type=submit]'), $('close-editor')];
  state.busy = true;
  buttons.forEach(button => { button.disabled = true; });
  message('form-error', '');
  try {
    if (save) {
      const saved = await api('patients', payload);
      state.cases = state.cases.filter(item => item.patient_record.id !== saved.patient_record.id);
      state.cases.push(saved);
      state.cases.sort((a, b) => a.patient_record.name.localeCompare(b.patient_record.name));
      state.active = saved;
      $('case-search').value = '';
    } else {
      const evaluation = await api('evaluate', payload);
      state.active = { patient_record: payload, evaluation, draft: true };
    }
    $('editor').close();
    renderCases();
    renderCase();
    $('case-title').focus();
  } catch (error) {
    message('form-error', error.message, true);
  } finally {
    state.busy = false;
    buttons.forEach(button => { button.disabled = false; });
  }
});

async function load() {
  $('retry').hidden = true;
  message('notice', 'Loading workspace…');
  try {
    const [cases, formulary] = await Promise.all([api('patients'), api('formulary')]);
    state.cases = cases.patients;
    state.formulary = formulary.formulary.sort((a, b) => a.name.localeCompare(b.name));
    state.active = state.cases[0] ?? null;
    $('new-case').disabled = false;
    message('notice', '');
    renderCases();
    renderCase();
    if (state.view === 'formulary') renderFormulary();
    if (state.view === 'handoff') renderHandoff();
  } catch (error) {
    message('notice', error.message, true);
    $('retry').hidden = false;
  }
}

for (const button of document.querySelectorAll('[data-view]')) button.addEventListener('click', () => show(button.dataset.view));
$('case-search').addEventListener('input', renderCases);
$('drug-search').addEventListener('input', renderFormulary);
$('new-case').addEventListener('click', () => edit());
$('edit-case').addEventListener('click', () => edit(state.active));
$('add-med').addEventListener('click', () => addMedication().focus());
$('close-editor').addEventListener('click', () => $('editor').close());
$('editor').addEventListener('cancel', event => { if (state.busy) event.preventDefault(); });
$('case-handoff').addEventListener('click', () => show('handoff', true));
$('back-review').addEventListener('click', () => show('review', true));
$('language').addEventListener('change', () => {
  $('handout-text').textContent = state.active?.evaluation?.patient_handout[$('language').value] || '';
});
$('download-handoff').addEventListener('click', () => {
  const value = state.active?.evaluation?.ipass.markdown;
  if (value) download('nephroguard-training-handoff.md', 'TRAINING EXAMPLE — Requires independent review.\n\n' + value, 'text/markdown');
});
$('download-fhir').addEventListener('click', () => {
  const value = state.active?.evaluation?.fhir_bundle;
  if (value) download('nephroguard-training-fhir-sample.json', JSON.stringify(value, null, 2), 'application/json');
});
$('log-handoff').addEventListener('click', async () => {
  const item = state.active;
  if (!item || item.draft || state.busy) return;
  $('log-handoff').disabled = true;
  state.busy = true;
  message('log-status', 'Logging draft…');
  try {
    await api('handoffs', { ...item.patient_record, signed_by: 'Training workspace' });
    message('log-status', 'Training draft logged.');
    await loadHandoffs();
  } catch (error) {
    message('log-status', error.message, true);
  } finally {
    state.busy = false;
    $('log-handoff').disabled = !!state.active?.draft;
  }
});
$('retry').addEventListener('click', load);
void load();
