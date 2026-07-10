const $ = (id) => document.getElementById(id);

// ---------- preset chips ----------
document.querySelectorAll('.chip').forEach((btn) => {
  btn.addEventListener('click', () => {
    $('intent').value = btn.dataset.preset;
    $('intent').focus();
  });
});

// ---------- translate ----------
async function translate() {
  const intent = $('intent').value.trim();
  if (!intent) return;
  const btn = $('translate');
  btn.disabled = true; btn.textContent = 'Translating…';
  $('result').classList.add('hidden');
  $('error').classList.add('hidden');
  try {
    const r = await fetch('/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intent }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const card = await r.json();
    renderCard(card);
  } catch (e) {
    $('error').textContent = `Something went wrong: ${e.message}`;
    $('error').classList.remove('hidden');
  } finally {
    btn.disabled = false; btn.textContent = 'Translate';
  }
}

$('translate').addEventListener('click', translate);
$('intent').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) translate();
});

// ---------- render card ----------
function renderCard(card) {
  const flagsHTML = (card.flags || []).map((f) =>
    `<span class="tag flag">${escape(f)}</span>`
  ).join('');
  const catsHTML = (card.category_tags || []).map((c) =>
    `<span class="tag">${escape(c)}</span>`
  ).join('');

  const musts = renderList(card.must_haves, 'card-block');
  const nices = renderList(card.nice_to_haves, 'card-block');
  const disqs = renderList(card.disqualifiers, 'card-block dq');
  const queries = (card.search_queries || []).map((q) =>
    `<li onclick="copyToClipboard('${escape(q).replace(/'/g,'\\'')}')">${escape(q)} <small>(copy)</small></li>`
  ).join('');

  const ent = card.entities || {};
  const entLines = Object.entries(ent)
    .filter(([_, v]) => v)
    .map(([k, v]) => `<li><b>${k}:</b> ${escape(JSON.stringify(v))}</li>`)
    .join('');

  $('result').innerHTML = `
    <div class="card-title">Structured Requirement Card</div>
    <p class="card-canonical">${escape(card.canonical_intent || '(no intent)')}</p>

    <div class="card-meta">
      ${catsHTML}
      ${flagsHTML}
    </div>

    ${musts ? `<div class="card-block"><h4>Must-haves</h4><ul>${musts}</ul></div>` : ''}
    ${nices ? `<div class="card-block"><h4>Nice-to-haves</h4><ul>${nices}</ul></div>` : ''}
    ${disqs ? `<div class="card-block dq"><h4>Disqualifiers</h4><ul>${disqs}</ul></div>` : ''}
    ${queries ? `<div class="card-block card-queries"><h4>Search queries (click to copy)</h4><ul>${queries}</ul></div>` : ''}
    ${entLines ? `<div class="card-block"><h4>Extracted entities</h4><ul>${entLines}</ul></div>` : ''}

    <div class="card-confidence">
      Confidence: <b>${(card.confidence * 100).toFixed(0)}%</b>
    </div>
  `;
  $('result').classList.remove('hidden');
}

function renderList(items, cls) {
  if (!items || items.length === 0) return '';
  return items.map((i) => `<li>${escape(i)}</li>`).join('');
}

function escape(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]
  ));
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text.replace(/&#39;/g,"'"));
}

// ---------- validator ----------
async function runValidator() {
  const btn = $('validate');
  btn.disabled = true; btn.textContent = 'Running 12 adversarial cases…';
  $('validator-result').classList.add('hidden');
  try {
    const r = await fetch('/validate', { method: 'POST' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const result = await r.json();
    renderValidator(result);
  } catch (e) {
    $('validator-result').innerHTML = `<div class="error">Failed: ${e.message}</div>`;
    $('validator-result').classList.remove('hidden');
  } finally {
    btn.disabled = false; btn.textContent = 'Run the 12-case adversarial test';
  }
}
$('validate').addEventListener('click', runValidator);

function renderValidator(r) {
  const rows = r.per_case.map((c) => `
    <tr>
      <td>${c.id}</td>
      <td><em>${escape(c.klass)}</em></td>
      <td>${escape(c.intent.substring(0, 60))}${c.intent.length > 60 ? '…' : ''}</td>
      <td><span class="verdict ${c.verdict}">${c.verdict}</span></td>
    </tr>
  `).join('');

  $('validator-result').innerHTML = `
    <div class="card-title">Adversarial validator results</div>
    <div class="summary-row">
      <span><b>Accuracy:</b> ${(r.accuracy * 100).toFixed(1)}%</span>
      <span><b>Passed:</b> ${r.passed}/${r.total_cases}</span>
      <span><b>Partial:</b> ${r.partial}</span>
      <span><b>Failed:</b> ${r.failed}</span>
      <span><b>Confidence calibration:</b> ${(r.confidence_calibration_score * 100).toFixed(1)}%</span>
    </div>
    <table>
      <thead>
        <tr><th>#</th><th>Class</th><th>Intent</th><th>Result</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  $('validator-result').classList.remove('hidden');
}
