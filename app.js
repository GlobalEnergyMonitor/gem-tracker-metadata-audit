/* ── State ───────────────────────────────────────────────── */
let summary = [];
let currentData = null;
let expandedField = null;
let crossTrackerData = null;
let referenceSets = {};  // loaded from reference_sets.json
let currentView = 'welcome'; // 'welcome' | 'table' | 'cross-tracker'
let ctActiveTab = 'categories'; // 'categories' | 'exact' | 'fuzzy'

// Overrides: merged from overrides.json (committed) + localStorage (local edits)
const LS_OVERRIDES_KEY = 'gem_overrides_v1';
let committedOverrides = {};  // loaded from overrides.json
let localOverrides = {};      // loaded from localStorage, merged on top
let hasUnsavedOverrides = false;

/* Tab slugs that are metadata/lookup tables, not real data */
const SKIP_TAB_SLUGS = new Set([
  'introduction_terminology', 'column_dictionary', 'regions_area_and_countries',
  'about_ggit_lng',
]);
const SKIP_TRACKER_SLUGS = new Set(['sqlite_sequence', '']);
const SKIP_TAB_PREFIX = 'about_';

/* ── Boot ────────────────────────────────────────────────── */
async function init() {
  try {
    const res = await fetch('./analysis/summary.json');
    if (!res.ok) throw new Error(res.statusText);
    summary = await res.json();
  } catch {
    document.getElementById('content').innerHTML = `
      <div class="state-msg state-error">
        Could not load <code>analysis/summary.json</code>.
        Run <code>python3 analyze.py</code> first, then serve from the project root:
        <code>python3 -m http.server 8080</code>
      </div>`;
    return;
  }

  // Load committed overrides.json (non-fatal)
  fetch('./overrides.json')
    .then(r => r.ok ? r.json() : {})
    .then(data => { committedOverrides = data || {}; })
    .catch(() => {});

  // Load local overrides from localStorage
  try {
    const stored = localStorage.getItem(LS_OVERRIDES_KEY);
    if (stored) localOverrides = JSON.parse(stored);
  } catch {}

  // Warn before closing if there are unsaved local overrides
  window.addEventListener('beforeunload', e => {
    if (hasUnsavedOverrides) {
      e.preventDefault();
    }
  });

  // Load reference sets in background (non-fatal if missing)
  fetch('./reference_sets.json')
    .then(r => r.ok ? r.json() : {})
    .then(data => { referenceSets = data || {}; })
    .catch(() => {});

  // Load cross-tracker data in background (non-fatal if missing)
  fetch('./analysis/cross_tracker.json')
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      crossTrackerData = data;
      renderSidebar();
      if (currentView === 'welcome') renderWelcome();
    })
    .catch(() => {});

  renderSidebar();
  renderWelcome();
}

/* ── Overrides helpers ───────────────────────────────────── */
function mergedOverrides() {
  const merged = JSON.parse(JSON.stringify(committedOverrides));
  for (const [table, fields] of Object.entries(localOverrides)) {
    if (!merged[table]) merged[table] = {};
    for (const [field, suppressions] of Object.entries(fields)) {
      merged[table][field] = suppressions;
    }
  }
  return merged;
}

function getFieldOverrides(tableName, fieldName) {
  const m = mergedOverrides();
  return (m[tableName]?.[fieldName] || []);
}

function isFlagSuppressed(tableName, fieldName, flagKey) {
  return getFieldOverrides(tableName, fieldName).some(o => o.flag === flagKey);
}

function toggleFlagSuppression(tableName, fieldName, flagKey, reason) {
  if (!localOverrides[tableName]) localOverrides[tableName] = {};
  const existing = localOverrides[tableName][fieldName] || [];
  const idx = existing.findIndex(o => o.flag === flagKey);
  const suppressing = idx < 0;
  if (idx >= 0) {
    existing.splice(idx, 1);
  } else {
    existing.push({ flag: flagKey, reason: reason || '' });
  }
  localOverrides[tableName][fieldName] = existing;
  try { localStorage.setItem(LS_OVERRIDES_KEY, JSON.stringify(localOverrides)); } catch {}
  hasUnsavedOverrides = Object.values(localOverrides).some(
    fields => Object.values(fields).some(arr => arr.length > 0)
  );

  // Update in-memory currentData so re-render reflects the change immediately
  if (currentData && currentData.table_name === tableName) {
    const fieldObj = currentData.fields.find(f => f.field_name === fieldName);
    if (fieldObj) {
      if (suppressing) {
        const flagStr = fieldObj.flags.find(f => f.split(':')[0] === flagKey);
        if (flagStr) {
          fieldObj.flags = fieldObj.flags.filter(f => f !== flagStr);
          fieldObj.suppressed_flags = [...(fieldObj.suppressed_flags || []), { flag: flagKey, reason: reason || '' }];
        }
      } else {
        fieldObj.suppressed_flags = (fieldObj.suppressed_flags || []).filter(s => s.flag !== flagKey);
        // Re-add to active flags (key only; full detail restored on next analyze.py run)
        if (!fieldObj.flags.some(f => f.split(':')[0] === flagKey)) {
          fieldObj.flags = [...fieldObj.flags, flagKey];
        }
      }
    }
  }
}

function downloadOverrides() {
  const merged = mergedOverrides();
  const blob = new Blob([JSON.stringify(merged, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'overrides.json';
  a.click();
  hasUnsavedOverrides = false;
}

/* ── Sidebar ─────────────────────────────────────────────── */

/* Flag groups — each group shares a color and collapses to one badge in the sidebar */
const FLAG_GROUPS = [
  { color: '#fc8181', label: 'error',   keys: ['out_of_set_categorical', 'categorical_rare_values', 'numeric_outliers'] },
  { color: '#f6ad55', label: 'warning', keys: ['mostly_numeric_with_outliers', 'wrong_multi_value_separator', 'year_out_of_range', 'non_standard_null_proxies', 'numeric_null_proxies'] },
  { color: '#d6bcfa', label: 'info',    keys: ['boolean_encoding', 'multi_value_separator_check'] },
];

/* Flat map for color lookup in the home page flag table */
const FLAG_COLOR = {};
FLAG_GROUPS.forEach(g => g.keys.forEach(k => { FLAG_COLOR[k] = g.color; }));

function sidebarFlagBadges(flagsByType) {
  if (!flagsByType) return '';
  return FLAG_GROUPS
    .map(({ color, keys }) => {
      const total = keys.reduce((s, k) => s + (flagsByType[k] || 0), 0);
      return total > 0
        ? `<span class="sb-flag" style="color:${color}" title="${keys.filter(k => flagsByType[k]).map(k => `${k}: ${flagsByType[k]}`).join(', ')}">${total}</span>`
        : '';
    })
    .join('');
}

function aggregateFlags(tabs) {
  const out = {};
  for (const tab of tabs)
    for (const [k, v] of Object.entries(tab.flags_by_type || {}))
      out[k] = (out[k] || 0) + v;
  return out;
}

function renderSidebar() {
  const flaggedOnly = document.getElementById('sidebar-flagged-only').checked;

  /* Group tabs by tracker, filtering out non-data items */
  const groups = new Map();
  for (const item of summary) {
    if (SKIP_TRACKER_SLUGS.has(item.tracker_slug)) continue;
    if (SKIP_TAB_SLUGS.has(item.tab_slug)) continue;
    if (item.tab_slug.startsWith(SKIP_TAB_PREFIX)) continue;
    if (flaggedOnly && item.n_flagged === 0) continue;
    if (!groups.has(item.tracker_slug)) groups.set(item.tracker_slug, []);
    groups.get(item.tracker_slug).push(item);
  }

  const container = document.getElementById('tracker-list');
  const ctCount = crossTrackerData
    ? `${crossTrackerData.stats.n_exact_groups} groups`
    : '…';
  container.innerHTML = `
    <div class="ct-nav-item ${currentView === 'cross-tracker' ? 'active' : ''}" id="ct-nav-btn">
      <span class="ct-nav-label">Cross-tracker analysis</span>
      <span class="ct-nav-meta">${ctCount}</span>
    </div>
    <div class="ct-nav-divider"></div>
  `;

  for (const [tracker, tabs] of groups) {
    const trackerFlags = aggregateFlags(tabs);
    const group = document.createElement('div');
    group.className = 'tracker-group';

    const isInDb = tabs.some(t => t.in_research_db);
    const dbBadge = isInDb
      ? `<span class="sb-db-badge" title="Data managed in GEM research database">DB</span>`
      : '';
    group.innerHTML = `
      <div class="tracker-label">
        ${escHtml(formatTrackerName(tracker))}${dbBadge}
        <span class="sb-flag-row">${sidebarFlagBadges(trackerFlags)}</span>
      </div>
      <div>
        ${tabs.map(tab => `
          <div class="tab-item" data-table="${escAttr(tab.table_name)}">
            <span class="tab-name">${escHtml(formatTabName(tab.tab_slug))}</span>
            <span class="tab-meta">${tab.n_rows.toLocaleString()} rows</span>
            <span class="sb-flag-row">${sidebarFlagBadges(tab.flags_by_type)}</span>
          </div>
        `).join('')}
      </div>
    `;
    container.appendChild(group);
  }

  container.querySelectorAll('.tab-item').forEach(el => {
    el.addEventListener('click', () => loadTable(el.dataset.table, el));
  });
  document.getElementById('ct-nav-btn')?.addEventListener('click', showCrossTracker);
}

/* ── Welcome screen ──────────────────────────────────────── */
function showWelcome() {
  currentView = 'welcome';
  document.querySelectorAll('.tab-item').forEach(e => e.classList.remove('active'));
  document.getElementById('toolbar').hidden = true;
  renderSidebar();
  renderWelcome();
}

function renderWelcome() {
  const validItems = summary.filter(
    s => !SKIP_TRACKER_SLUGS.has(s.tracker_slug) &&
         !SKIP_TAB_SLUGS.has(s.tab_slug) &&
         !s.tab_slug.startsWith(SKIP_TAB_PREFIX)
  );
  const totalFields  = validItems.reduce((s, t) => s + t.n_fields, 0);
  const totalFlagged = validItems.reduce((s, t) => s + t.n_flagged, 0);
  const allTrackers  = [...new Set(validItems.map(i => i.tracker_slug))].sort();

  // Aggregate flag counts by type across all tables
  const flagTotals = {};
  validItems.forEach(t => {
    Object.entries(t.flags_by_type || {}).forEach(([flag, count]) => {
      flagTotals[flag] = (flagTotals[flag] || 0) + count;
    });
  });
  const FLAG_META = {
    boolean_encoding:            { label: 'Boolean encoding varies',        tip: 'Field has ≤4 unique values matching multiple boolean encodings (yes/no, True/False, Y/N, 1/0). Values are inconsistent across trackers.' },
    year_out_of_range:           { label: 'Year values out of range',        tip: 'A field guessed as a year contains values outside 1900–2100, or non-numeric values mixed with years.' },
    categorical_rare_values:     { label: 'Categorical rare values',         tip: 'A categorical field has values that appear in fewer than 2% of non-null rows — possible typos, variant spellings, or one-off entries.' },
    out_of_set_categorical:      { label: 'Values outside reference set',    tip: 'A field with a known allowed-value set (country names, status values) contains values not in that set.' },
    wrong_multi_value_separator: { label: 'Wrong multi-value separator',     tip: 'A multi-value field uses comma (,) as its separator, which conflicts with CSV export. Org standard is & or ;.' },
    multi_value_separator_check: { label: 'Multi-value separator in use',    tip: 'Informational: field contains & or ; as a separator. Confirms multi-value encoding is present; check that the separator choice is consistent with STD-02.' },
    non_standard_null_proxies:   { label: 'Non-standard null proxies',       tip: 'A numeric or boolean field contains shorthand null proxies (*, -, UA, --) instead of empty cells. These block numeric aggregation.' },
    numeric_outliers:            { label: 'Numeric field with outliers',     tip: 'A field that is mostly numeric has a small number of non-numeric, non-null-proxy values — likely data entry errors or stray text.' },
    mostly_numeric_with_outliers:{ label: 'Mostly numeric with outliers',    tip: 'Field is >50% numeric but below the threshold to be classified as numeric. May be a numeric field with significant non-numeric contamination.' },
  };
  const flagRows = Object.entries(flagTotals)
    .sort((a, b) => b[1] - a[1])
    .map(([flag, count]) => {
      const color = FLAG_COLOR[flag] || 'var(--dim)';
      const { label, tip } = FLAG_META[flag] || { label: flag, tip: '' };
      return `<tr>
        <td><span class="flag-dot" style="background:${color}"></span><span title="${escAttr(tip)}">${escHtml(label)}</span></td>
        <td class="flag-count" style="color:${color}"><strong>${count}</strong></td>
      </tr>`;
    })
    .join('');

  // Category summary table (requires crossTrackerData)
  const cats = crossTrackerData?.categories ?? {};
  const CAT_ORDER = ['IDs','Names','Status','Capacity','Location','Temporal','Entities'];

  const IOP_DOCS = {
    'IDs':      'docs/iop-01-ids',
    'Names':    'docs/iop-02-names',
    'Status':   'docs/iop-03-status',
    'Capacity': 'docs/iop-04-capacity',
    'Location': 'docs/iop-05-location',
    'Temporal': 'docs/iop-06-temporal',
  };

  const catRows = CAT_ORDER.filter(c => cats[c]).map(catName => {
    const cat = cats[catName];
    const coverage = cat.n_trackers_with_field;
    const total = allTrackers.length;
    const jac = cat.value_jaccard;
    const jacStr = jac != null
      ? `<span class="welcome-jaccard" style="background:${jaccardColor(jac)}">${jac.toFixed(2)}</span>`
      : '<span style="color:var(--dim)">—</span>';
    const coveragePct = total > 0 ? Math.round(coverage / total * 100) : 0;
    const covBar = `<div class="welcome-cov-bar"><div style="width:${coveragePct}%;background:var(--accent)"></div></div>`;
    const docLink = IOP_DOCS[catName]
      ? `<a class="welcome-cat-doc" href="${escAttr(IOP_DOCS[catName])}" target="_blank">doc ↗</a>`
      : '';
    return `
      <tr class="welcome-cat-row" data-cat="${escAttr(catName)}">
        <td><strong>${escHtml(catName)}</strong> ${docLink}<div class="welcome-cat-desc">${escHtml(cat.description)}</div></td>
        <td>${coverage}/${total} ${covBar}</td>
        <td>${cat.n_exact_groups}</td>
        <td>${jacStr}</td>
      </tr>
    `;
  }).join('');

  // Tracker dot matrix — commented out pending richer compliance data
  // const activeCats = CAT_ORDER.filter(c => cats[c]);
  // const trackerRows = allTrackers.map(slug => { ... }).join('');

  const catSection = catRows ? `
    <div class="welcome-section">
      <h3>Interoperability by category</h3>
      <table class="welcome-cat-table">
        <thead><tr><th>Category</th><th>Tracker coverage</th><th>Field variants</th><th>Value overlap</th></tr></thead>
        <tbody>${catRows}</tbody>
      </table>
      <p class="welcome-hint">Click <a href="#" id="welcome-ct-link">Cross-tracker analysis</a> for full detail.</p>
    </div>
  ` : `<p style="color:var(--dim)">Run <code>python3 cross_tracker.py</code> to see category compatibility.</p>`;

  document.getElementById('content').innerHTML = `
    <div id="welcome">
      <h2>GEM Tracker Metadata Audit</h2>
      <div id="summary-grid">
        <div class="summary-card"><div class="sc-val">${allTrackers.length}</div><div class="sc-label">Trackers</div></div>
        <div class="summary-card"><div class="sc-val">${validItems.length}</div><div class="sc-label">Data tabs</div></div>
        <div class="summary-card"><div class="sc-val">${totalFields.toLocaleString()}</div><div class="sc-label">Fields</div></div>
        <div class="summary-card"><div class="sc-val" style="color:var(--red)">${totalFlagged.toLocaleString()}</div><div class="sc-label">Flagged fields</div></div>
      </div>
      <div class="welcome-section">
        <h3>Flags by type <span style="font-weight:normal;font-size:0.85em;color:var(--dim)">(across all trackers)</span></h3>
        <table class="welcome-flag-table">
          <thead><tr><th>Flag</th><th>Count</th></tr></thead>
          <tbody>${flagRows}</tbody>
        </table>
      </div>
      ${catSection}
    </div>
  `;

  document.getElementById('welcome-ct-link')?.addEventListener('click', e => {
    e.preventDefault();
    showCrossTracker();
  });
}

/* ── Load a tracker tab ──────────────────────────────────── */
async function loadTable(tableName, el) {
  document.querySelectorAll('.tab-item').forEach(e => e.classList.remove('active'));
  el?.classList.add('active');

  document.getElementById('toolbar').hidden = false;
  document.getElementById('content').innerHTML = '<div class="state-msg">Loading…</div>';

  try {
    const res = await fetch(`./analysis/${encodeURIComponent(tableName)}.json`);
    if (!res.ok) throw new Error(res.statusText);
    currentData = await res.json();
    expandedField = null;
    renderTable();
  } catch (e) {
    document.getElementById('content').innerHTML =
      `<div class="state-msg state-error">Could not load <code>${escHtml(tableName)}.json</code>: ${escHtml(e.message)}</div>`;
  }
}

/* ── Field table ─────────────────────────────────────────── */
function getFilters() {
  return {
    search:   document.getElementById('search').value.toLowerCase(),
    flag:     document.getElementById('filter-flag').value,
    type:     document.getElementById('filter-type').value,
  };
}

function matchesFilters(field, f) {
  if (f.search && !field.field_name.toLowerCase().includes(f.search) &&
      !field.code_friendly_name_guess.includes(f.search)) return false;
  if (f.flag === '__any__' && field.flags.length === 0) return false;
  if (f.flag && f.flag !== '__any__' && !field.flags.some(fl => fl.startsWith(f.flag))) return false;
  const typeStr = field.subtype_guess ? `${field.type_guess}/${field.subtype_guess}` : field.type_guess;
  if (f.type && !typeStr.startsWith(f.type)) return false;
  return true;
}

function renderTable() {
  if (!currentData) return;

  const { n_rows, table_name, fields, tracker_info } = currentData;
  const nFlagged = fields.filter(f => f.flags.length > 0).length;

  const ti = tracker_info || {};
  const isInDb = summary.find(s => s.table_name === table_name)?.in_research_db ?? false;
  const sourceTag = isInDb
    ? `<span class="toolbar-db-badge">Research DB</span>`
    : `<span class="toolbar-csv-badge">Spreadsheet only</span>`;
  const subtitle = [
    ti.title ? escHtml(ti.title) : null,
    ti.citation ? `<span title="${escAttr(ti.citation)}" style="cursor:help;border-bottom:1px dashed var(--dim)">citation ↗</span>` : null,
    ti.contact ? `<span title="${escAttr(ti.contact)}" style="cursor:help;border-bottom:1px dashed var(--dim)">contact</span>` : null,
  ].filter(Boolean).join(' · ');

  const dupRows = currentData.n_duplicate_rows || 0;
  const dupNote = dupRows > 0
    ? ` · <span style="color:var(--red)" title="Rows where all column values match another row">${dupRows} duplicate row${dupRows !== 1 ? 's' : ''}</span>`
    : '';

  const localCount = Object.values(localOverrides[table_name] || {})
    .reduce((s, arr) => s + arr.length, 0);
  const downloadBtn = localCount > 0
    ? `<button class="download-overrides-btn" onclick="downloadOverrides()" title="Download merged overrides.json to commit to the repo">⬇ Download overrides.json (${localCount} pending)</button>`
    : '';

  const info = document.getElementById('table-info');
  info.innerHTML = `
    <span class="tname">${escHtml(formatTableName(table_name))} ${sourceTag}</span>
    <span class="tmeta">${n_rows.toLocaleString()} rows · ${fields.length} fields · <span style="color:var(--red)">${nFlagged} flagged</span>${dupNote}${subtitle ? ' · ' + subtitle : ''}</span>
    ${downloadBtn}
  `;

  const filters = getFilters();
  const filtered = fields.filter(f => matchesFilters(f, filters));
  const content = document.getElementById('content');

  if (filtered.length === 0) {
    content.innerHTML = '<div class="state-msg">No fields match the current filters.</div>';
    return;
  }

  const rows = filtered.map(field => renderFieldRow(field)).join('');
  content.innerHTML = `
    <table id="field-table">
      <thead>
        <tr>
          <th>Field</th>
          <th>Type</th>
          <th>Null %</th>
          <th>Unique</th>
          <th>Flags</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;

  content.querySelectorAll('.field-row').forEach(row => {
    row.addEventListener('click', () => {
      expandedField = expandedField === row.dataset.field ? null : row.dataset.field;
      renderTable();
      if (expandedField) {
        setTimeout(() => {
          content.querySelector('.field-row.expanded')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }, 0);
      }
    });
  });

  // Suppress/unsuppress flag buttons (inside detail rows, stop propagation to avoid row toggle)
  content.querySelectorAll('.suppress-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const { flag, table, field } = btn.dataset;
      let reason = '';
      if (!btn.classList.contains('unsuppress-btn')) {
        reason = prompt(`Reason for suppressing "${flag}" on "${field}" (optional):`) ?? '';
        if (reason === null) return; // user cancelled
      }
      toggleFlagSuppression(table, field, flag, reason);
      renderTable();
    });
  });
}

function renderFieldRow(field) {
  const typeHtml = field.subtype_guess
    ? `<span class="type-main">${field.type_guess}</span><span class="type-sep">/</span><span class="type-sub">${field.subtype_guess}</span>`
    : `<span class="type-main">${field.type_guess}</span>`;

  const nullPct = (field.null_rate * 100).toFixed(1);
  const nullCls = field.null_rate > 0.5 ? 'null-high' : field.null_rate > 0.1 ? 'null-mid' : '';

  const flagsHtml = [
    ...field.flags.map(f =>
      `<span class="flag flag-${escAttr(flagCls(f))}">${escHtml(flagLabel(f))}</span>`
    ),
    ...(field.suppressed_flags || []).map(s =>
      `<span class="flag flag-suppressed" title="Suppressed: ${escAttr(s.reason || 'no reason given')}">${escHtml(flagLabel(s.flag))}</span>`
    ),
  ].join('');

  const isExp = expandedField === field.field_name;
  let html = `
    <tr class="field-row ${isExp ? 'expanded' : ''}" data-field="${escAttr(field.field_name)}">
      <td><span class="fn-main">${escHtml(field.field_name)}</span><span class="fn-code">${escHtml(field.code_friendly_name_guess)}</span></td>
      <td class="type-cell">${typeHtml}</td>
      <td class="null-cell ${nullCls}">${nullPct}%</td>
      <td class="uniq-cell">${field.n_unique.toLocaleString()}</td>
      <td class="flags-cell">${flagsHtml || '<span style="color:var(--dim)">—</span>'}</td>
    </tr>
  `;

  if (isExp) html += `<tr class="detail-row"><td colspan="5">${renderDetail(field)}</td></tr>`;
  return html;
}

/* ── Field detail ────────────────────────────────────────── */
function renderDetail(field) {
  const totalNonNull = field.n_total - field.n_null;

  /* ── Stats strip ── */
  const statsHtml = `
    <div class="detail-stats">
      <div class="stat"><label>Rows</label><span>${field.n_total.toLocaleString()}</span></div>
      <div class="stat"><label>Non-null</label><span>${field.n_non_null.toLocaleString()}</span></div>
      <div class="stat"><label>Null</label><span>${field.n_null.toLocaleString()} (${(field.null_rate*100).toFixed(1)}%)</span></div>
      <div class="stat"><label>Unique</label><span>${field.n_unique.toLocaleString()}</span></div>
      ${field.portion_numeric != null
        ? `<div class="stat"><label>% numeric</label><span>${(field.portion_numeric*100).toFixed(1)}%</span></div>`
        : ''}
      <div class="stat"><label>Type guess</label><span>${field.type_guess}${field.subtype_guess ? ' / '+field.subtype_guess : ''}</span></div>
      <div class="stat"><label>Required?</label><span>${field.is_required_guess ? 'yes' : 'no'}</span></div>
      <div class="stat"><label>API name</label><code>${escHtml(field.code_friendly_name_guess)}</code></div>
    </div>
  `;

  /* ── Flags with suppress toggles ── */
  const tableName = currentData?.table_name ?? '';
  const allFlags = [
    ...field.flags.map(f => ({ flag: f, suppressed: false })),
    ...(field.suppressed_flags || []).map(s => ({ flag: s.flag, suppressed: true, reason: s.reason })),
  ];
  const flagsHtml = allFlags.length > 0 ? `
    <div class="detail-flags">
      ${allFlags.map(({ flag, suppressed, reason }) => {
        const key = flag.split(':')[0];
        const btnLabel = suppressed ? 'Unsuppress' : 'Suppress';
        const btnCls = suppressed ? 'suppress-btn unsuppress-btn' : 'suppress-btn';
        return `
          <div class="flag-with-action ${suppressed ? 'flag-suppressed-row' : ''}">
            <span class="flag flag-${escAttr(flagCls(flag))} ${suppressed ? 'flag-suppressed' : ''}"
                  title="${suppressed ? 'Suppressed: ' + escAttr(reason || 'no reason') : escHtml(flag)}"
            >${escHtml(flagLabel(flag))}</span>
            <button class="${btnCls}"
              data-flag="${escAttr(key)}"
              data-table="${escAttr(tableName)}"
              data-field="${escAttr(field.field_name)}"
            >${btnLabel}</button>
            ${suppressed && reason ? `<span class="suppress-reason">${escHtml(reason)}</span>` : ''}
          </div>`;
      }).join('')}
    </div>
  ` : '';

  /* ── Non-numeric outliers (for mostly_numeric_with_outliers flag) ── */
  const outliers = getNonNumericOutliers(field);
  const outliersHtml = outliers.length > 0 ? `
    <div class="detail-panel" style="border-color:#fbd38d">
      <div class="panel-head" style="background:#fffff0;color:#b7791f">Non-numeric values in this field</div>
      <div class="panel-body">
        <div class="value-list">
          ${outliers.map(([val, count]) => `
            <div class="value-row">
              <span class="value-label" style="color:#b7791f;font-weight:600">${escHtml(String(val))}</span>
              <div class="value-bar-wrap"><div class="value-bar" style="width:100%;background:#f6ad55;opacity:0.5"></div></div>
              <span class="value-pct">${count.toLocaleString()} rows</span>
            </div>
          `).join('')}
        </div>
        <div class="value-more" style="margin-top:6px">These values prevented this field from being typed as numeric. They may be special codes, errors, or intentional non-numeric entries.</div>
      </div>
    </div>
  ` : '';

  /* ── Null-proxy values (for numeric_null_proxies soft flag) ── */
  const nullProxies = getNullProxyOutliers(field);
  const nullProxiesHtml = nullProxies.length > 0 ? `
    <div class="detail-panel" style="border-color:#bee3f8">
      <div class="panel-head" style="background:#ebf8ff;color:#2c5282">Non-standard null values in this field</div>
      <div class="panel-body">
        <div class="value-list">
          ${nullProxies.map(([val, count]) => `
            <div class="value-row">
              <span class="value-label" style="color:#2b6cb0;font-family:'SF Mono','Fira Code',monospace">${escHtml(String(val))}</span>
              <div class="value-bar-wrap"><div class="value-bar" style="width:100%;background:#90cdf4;opacity:0.5"></div></div>
              <span class="value-pct">${count.toLocaleString()} rows</span>
            </div>
          `).join('')}
        </div>
        <div class="value-more" style="margin-top:6px">These values appear to be shorthand for missing data (e.g. "--", "**"). Consider standardizing to null/empty.</div>
      </div>
    </div>
  ` : '';

  /* ── Value distribution ── */
  const maxCount = field.top_values.length > 0 ? Math.max(...field.top_values.map(([,c]) => c)) : 1;
  const oosSet = new Set((field.out_of_set_values || []).map(v => String(v)));
  const valueBars = field.top_values.map(([val, count]) => {
    const pct = totalNonNull > 0 ? count / totalNonNull * 100 : 0;
    const barW = (count / maxCount * 100).toFixed(1);
    const isOos = val != null && oosSet.has(String(val));
    const isRare = !isOos && pct < 1 && ['categorical', 'ordinal', 'accuracy'].includes(field.subtype_guess);
    const labelStyle = isOos ? ' style="color:#e53e3e;font-weight:600"' : '';
    const oosIcon = isOos ? ` <span title="Not in reference set" style="color:#e53e3e;font-size:9px;vertical-align:middle">✗</span>` : '';
    return `
      <div class="value-row ${isRare ? 'value-rare' : ''}">
        <span class="value-label"${labelStyle} title="${escAttr(String(val ?? ''))}">${escHtml(val == null ? '(null)' : String(val))}${oosIcon}</span>
        <div class="value-bar-wrap"><div class="value-bar" style="width:${barW}%${isOos ? ';background:#fc8181' : ''}"></div></div>
        <span class="value-pct">${count.toLocaleString()} <span style="color:var(--dim)">(${pct.toFixed(1)}%)</span></span>
      </div>
    `;
  }).join('');

  /* ── Reference set provenance (shown when out_of_set_categorical is flagged) ── */
  const refSetHtml = (() => {
    if (!field.ref_set_source) return '';
    const srcLabel = {
      country: 'GEM country/area list',
      status: 'GEM status taxonomy',
      fuel_category: 'GEM fuel category taxonomy',
      api_allowed_values: 'API gold-standard allowed values',
    }[field.ref_set_source] || field.ref_set_source;

    const refValues = referenceSets[field.ref_set_source];
    const valuesHtml = refValues
      ? `<div class="ref-set-values">${refValues.map(v => `<span class="ref-set-chip">${escHtml(v)}</span>`).join('')}</div>`
      : '';

    const hasOosFlag = (field.flags || []).some(f => f.startsWith('out_of_set_categorical'));
    if (!hasOosFlag && !field.out_of_set_values?.length) return '';

    return `
      <div class="detail-panel" style="border-color:#fbb6ce">
        <div class="panel-head" style="background:#fff5f7;color:#97266d">Reference set: ${escHtml(srcLabel)}</div>
        <div class="panel-body">
          ${valuesHtml}
          ${field.out_of_set_values?.length
            ? `<div style="margin-top:8px;font-size:11px;color:#e53e3e">Out-of-set values: ${field.out_of_set_values.map(v => `<code>${escHtml(String(v))}</code>`).join(', ')}</div>`
            : ''}
          <div style="margin-top:6px;font-size:11px;color:var(--dim)">
            If the reference set doesn't match this field's domain, add it to <code>overrides.json</code> to suppress the flag.
          </div>
        </div>
      </div>
    `;
  })();

  const moreNote = field.n_unique > field.top_values.length
    ? `<div class="value-more">Showing ${field.top_values.length} of ${field.n_unique.toLocaleString()} unique values</div>`
    : '';

  const valuesPanel = `
    <div class="detail-panel">
      <div class="panel-head">Value distribution</div>
      <div class="panel-body">
        ${valueBars ? `<div class="value-list">${valueBars}</div>${moreNote}` : '<span style="color:var(--dim)">No values</span>'}
      </div>
    </div>
  `;

  /* ── Metadata panel ── */
  const metaPanel = buildMetaPanel(field);

  return `
    <div class="field-detail">
      ${statsHtml}
      ${flagsHtml}
      ${outliersHtml}
      ${nullProxiesHtml}
      ${refSetHtml}
      <div class="detail-body">
        ${valuesPanel}
        ${metaPanel}
      </div>
    </div>
  `;
}

function buildMetaPanel(field) {
  const parts = [];

  /* Definition from spreadsheet README */
  if (field.definition_from_readme) {
    parts.push(`
      <div>
        <p class="meta-def">${escHtml(field.definition_from_readme)}</p>
        ${field.notes_from_readme ? `<p class="meta-note">${escHtml(field.notes_from_readme)}</p>` : ''}
      </div>
    `);
  }

  /* Value definitions from README "Definitions" sections */
  if (field.value_definitions?.length) {
    const rows = field.value_definitions.map(({ name, definition }) => `
      <div class="meta-prop">
        <label style="font-family:'SF Mono','Fira Code',monospace;font-size:10px">${escHtml(name)}</label>
        <span class="val">${escHtml(definition || '—')}</span>
      </div>
    `).join('');
    parts.push(`
      <div>
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:var(--dim);margin-bottom:6px">Allowed values</div>
        <div class="meta-props">${rows}</div>
      </div>
    `);
  }

  /* API / gold-standard metadata */
  if (field.api_metadata) {
    const m = field.api_metadata;
    const props = [];

    if (m.definition && m.definition !== field.definition_from_readme)
      props.push(['Definition', escHtml(m.definition)]);
    if (m.data_type)
      props.push(['Type', `${m.data_type}${m.data_sub_type ? ' / '+m.data_sub_type : ''}`]);
    if (m.category)
      props.push(['Category', m.category]);
    if (m.is_required !== undefined)
      props.push(['Required', String(m.is_required)]);
    if (m.taxonomy)
      props.push(['Taxonomy', m.taxonomy]);
    if (m.allowed_values?.length)
      props.push(['Allowed values', escHtml(m.allowed_values.join(', '))]);
    if (m.required_format_regex)
      props.push(['Regex', `<code>${escHtml(m.required_format_regex)}</code>`]);
    if (m.unit_name_short)
      props.push(['Unit', escHtml(m.unit_name_short)]);
    if (m.null_is_what)
      props.push(['Null means', escHtml(m.null_is_what)]);
    if (m.other_rules)
      props.push(['Rules', escHtml(m.other_rules)]);

    if (props.length > 0) {
      const propsHtml = props.map(([label, val]) =>
        `<div class="meta-prop"><label>${label}</label><span class="val">${val}</span></div>`
      ).join('');
      parts.push(`<div class="api-source meta-props">${propsHtml}</div>`);
    }
  }

  if (parts.length === 0 && !field.definition_from_readme && !field.api_metadata) {
    parts.push('<span style="color:var(--dim);font-size:12px">No metadata available for this field yet.</span>');
  }

  const label = field.api_metadata ? 'Metadata (gold standard ✓)' : 'Metadata';
  return `
    <div class="detail-panel">
      <div class="panel-head">${label}</div>
      <div class="panel-body">${parts.join('<hr style="border:none;border-top:1px solid var(--border);margin:8px 0">')}</div>
    </div>
  `;
}

/* ── Cross-tracker view ──────────────────────────────────── */

async function showCrossTracker() {
  currentView = 'cross-tracker';
  document.querySelectorAll('.tab-item').forEach(e => e.classList.remove('active'));
  renderSidebar();
  document.getElementById('toolbar').hidden = true;

  if (!crossTrackerData) {
    document.getElementById('content').innerHTML =
      `<div class="state-msg state-error">Could not load <code>analysis/cross_tracker.json</code>. Run <code>python3 cross_tracker.py</code> first.</div>`;
    return;
  }
  renderCrossTracker();
}

function renderCrossTracker() {
  const d = crossTrackerData;
  const s = d.stats;
  document.getElementById('content').innerHTML = `
    <div id="ct-page">
      <div class="ct-page-header">
        <div>
          <h2 class="ct-page-title">Cross-tracker field analysis</h2>
          <div class="ct-page-stats">
            ${s.n_field_records.toLocaleString()} fields across ${new Set(summary.map(x=>x.tracker_slug)).size} trackers ·
            <strong>${s.n_exact_groups}</strong> exact-name groups ·
            <strong>${s.n_fuzzy_pairs}</strong> fuzzy pairs
            <span class="ct-gen-time" title="${escHtml(d.generated_at)}">generated ${new Date(d.generated_at).toLocaleDateString()}</span>
          </div>
        </div>
      </div>

      <details class="ct-methodology">
        <summary>Methodology</summary>
        <p>${escHtml(d.methodology)}</p>
      </details>

      <div class="ct-tabs">
        <button class="ct-tab ${ctActiveTab==='categories'?'active':''}" data-tab="categories">
          Categories <span class="ct-tab-count">7</span>
        </button>
        <button class="ct-tab ${ctActiveTab==='exact'?'active':''}" data-tab="exact">
          Exact matches <span class="ct-tab-count">${s.n_exact_groups}</span>
        </button>
        <button class="ct-tab ${ctActiveTab==='fuzzy'?'active':''}" data-tab="fuzzy">
          Fuzzy pairs <span class="ct-tab-count">${s.n_fuzzy_pairs}</span>
        </button>
      </div>

      <div class="ct-filters" id="ct-filters" ${ctActiveTab === 'categories' ? 'style="display:none"' : ''}>
        ${ctActiveTab === 'exact' ? renderExactFilters() : ctActiveTab === 'fuzzy' ? renderFuzzyFilters() : ''}
      </div>

      <div id="ct-groups"></div>
    </div>
  `;

  document.querySelectorAll('.ct-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      ctActiveTab = btn.dataset.tab;
      renderCrossTracker();
    });
  });

  ['ct-search','ct-min-trackers','ct-cats-only','ct-conflicts-only',
   'ct-fuzzy-search','ct-fuzzy-min','ct-fuzzy-sim'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', refreshCtGroups);
  });

  refreshCtGroups();
}

/* ── Category panels ─────────────────────────────────────── */
const CAT_ORDER = ['IDs','Names','Status','Capacity','Location','Temporal','Entities'];

function renderCategoryPanels() {
  const cats = crossTrackerData?.categories ?? {};
  const allTrackers = [...new Set(summary
    .filter(s => !SKIP_TRACKER_SLUGS.has(s.tracker_slug) && !s.tab_slug.startsWith(SKIP_TAB_PREFIX))
    .map(s => s.tracker_slug)
  )].sort();

  return CAT_ORDER.filter(c => cats[c]).map(catName => {
    const cat = cats[catName];
    const jac = cat.value_jaccard;
    const jacStr = jac != null
      ? `<span class="ct-jaccard" style="background:${jaccardColor(jac)}" title="Mean value Jaccard across categorical groups">value overlap ${jac.toFixed(2)}</span>`
      : '';

    // Per-tracker rows
    const rows = allTrackers.map(slug => {
      const isDb = summary.some(s => s.tracker_slug === slug && s.in_research_db);
      const fields = cat.tracker_fields?.[slug] || [];
      const present = fields.length > 0;
      const fieldNames = fields.map(f => f.field_name).join(', ');
      const groupKeys = [...new Set(fields.map(f => f.group_key))].join(', ');
      return `
        <tr class="${present ? '' : 'cat-row-missing'}">
          <td>${escHtml(formatTrackerName(slug))}${isDb ? ' <span class="sb-db-badge" style="font-size:8px">DB</span>' : ''}</td>
          <td>${present
            ? `<span class="cat-present" title="${escAttr(groupKeys)}">✓ ${escHtml(fieldNames)}</span>`
            : '<span class="cat-absent">—</span>'}</td>
        </tr>`;
    }).join('');

    // Compatibility blocker note
    let blocker = '';
    if (catName === 'Status' && jac != null && jac < 0.5) {
      const vo = crossTrackerData.exact_groups.find(g => g.group_key === 'status')?.value_overlap;
      if (vo) blocker = `<div class="cat-blocker">⚠ ${vo.tracker_specific ? Object.keys(vo.tracker_specific).length : '?'} trackers have tracker-specific status values not shared by others. Shared: ${vo.shared_values.slice(0,4).join(', ')}${vo.shared_values.length > 4 ? '…' : ''}.</div>`;
    } else if (cat.n_trackers_with_field > 0 && cat.n_trackers_with_field < allTrackers.length) {
      const nMissing = allTrackers.length - cat.n_trackers_with_field;
      blocker = `<div class="cat-blocker-soft">${nMissing} tracker${nMissing !== 1 ? 's' : ''} missing this category.</div>`;
    }

    return `
      <div class="ct-card ct-card-expanded">
        <div class="ct-card-head">
          <div class="ct-card-title">
            <span class="ct-field-name">${escHtml(catName)}</span>
            <span class="cat-desc">${escHtml(cat.description)}</span>
            ${jacStr}
          </div>
          <div class="ct-card-right">
            <span class="ct-tracker-count">${cat.n_trackers_with_field}/${allTrackers.length} trackers</span>
          </div>
        </div>
        <div class="ct-card-body">
          ${blocker}
          <table class="ct-field-table cat-table">
            <thead><tr><th>Tracker</th><th>Field(s) used</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  }).join('');
}

function renderExactFilters() {
  return `
    <input type="search" id="ct-search" class="ct-filter-input" placeholder="Search field names…" style="width:200px">
    <label class="ct-filter-label">Min trackers:
      <input type="number" id="ct-min-trackers" class="ct-filter-input" value="2" min="2" max="24" style="width:55px">
    </label>
    <label class="ct-filter-label"><input type="checkbox" id="ct-cats-only"> Categoricals only</label>
    <label class="ct-filter-label"><input type="checkbox" id="ct-conflicts-only"> Value conflicts (jaccard &lt; 0.5)</label>
  `;
}

function renderFuzzyFilters() {
  return `
    <input type="search" id="ct-fuzzy-search" class="ct-filter-input" placeholder="Search field names…" style="width:200px">
    <label class="ct-filter-label">Min combined trackers:
      <input type="number" id="ct-fuzzy-min" class="ct-filter-input" value="3" min="2" max="24" style="width:55px">
    </label>
    <label class="ct-filter-label">Min similarity:
      <select id="ct-fuzzy-sim" class="ct-filter-input">
        <option value="0.5">0.5</option>
        <option value="0.67">0.67</option>
        <option value="1.0">1.0 (exact words, different order)</option>
      </select>
    </label>
  `;
}

function refreshCtGroups() {
  const container = document.getElementById('ct-groups');
  if (!container) return;

  if (ctActiveTab === 'categories') {
    container.innerHTML = renderCategoryPanels();
    return;
  }

  if (ctActiveTab === 'exact') {
    const search   = document.getElementById('ct-search')?.value.toLowerCase() ?? '';
    const minT     = parseInt(document.getElementById('ct-min-trackers')?.value ?? '2');
    const catsOnly = document.getElementById('ct-cats-only')?.checked ?? false;
    const conflictsOnly = document.getElementById('ct-conflicts-only')?.checked ?? false;

    let groups = crossTrackerData.exact_groups.filter(g => {
      if (g.n_trackers < minT) return false;
      if (search && !g.group_key.includes(search) && !g.label.toLowerCase().includes(search)) return false;
      if (catsOnly && !g.subtypes.some(s => ['categorical','ordinal','accuracy'].includes(s))) return false;
      if (conflictsOnly && (!g.value_overlap || g.value_overlap.jaccard >= 0.5)) return false;
      return true;
    });

    container.innerHTML = groups.length === 0
      ? '<div class="state-msg">No groups match the current filters.</div>'
      : groups.map(renderExactGroup).join('');
  } else {
    const search = document.getElementById('ct-fuzzy-search')?.value.toLowerCase() ?? '';
    const minT   = parseInt(document.getElementById('ct-fuzzy-min')?.value ?? '3');
    const minSim = parseFloat(document.getElementById('ct-fuzzy-sim')?.value ?? '0.5');

    let pairs = crossTrackerData.fuzzy_pairs.filter(p => {
      if (p.n_trackers_a + p.n_trackers_b < minT) return false;
      if (p.similarity < minSim) return false;
      if (search && !p.name_a.includes(search) && !p.name_b.includes(search) &&
          !p.label_a.toLowerCase().includes(search) && !p.label_b.toLowerCase().includes(search)) return false;
      return true;
    });

    container.innerHTML = pairs.length === 0
      ? '<div class="state-msg">No pairs match the current filters.</div>'
      : pairs.map(renderFuzzyPair).join('');
  }

  // Wire up expand/collapse toggles
  document.getElementById('ct-groups')?.querySelectorAll('.ct-group-toggle').forEach(btn => {
    btn.addEventListener('click', e => {
      const card = e.currentTarget.closest('.ct-card');
      card.classList.toggle('ct-card-expanded');
      btn.textContent = card.classList.contains('ct-card-expanded') ? '▲' : '▼';
    });
  });
}

function renderExactGroup(g) {
  const vo = g.value_overlap;
  const jaccardHtml = vo
    ? `<span class="ct-jaccard" style="background:${jaccardColor(vo.jaccard)}" title="Value overlap (Jaccard) across categorical fields">${vo.jaccard.toFixed(2)}</span>`
    : '';
  const subtypeHtml = g.subtypes.map(s =>
    `<span class="ct-subtype-chip">${s}</span>`).join('');

  return `
    <div class="ct-card">
      <div class="ct-card-head">
        <div class="ct-card-title">
          <span class="ct-field-name">${escHtml(g.label)}</span>
          <code class="ct-cfn">${escHtml(g.group_key)}</code>
          ${subtypeHtml}
          ${jaccardHtml}
        </div>
        <div class="ct-card-right">
          <span class="ct-tracker-count">${g.n_trackers} trackers</span>
          <button class="ct-group-toggle" title="Expand details">▼</button>
        </div>
      </div>
      <div class="ct-card-trackers">
        ${g.trackers.map(t => trackerBadge(t)).join('')}
      </div>
      <div class="ct-card-body">
        ${vo ? renderValueOverlap(vo) : ''}
        ${renderFieldTable(g.fields)}
      </div>
    </div>
  `;
}

function renderFuzzyPair(p) {
  const vo = p.value_overlap;
  const jaccardHtml = vo
    ? `<span class="ct-jaccard" style="background:${jaccardColor(vo.jaccard)}" title="Value overlap across categorical fields">${vo.jaccard.toFixed(2)}</span>`
    : '';
  const simColor = p.similarity >= 1 ? '#276749' : p.similarity >= 0.67 ? '#b7791f' : '#718096';

  return `
    <div class="ct-card">
      <div class="ct-card-head">
        <div class="ct-card-title">
          <span class="ct-field-name">${escHtml(p.label_a)}</span>
          <code class="ct-cfn">${escHtml(p.name_a)}</code>
          <span class="ct-arrow">↔</span>
          <span class="ct-field-name">${escHtml(p.label_b)}</span>
          <code class="ct-cfn">${escHtml(p.name_b)}</code>
          ${jaccardHtml}
        </div>
        <div class="ct-card-right">
          <span class="ct-sim-badge" style="color:${simColor}">sim ${p.similarity.toFixed(2)}</span>
          <button class="ct-group-toggle" title="Expand details">▼</button>
        </div>
      </div>
      <div class="ct-card-trackers">
        <span class="ct-side-label">A:</span>
        ${p.trackers_a.map(t => trackerBadge(t)).join('')}
        <span class="ct-side-label" style="margin-left:8px">B:</span>
        ${p.trackers_b.map(t => trackerBadge(t)).join('')}
      </div>
      <div class="ct-card-body">
        ${vo ? renderValueOverlap(vo) : ''}
        <div class="ct-pair-tables">
          <div>
            <div class="ct-side-heading">${escHtml(p.name_a)}</div>
            ${renderFieldTable(p.fields_a)}
          </div>
          <div>
            <div class="ct-side-heading">${escHtml(p.name_b)}</div>
            ${renderFieldTable(p.fields_b)}
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderValueOverlap(vo) {
  if (!vo) return '';
  const sharedHtml = vo.shared_values.map(v =>
    `<span class="ct-val-chip ct-val-shared">${escHtml(v)}</span>`).join('');
  const partialHtml = vo.partial_values.map(v =>
    `<span class="ct-val-chip ct-val-partial">${escHtml(v)}</span>`).join('');
  const specificRows = Object.entries(vo.tracker_specific).map(([tracker, vals]) =>
    `<div class="ct-specific-row">
      <span class="ct-specific-tracker">${escHtml(formatTrackerName(tracker))}:</span>
      ${vals.map(v => `<span class="ct-val-chip ct-val-specific">${escHtml(v)}</span>`).join('')}
    </div>`
  ).join('');

  return `
    <div class="ct-value-overlap">
      <div class="ct-vo-head">
        <span class="ct-vo-title">Value overlap</span>
        <span class="ct-vo-jaccard">Jaccard ${vo.jaccard.toFixed(2)} across ${vo.n_fields} fields</span>
      </div>
      ${sharedHtml || partialHtml ? `
        <div class="ct-vo-row">
          ${sharedHtml ? `<span class="ct-vo-label">All share:</span>${sharedHtml}` : ''}
        </div>` : ''}
      ${partialHtml ? `
        <div class="ct-vo-row">
          <span class="ct-vo-label">Majority share:</span>${partialHtml}
        </div>` : ''}
      ${specificRows ? `<div class="ct-vo-specific">${specificRows}</div>` : ''}
    </div>
  `;
}

function renderFieldTable(fields) {
  if (!fields.length) return '';
  const rows = fields.map(f => `
    <tr>
      <td>${escHtml(formatTrackerName(f.tracker_slug))}${f.in_research_db ? ' <span class="sb-db-badge" style="font-size:8px">DB</span>' : ''}</td>
      <td>${escHtml(f.field_name)}${f.field_name !== f.code_friendly_name && f.code_friendly_name !== f.field_name.toLowerCase().replace(/\s+/g,'_') ? `<br><code style="font-size:10px;color:var(--dim)">${escHtml(f.code_friendly_name)}</code>` : ''}</td>
      <td>${f.subtype_guess ? `<span class="type-sub">${f.subtype_guess}</span>` : `<span style="color:var(--dim)">${f.type_guess||''}</span>`}</td>
      <td style="color:var(--dim)">${(f.null_rate*100).toFixed(0)}%</td>
      <td style="font-size:11px;color:var(--dim);max-width:220px">${escHtml(f.definition_from_readme || '')}</td>
    </tr>
  `).join('');
  return `
    <table class="ct-field-table">
      <thead><tr><th>Tracker</th><th>Field name</th><th>Type</th><th>Null%</th><th>Definition</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function trackerBadge(slug) {
  const isDb = summary.some(s => s.tracker_slug === slug && s.in_research_db);
  return `<span class="ct-tracker-badge ${isDb ? 'ct-tracker-db' : ''}" title="${escAttr(slug)}">${escHtml(formatTrackerName(slug))}</span>`;
}

function jaccardColor(j) {
  if (j >= 0.8) return '#c6f6d5';   // green
  if (j >= 0.5) return '#fefcbf';   // yellow
  if (j > 0)    return '#fed7d7';   // red
  return '#fee2e2';                  // red (empty intersection)
}

/* ── Formatting helpers ──────────────────────────────────── */
const ACRONYMS = { gem:'GEM', ggit:'GGIT', goit:'GOIT', gmet:'GMET', gcmt:'GCMT', gcpt:'GCPT',
                   lng:'LNG', ngl:'NGL', co2:'CO₂', chp:'CHP', ghg:'GHG', mw:'MW', mwh:'MWh' };

function formatTrackerName(slug) {
  return slug
    .replace(/_(january|february|march|april|may|june|july|august|september|october|november|december)_\d{4}(_\w+)?$/i, '')
    .replace(/_\d{4}_\d{2}(_\w+)?$/, '')
    .replace(/_\d{4}$/, '')
    .replace(/_v\d+(_\d+)?$/i, '')
    .replace(/_final$/, '')
    .replace(/_release$/, '')
    .replace(/_global_energy_monitor_?\d*$/i, '')
    .split('_')
    .map(w => ACRONYMS[w.toLowerCase()] || (w.charAt(0).toUpperCase() + w.slice(1)))
    .join(' ');
}

function formatTabName(slug) {
  return slug.split('_').map(w => ACRONYMS[w.toLowerCase()] || (w.charAt(0).toUpperCase() + w.slice(1))).join(' ');
}

function formatTableName(name) {
  const [tracker, tab] = name.split('__');
  return tab ? `${formatTrackerName(tracker)} — ${formatTabName(tab)}` : name;
}

function flagCls(flag) {
  const key = flag.split(':')[0];
  if (key === 'numeric_outliers')            return 'error';
  if (key === 'out_of_set_categorical')      return 'error';
  if (key === 'wrong_multi_value_separator') return 'error';
  if (key === 'non_standard_null_proxies')   return 'soft';
  if (key === 'numeric_null_proxies')        return 'soft';
  if (key === 'mostly_numeric_with_outliers') return 'numeric';
  if (key === 'categorical_rare_values')     return 'rare';
  if (key === 'potential_multi_value')       return 'multi';
  if (key === 'year_out_of_range')           return 'warn';
  if (key === 'boolean_encoding')            return 'info';
  if (key === 'multi_value_separator_check') return 'info';
  if (key === 'required_field_has_nulls')    return 'warn';
  return 'other';
}

function flagLabel(flag, long = false) {
  const [key, detail] = flag.split(':');
  if (key === 'numeric_outliers') {
    const m = flag.match(/(\d+)_non/); const n = m?.[1] ?? '?';
    return long ? 'Non-numeric values in numeric field' : `${n} non-numeric`;
  }
  if (key === 'out_of_set_categorical') {
    const m = flag.match(/(\d+)_values/); const n = m?.[1] ?? '?';
    return long ? 'Values outside reference set' : `${n} out-of-set`;
  }
  if (key === 'wrong_multi_value_separator')
    return long ? 'Wrong multi-value separator (comma)' : 'wrong separator';
  if (key === 'non_standard_null_proxies')
    return long ? 'Non-standard null shorthands' : 'null shorthands';
  if (key === 'numeric_null_proxies')
    return long ? 'Non-standard null values' : 'chars as nulls';
  if (key === 'mostly_numeric_with_outliers')
    return long ? 'Numeric with outliers' : 'numeric outliers';
  if (key === 'categorical_rare_values') {
    const m = flag.match(/(\d+)_values/); const n = m?.[1] ?? '?';
    return long ? 'Rare categorical values' : `${n} rare value${n !== '1' ? 's' : ''}`;
  }
  if (key === 'potential_multi_value')
    return long ? 'Potential multi-value' : 'multi-value';
  if (key === 'year_out_of_range') {
    const m = flag.match(/(\d+)_invalid/); const n = m?.[1] ?? '?';
    return long ? 'Year values out of range' : `${n} invalid year${n !== '1' ? 's' : ''}`;
  }
  if (key === 'boolean_encoding')
    return long ? `Boolean encoding: ${detail || ''}` : `bool: ${detail || ''}`;
  if (key === 'multi_value_separator_check')
    return long ? `Multi-value separator in use: ${detail || ''}` : `sep: ${detail || ''}`;
  if (key === 'required_field_has_nulls')
    return long ? 'Required field has null values' : 'required+nulls';
  return flag;
}

/* Null-proxy detection — mirrors analyze.py logic */
const NULL_PROXIES = new Set(['', '*', '-', 'n/a', 'N/A', 'UA', 'ua', 'None', 'none', 'NA', 'na', 'null', 'NULL']);
const EXTENDED_NULL_RE = /^(\*{2,}|#{2,}|\?{2,}|-{2,}|={2,}|~{2,}|tbd|t\.b\.d\.|nd|nr|ns|nk|unk(nown)?|unspecified|unclear|unavailable|not\s+(available|found|applicable|reported|known))$/i;

function looksLikeNullProxy(val) {
  if (val == null) return true;
  const s = String(val).trim();
  return NULL_PROXIES.has(s) || EXTENDED_NULL_RE.test(s);
}

/* Values in top_values that are non-numeric and not null-proxy-like (genuine outliers) */
function getNonNumericOutliers(field) {
  if (!field.flags.some(f => f === 'mostly_numeric_with_outliers')) return [];
  return field.top_values.filter(([val]) => {
    if (looksLikeNullProxy(val)) return false;
    return isNaN(parseFloat(String(val).replace(/,/g, '')));
  });
}

/* Values in top_values that are non-numeric and look like null-proxy shorthands */
function getNullProxyOutliers(field) {
  if (!field.flags.some(f => f === 'numeric_null_proxies')) return [];
  return field.top_values.filter(([val]) => {
    if (val == null || NULL_PROXIES.has(String(val))) return false;
    if (!isNaN(parseFloat(String(val).replace(/,/g, '')))) return false;
    return looksLikeNullProxy(val);
  });
}

/* ── XSS-safe helpers ────────────────────────────────────── */
function escHtml(s) {
  return String(s ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function escAttr(s) { return escHtml(s); }

/* ── Wire up filters ─────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  ['search','filter-flag','filter-type'].forEach(id => {
    document.getElementById(id).addEventListener('input', () => { if (currentData) renderTable(); });
  });
  document.getElementById('sidebar-flagged-only').addEventListener('change', renderSidebar);
  init();
});
