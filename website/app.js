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
    fetchMatches(card);
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

// ---------- suggested matches ----------
async function fetchMatches(card) {
  const el = $('matches');
  if (!el) return;
  el.innerHTML = `<div class="card-title">Suggested matches</div><div class="matches-loading">Finding illustrative matches…</div>`;
  el.classList.remove('hidden');
  try {
    const r = await fetch('/suggest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    renderMatches(j);
  } catch (e) {
    el.innerHTML = `<div class="card-title">Suggested matches</div><div class="matches-loading">Could not load matches: ${escape(e.message)}</div>`;
  }
}

function renderMatches(data) {
  const el = $('matches');
  if (!data.matches || data.matches.length === 0) {
    el.innerHTML = `
      <div class="card-title">Suggested matches</div>
      <div class="matches-loading">${escape(data.note || 'No matches to suggest.')}</div>
    `;
    return;
  }
  const rows = data.matches.map((m) => `
    <div class="match-row">
      <div class="match-head">
        <div class="match-name">${escape(m.product_name || '(unnamed)')}</div>
        <div class="match-score">${Math.round((m.match_score || 0) * 100)}%</div>
      </div>
      <div class="match-meta">${escape(m.category || '')} · ₹${(m.price_range_inr?.min ?? '?').toLocaleString?.() ?? '?'}–₹${(m.price_range_inr?.max ?? '?').toLocaleString?.() ?? '?'}</div>
      <div class="match-why">${escape(m.why_match || '')}</div>
      ${(m.typical_seller_types || []).length ? `<div class="match-sellers">${m.typical_seller_types.map((s) => `<span class="tag">${escape(s)}</span>`).join('')}</div>` : ''}
    </div>
  `).join('');
  el.innerHTML = `
    <div class="card-title">Suggested matches</div>
    <div class="matches-note">${escape(data.note || '')}</div>
    <div class="matches-grid">${rows}</div>
  `;
}

// ---------- chatbox ----------
const chatState = { messages: [] };

function addMsg(role, text, opts = {}) {
  const el = document.createElement('div');
  el.className = `msg ${role}` + (opts.thinking ? ' thinking' : '');
  el.textContent = text;
  $('chat-log').appendChild(el);
  $('chat-log').scrollTop = $('chat-log').scrollHeight;
  return el;
}

async function sendChat() {
  const text = $('chat-text').value.trim();
  if (!text) return;
  $('chat-text').value = '';
  $('chat-send').disabled = true;

  chatState.messages.push({ role: 'user', content: text });
  addMsg('user', text);
  const thinking = addMsg('bot', 'thinking…', { thinking: true });

  try {
    const r = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: chatState.messages }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    thinking.remove();
    // Show conversational reply (with any code blocks stripped for display, but preserved for card)
    const displayText = (j.reply || '').replace(/```(?:json)?[\s\S]*?```/g, '').trim();
    addMsg('bot', displayText || '(assistant returned no text)');
    chatState.messages.push({ role: 'assistant', content: j.reply });

    // If a Requirement Card was extracted, render it below the demo section too
    if (j.card) {
      const summary = document.createElement('div');
      summary.className = 'msg bot';
      summary.innerHTML = `<b>Requirement card generated.</b> Scroll up to see it rendered in the demo section.`;
      $('chat-log').appendChild(summary);
      renderCard(j.card);
      document.getElementById('result').scrollIntoView({ behavior: 'smooth' });
    }
  } catch (e) {
    thinking.remove();
    addMsg('bot', `Something went wrong: ${e.message}`);
  } finally {
    $('chat-send').disabled = false;
    $('chat-text').focus();
  }
}

$('chat-send').addEventListener('click', sendChat);
$('chat-text').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendChat(); });

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
