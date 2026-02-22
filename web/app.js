/* ── MEEP-KB Chat App ─────────────────────────────────────────────────── */

const API_BASE = 'http://localhost:8765';
let chatHistory = [];

// ── marked.js 설정 ─────────────────────────────────────────────────────────
marked.setOptions({
  highlight: (code, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value;
    }
    return hljs.highlightAuto(code).value;
  },
  breaks: true,
  gfm: true,
});

// ── 초기화 ─────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  loadStatus();
  setInterval(loadStatus, 30000); // 30초마다 갱신

  const input = document.getElementById('query-input');
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendQuery();
    }
  });

  // 자동 높이 조정
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });
});

// ── 서버 상태 로드 ──────────────────────────────────────────────────────────
async function loadStatus() {
  const badge = document.getElementById('server-badge');
  const statusText = document.getElementById('server-status-text');
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    if (!res.ok) throw new Error('서버 오류');
    const data = await res.json();

    document.getElementById('stat-errors').textContent   = fmtNum(data.db_errors);
    document.getElementById('stat-examples').textContent = fmtNum(data.db_examples);
    document.getElementById('stat-docs').textContent     = fmtNum(data.db_docs);
    document.getElementById('stat-nodes').textContent    = fmtNum(data.graph_nodes);

    badge.className = 'server-badge online';
    statusText.textContent = data.server_ready ? '서버 준비 완료' : '서버 초기화 중...';
  } catch {
    badge.className = 'server-badge offline';
    statusText.textContent = '서버 연결 실패';
    setStatDash();
  }
}

function setStatDash() {
  ['stat-errors','stat-examples','stat-docs','stat-nodes'].forEach(id => {
    document.getElementById(id).textContent = '-';
  });
}

function fmtNum(n) {
  if (n < 0) return '-';
  return n.toLocaleString('ko-KR');
}

// ── 예제 쿼리 설정 ─────────────────────────────────────────────────────────
function setQuery(q) {
  const input = document.getElementById('query-input');
  input.value = q;
  input.focus();
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
}

// ── 메시지 전송 ────────────────────────────────────────────────────────────
async function sendQuery() {
  const input   = document.getElementById('query-input');
  const nSelect = document.getElementById('n-select');
  const btn     = document.getElementById('send-btn');
  const query   = input.value.trim();

  if (!query) return;

  // 환영 카드 제거
  const welcome = document.querySelector('.welcome-card');
  if (welcome) welcome.remove();

  // 사용자 메시지 추가
  appendUserMessage(query);

  // 입력창 초기화 + 비활성화
  input.value = '';
  input.style.height = 'auto';
  input.disabled = true;
  btn.disabled   = true;

  // 로딩 스피너
  const loadingId = appendLoading();
  scrollToBottom();

  try {
    const body = {
      message: query,
      history: chatHistory,
      n: parseInt(nSelect.value, 10),
    };

    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(`서버 오류 ${res.status}: ${err}`);
    }

    const data = await res.json();

    // 히스토리 업데이트
    if (data.history) chatHistory = data.history;

    // 로딩 제거
    removeLoading(loadingId);

    // 응답 카드 추가
    appendAIMessage(data);

  } catch (err) {
    removeLoading(loadingId);
    appendErrorMessage(err.message);
  } finally {
    input.disabled = false;
    btn.disabled   = false;
    input.focus();
    scrollToBottom();
  }
}

// ── 사용자 메시지 ──────────────────────────────────────────────────────────
function appendUserMessage(text) {
  const msgs = document.getElementById('messages');
  const div  = document.createElement('div');
  div.className = 'msg-user';
  div.innerHTML = `
    <div class="bubble">${escHtml(text)}</div>
    <div class="user-avatar">👤</div>
  `;
  msgs.appendChild(div);
  scrollToBottom();
}

// ── 로딩 ───────────────────────────────────────────────────────────────────
function appendLoading() {
  const msgs = document.getElementById('messages');
  const id   = 'loading-' + Date.now();
  const div  = document.createElement('div');
  div.id        = id;
  div.className = 'loading-card';
  div.innerHTML = `
    <div class="ai-avatar">🔬</div>
    <div class="loading-bubble">
      <div class="spinner"></div>
      <span class="loading-text">검색 중...</span>
    </div>
  `;
  msgs.appendChild(div);
  return id;
}

function removeLoading(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ── AI 응답 카드 ────────────────────────────────────────────────────────────
function appendAIMessage(data) {
  const msgs = document.getElementById('messages');
  const div  = document.createElement('div');
  div.className = 'msg-ai';

  const isGeneration = data.mode === 'generation';
  const icon = isGeneration ? '🤖' : '🔬';
  const title = isGeneration ? 'MEEP-KB (LLM 답변)' : 'MEEP-KB';

  // 의도 뱃지
  const intentBadge = buildIntentBadge(data.intent);

  // 검색 방식 pills
  const methodPills = (data.methods_used || []).map(m =>
    `<span class="method-pill mp-${m}">${methodIcon(m)} ${m}</span>`
  ).join('');

  // 본문: Generation or DB 직출력
  let bodyHtml = '';

  if (isGeneration) {
    // ① Hallucination 경고
    bodyHtml += `
      <div class="hallucination-warning">
        <strong>⚠️ AI 생성 답변 — 환각(Hallucination) 주의</strong>
        이 답변은 Claude AI가 생성했습니다. DB에 없는 내용이 포함될 수 있으며,
        부정확할 수 있습니다. 중요한 내용은 공식 MEEP 문서 또는 GitHub Issues에서
        직접 확인하세요.
        <a href="https://meep.readthedocs.io" target="_blank">공식 문서 →</a>
      </div>`;

    // ② LLM 답변 (마크다운 렌더링)
    const answerHtml = marked.parse(data.answer || '');
    bodyHtml += `<div class="llm-answer">${answerHtml}</div>`;

    // ③ 참고 DB 자료
    if (data.results && data.results.length > 0) {
      const srcItems = data.results.map(r => {
        const typeIcon = typeIconChar(r.type);
        const link = r.url
          ? `<a href="${escHtml(r.url)}" target="_blank">${escHtml(r.title)}</a>`
          : escHtml(r.title);
        return `<li>${typeIcon} ${link}</li>`;
      }).join('');
      bodyHtml += `
        <div class="llm-sources">
          <div class="llm-sources-title">📚 참고 DB 자료 (${data.results.length}건)</div>
          <ul>${srcItems}</ul>
        </div>`;
    }
  } else {
    // DB 직출력
    if (data.results && data.results.length > 0) {
      const cardsHtml = data.results.map((r, i) => buildResultCard(r, i + 1)).join('');
      bodyHtml += `<div class="db-results">${cardsHtml}</div>`;
    } else {
      bodyHtml += `
        <div style="padding:16px;color:var(--text-dim);font-size:13px;">
          ❌ 관련 자료를 찾지 못했습니다. 더 구체적인 키워드로 검색해보세요.
        </div>`;
    }
  }

  // elapsed
  bodyHtml += `<div class="elapsed-row">⏱ ${data.elapsed_ms}ms · ${modeLabel(data.mode)}</div>`;

  div.innerHTML = `
    <div class="ai-avatar">${icon}</div>
    <div class="ai-card">
      <div class="ai-card-header">
        <span class="ai-card-title">${title}</span>
        <div class="ai-card-meta">${intentBadge}</div>
      </div>
      <div class="methods-row">
        <span>검색 방식:</span>
        ${methodPills}
      </div>
      ${bodyHtml}
    </div>
  `;

  msgs.appendChild(div);

  // highlight.js 코드 하이라이팅
  div.querySelectorAll('pre code').forEach(block => {
    hljs.highlightElement(block);
  });
}

// ── 결과 카드 하나 ─────────────────────────────────────────────────────────
function buildResultCard(r, rank) {
  const typeIcon = typeIconChar(r.type);
  const score    = r.score || 0;
  const pct      = Math.round(score * 100);
  const barClass = score >= 0.65 ? 'score-high' : score >= 0.50 ? 'score-mid' : 'score-low';

  let bodyLines = '';
  if (r.type === 'ERROR') {
    if (r.cause)    bodyLines += `<div class="result-field"><label>원인:</label><span>${escHtml(r.cause.slice(0, 200))}</span></div>`;
    if (r.solution) bodyLines += `<div class="result-field"><label>✅ 해결:</label><span>${escHtml(r.solution.slice(0, 250))}</span></div>`;
  } else if (r.type === 'EXAMPLE') {
    if (r.code) {
      const snippet = r.code.slice(0, 300).trim();
      bodyLines += `<pre><code class="language-python">${escHtml(snippet)}</code></pre>`;
    }
  } else if (r.type === 'DOC') {
    if (r.cause) bodyLines += `<div class="result-field"><span>${escHtml(r.cause.slice(0, 200))}</span></div>`;
  }

  const link = r.url
    ? `<a class="result-link" href="${escHtml(r.url)}" target="_blank">🔗 ${escHtml(r.url.slice(0, 80))}</a>`
    : '';

  return `
    <div class="result-card">
      <div class="result-header">
        <span class="result-rank">${rank}.</span>
        <span class="result-type-icon">${typeIcon}</span>
        <span class="result-title">${escHtml(r.title)}</span>
        <span class="result-score">${pct}%</span>
        <div class="score-bar-wrap">
          <div class="score-bar ${barClass}" style="width:${pct}%"></div>
        </div>
        <span style="font-size:11px;color:var(--text-mute)">${r.source}</span>
      </div>
      <div class="result-body">
        ${bodyLines}
        ${link}
      </div>
    </div>`;
}

// ── 에러 메시지 ────────────────────────────────────────────────────────────
function appendErrorMessage(msg) {
  const msgs = document.getElementById('messages');
  const div  = document.createElement('div');
  div.className = 'msg-ai';
  div.innerHTML = `
    <div class="ai-avatar">❌</div>
    <div class="ai-card">
      <div class="ai-card-header">
        <span class="ai-card-title" style="color:var(--red)">오류 발생</span>
      </div>
      <div style="padding:14px 16px;color:var(--red);font-size:13px;">${escHtml(msg)}</div>
    </div>`;
  msgs.appendChild(div);
}

// ── 유틸 함수들 ────────────────────────────────────────────────────────────
function buildIntentBadge(intent) {
  if (!intent) return '';
  const type = intent.type || 'unknown';
  const conf = Math.round((intent.confidence || 0) * 100);
  const cls  = {
    error_debug:  'intent-error',
    code_example: 'intent-example',
    concept_map:  'intent-concept',
    doc_lookup:   'intent-doc',
    unknown:      'intent-unknown',
  }[type] || 'intent-unknown';

  const icon = {
    error_debug:  '🔴',
    code_example: '🟢',
    concept_map:  '🕸️',
    doc_lookup:   '📄',
    unknown:      '❓',
  }[type] || '❓';

  const label = {
    error_debug:  '에러 디버깅',
    code_example: '코드 예제',
    concept_map:  '개념 탐색',
    doc_lookup:   '문서 참조',
    unknown:      '전방위',
  }[type] || type;

  return `<span class="intent-badge ${cls}">${icon} ${label} ${conf}%</span>`;
}

function typeIconChar(type) {
  return { ERROR: '🔴', EXAMPLE: '🟢', DOC: '📄' }[type] || '•';
}

function methodIcon(m) {
  return { keyword: '🔑', vector: '🔍', graph: '🕸️' }[m] || '';
}

function modeLabel(mode) {
  return { db_only: 'DB 직출력', generation: 'LLM 생성', hybrid: '하이브리드' }[mode] || mode;
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function scrollToBottom() {
  const msgs = document.getElementById('messages');
  requestAnimationFrame(() => {
    msgs.scrollTop = msgs.scrollHeight;
  });
}
