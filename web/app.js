/* ── MEEP-KB App ───────────────────────────────────────────────────────── */

const API_BASE = 'http://localhost:8765';
let chatHistory = [];
let isLoading = false;

// ── marked.js 설정 ──────────────────────────────────────────────────────────
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
  setInterval(loadStatus, 30_000);

  const input = document.getElementById('query-input');

  // Enter 전송 / Shift+Enter 줄바꿈
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendQuery();
    }
  });

  // 자동 높이 조정
  input.addEventListener('input', autoResize);

  // 예시 버튼 (사이드바)
  document.querySelectorAll('.example-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.dataset.query;
      if (q) { setQueryAndSend(q); closeSidebar(); }
    });
  });

  // 예시 버튼 (환영 카드)
  document.querySelectorAll('.welcome-example-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.dataset.query;
      if (q) setQueryAndSend(q);
    });
  });
});

function autoResize() {
  const ta = document.getElementById('query-input');
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
}

// ── 사이드바 토글 ───────────────────────────────────────────────────────────
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  const ov = document.getElementById('sidebar-overlay');
  sb.classList.toggle('open');
  ov.classList.toggle('active');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('active');
}

// ── 서버 상태 로드 ──────────────────────────────────────────────────────────
async function loadStatus() {
  const badge = document.getElementById('server-status');
  const text  = document.getElementById('status-text');
  try {
    const res  = await fetch(`${API_BASE}/api/status`);
    if (!res.ok) throw new Error('오류');
    const data = await res.json();

    setStatVal('stat-errors',   data.db_errors);
    setStatVal('stat-examples', data.db_examples);
    setStatVal('stat-docs',     data.db_docs);
    setStatVal('stat-nodes',    data.graph_nodes);

    badge.className = 'server-status online';
    text.textContent = data.server_ready ? '서버 준비 완료' : '서버 초기화 중...';
  } catch {
    badge.className = 'server-status offline';
    text.textContent = '서버 연결 실패';
    ['stat-errors','stat-examples','stat-docs','stat-nodes']
      .forEach(id => { const el = document.getElementById(id); if (el) el.textContent = '—'; });
  }
}

function setStatVal(id, n) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = (typeof n === 'number' && n >= 0)
    ? n.toLocaleString('ko-KR') + '건'
    : '—';
}

// ── 예시 쿼리 설정 + 즉시 전송 ────────────────────────────────────────────
function setQueryAndSend(q) {
  const input = document.getElementById('query-input');
  input.value = q;
  autoResize();
  sendQuery();
}

// ── 대화 초기화 ────────────────────────────────────────────────────────────
function resetChat() {
  chatHistory = [];
  const msgs = document.getElementById('messages');
  msgs.innerHTML = '';

  // 환영 카드 재생성
  const wc = document.createElement('div');
  wc.id = 'welcome-card';
  wc.className = 'welcome-card';
  wc.innerHTML = `
    <div class="welcome-icon">🔬</div>
    <h2 class="welcome-title">MEEP 지식베이스에 질문하세요</h2>
    <p class="welcome-desc">에러 디버깅, 코드 예제, 개념 설명 등<br>한국어·영어 모두 가능합니다.</p>
    <div class="welcome-tags">
      <span class="welcome-tag tag-error">🔴 에러 디버깅</span>
      <span class="welcome-tag tag-example">🟢 코드 예제</span>
      <span class="welcome-tag tag-concept">🕸️ 개념 탐색</span>
      <span class="welcome-tag tag-doc">📄 문서 검색</span>
    </div>
    <div class="welcome-examples">
      <button class="welcome-example-btn" data-query="adjoint 돌리다가 죽었어">adjoint 돌리다가 죽었어</button>
      <button class="welcome-example-btn" data-query="EigenModeSource 사용법">EigenModeSource 사용법</button>
      <button class="welcome-example-btn" data-query="PML이 뭐야">PML이 뭐야</button>
      <button class="welcome-example-btn" data-query="시뮬레이션이 발산해">시뮬레이션이 발산해</button>
    </div>`;

  // 환영 카드 버튼 이벤트 재등록
  wc.querySelectorAll('.welcome-example-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const q = btn.dataset.query;
      if (q) setQueryAndSend(q);
    });
  });

  msgs.appendChild(wc);
  closeSidebar();
}

// ── 메시지 전송 ────────────────────────────────────────────────────────────
async function sendQuery() {
  if (isLoading) return;

  const input  = document.getElementById('query-input');
  const nSel   = document.getElementById('n-select');
  const sendBtn = document.getElementById('send-btn');
  const query  = input.value.trim();
  if (!query) return;

  // 환영 카드 제거
  const wc = document.getElementById('welcome-card');
  if (wc) wc.remove();

  // 사용자 메시지 추가
  appendUserMessage(query);

  // 초기화
  input.value = '';
  input.style.height = 'auto';
  input.disabled = true;
  sendBtn.disabled = true;
  isLoading = true;

  // 로딩 카드
  const loadingId = appendLoading();
  scrollToBottom();

  try {
    const body = {
      message: query,
      history: chatHistory,
      n: parseInt(nSel.value, 10),
    };

    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`서버 오류 ${res.status}: ${errText}`);
    }

    const data = await res.json();
    if (data.history) chatHistory = data.history;

    removeLoading(loadingId);
    appendAIMessage(data);

  } catch (err) {
    removeLoading(loadingId);
    appendErrorMessage(err.message);
  } finally {
    input.disabled  = false;
    sendBtn.disabled = false;
    isLoading = false;
    input.focus();
    scrollToBottom();
  }
}

// ── 사용자 메시지 ──────────────────────────────────────────────────────────
function appendUserMessage(text) {
  const msgs = document.getElementById('messages');
  const div  = document.createElement('div');
  div.className = 'msg-user msg-animate';
  div.innerHTML = `<div class="msg-user-bubble">${escHtml(text)}</div>`;
  msgs.appendChild(div);
  scrollToBottom();
}

// ── 로딩 카드 ──────────────────────────────────────────────────────────────
const LOADING_STEPS = [
  { emoji: '🧠', text: '의도 분석 중...' },
  { emoji: '🕸️', text: '지식 그래프 탐색 중...' },
  { emoji: '🔍', text: '벡터 검색 중...' },
  { emoji: '🔑', text: '키워드 검색 중...' },
  { emoji: '📊', text: '결과 통합 중...' },
];

function appendLoading() {
  const msgs = document.getElementById('messages');
  const id   = 'loading-' + Date.now();
  const div  = document.createElement('div');
  div.id = id;
  div.className = 'loading-card msg-animate';

  div.innerHTML = `
    <div class="loading-inner">
      <div class="loading-header">
        <div class="spinner"></div>
        <span class="loading-label">🔬 MEEP-KB</span>
        <div class="loading-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
      <div class="loading-body" id="${id}-body">
        <div class="loading-step active">
          <span>⏳</span>
          <span id="${id}-step">의도 분석 중...</span>
        </div>
      </div>
    </div>`;

  msgs.appendChild(div);

  // 단계별 메시지 순환
  let stepIdx = 0;
  const stepEl = div.querySelector(`#${id}-step`);
  const interval = setInterval(() => {
    stepIdx = (stepIdx + 1) % LOADING_STEPS.length;
    const s = LOADING_STEPS[stepIdx];
    if (stepEl) stepEl.textContent = `${s.emoji} ${s.text}`;
  }, 1800);

  div._interval = interval;
  return id;
}

function removeLoading(id) {
  const el = document.getElementById(id);
  if (!el) return;
  if (el._interval) clearInterval(el._interval);
  el.remove();
}

// ── AI 응답 카드 ────────────────────────────────────────────────────────────
function appendAIMessage(data) {
  const msgs = document.getElementById('messages');
  const div  = document.createElement('div');
  div.className = 'msg-ai msg-animate';

  const isGen = data.mode === 'generation';

  // 헤더
  const modeBadge   = buildModeBadge(data.mode);
  const intentBadge = buildIntentBadge(data.intent);
  const elapsedMs   = data.elapsed_ms != null ? data.elapsed_ms : '—';
  const elapsed     = typeof elapsedMs === 'number'
    ? (elapsedMs >= 1000 ? (elapsedMs/1000).toFixed(1) + '초' : elapsedMs + 'ms')
    : elapsedMs;

  // 검색 방식 pills
  const methodPills = (data.methods_used || []).map(m =>
    `<span class="method-pill mp-${m}">${methodIcon(m)} ${m}</span>`
  ).join('');
  const methodsRow = methodPills
    ? `<div class="methods-row"><span class="methods-label">검색:</span>${methodPills}</div>`
    : '';

  // 본문
  let bodyHtml = '';

  if (isGen) {
    // 환각 경고
    bodyHtml += `
      <div class="hallucination-warning">
        <div class="hallucination-warning-title">⚠️ AI 생성 답변 — 환각 주의</div>
        <p>Claude AI 생성. 부정확한 내용이 포함될 수 있습니다.</p>
        <p>공식 문서에서 반드시 확인하세요.
          <a href="https://meep.readthedocs.io" target="_blank">공식 문서 →</a>
        </p>
      </div>`;

    // LLM 답변
    const answerHtml = marked.parse(data.answer || '');
    bodyHtml += `<div class="llm-answer">${answerHtml}</div>`;

    // 참고 자료
    if (data.results && data.results.length > 0) {
      const items = data.results.map(r => {
        const icon = typeIconChar(r.type);
        const linkEl = r.url
          ? `<a href="${escHtml(r.url)}" target="_blank">${escHtml(r.title)}</a>`
          : escHtml(r.title);
        return `<li>${icon} ${linkEl}</li>`;
      }).join('');
      bodyHtml += `
        <div class="llm-sources">
          <div class="llm-sources-title">📚 참고 DB 자료 · ${data.results.length}건</div>
          <ul class="llm-sources-list">${items}</ul>
        </div>`;
    }

  } else {
    // DB 직출력
    if (data.results && data.results.length > 0) {
      const cards = data.results.map((r, i) => buildResultCard(r, i + 1)).join('');
      bodyHtml += `<div class="db-results">${cards}</div>`;
    } else {
      bodyHtml += `
        <div class="no-results">
          <div class="no-results-icon">🔍</div>
          <div>관련 자료를 찾지 못했습니다.</div>
          <div style="font-size:12px;color:var(--text-faint);margin-top:6px;">
            더 구체적인 키워드로 검색해보세요.
          </div>
        </div>`;
    }
  }

  // 카드 푸터
  bodyHtml += `
    <div class="card-footer">
      <span>⏱ ${elapsed}</span>
      <span>${modeLabelStr(data.mode)}</span>
    </div>`;

  div.innerHTML = `
    <div class="ai-card">
      <div class="ai-card-header">
        <div class="ai-card-title-row">
          <span class="ai-card-icon">${isGen ? '🤖' : '🔬'}</span>
          <span class="ai-card-label">${isGen ? 'AI 생성 답변' : 'MEEP-KB'}</span>
        </div>
        <div class="ai-card-meta-row">
          ${intentBadge}
          ${modeBadge}
          <span class="elapsed-badge">⏱ ${elapsed}</span>
        </div>
      </div>
      ${methodsRow}
      ${bodyHtml}
    </div>`;

  msgs.appendChild(div);

  // 코드 하이라이팅
  div.querySelectorAll('pre code').forEach(block => {
    hljs.highlightElement(block);
  });

  scrollToBottom();
}

// ── 결과 카드 ──────────────────────────────────────────────────────────────
function buildResultCard(r, rank) {
  const typeIcon = typeIconChar(r.type);
  const score    = r.score || 0;
  const pct      = Math.round(score * 100);
  const barCls   = score >= 0.65 ? 'score-high' : score >= 0.50 ? 'score-mid' : 'score-low';
  const srcLabel = r.source ? `<span class="result-source">${escHtml(r.source)}</span>` : '';

  let bodyHtml = '';
  if (r.type === 'ERROR') {
    if (r.cause)    bodyHtml += `<div class="result-field"><span class="result-field-label">원인</span><span class="result-field-val">${escHtml(r.cause.slice(0, 220))}</span></div>`;
    if (r.solution) bodyHtml += `<div class="result-field"><span class="result-field-label">✅ 해결</span><span class="result-field-val">${escHtml(r.solution.slice(0, 260))}</span></div>`;
  } else if (r.type === 'EXAMPLE') {
    if (r.code) {
      const snippet = escHtml(r.code.slice(0, 300).trim());
      bodyHtml += `<pre><code class="language-python">${snippet}</code></pre>`;
    }
  } else if (r.type === 'DOC') {
    if (r.cause) bodyHtml += `<div class="result-field"><span class="result-field-val">${escHtml(r.cause.slice(0, 220))}</span></div>`;
  }

  const link = r.url
    ? `<a class="result-link" href="${escHtml(r.url)}" target="_blank">🔗 ${escHtml(r.url.slice(0, 80))}</a>`
    : '';

  return `
    <div class="result-card">
      <div class="result-header">
        <span class="result-rank">${rank}.</span>
        <span class="result-type-icon">${typeIcon}</span>
        <span class="result-title" title="${escHtml(r.title)}">${escHtml(r.title)}</span>
        <div class="result-score-group">
          <span class="result-score-pct">${pct}%</span>
          <div class="score-bar-track">
            <div class="score-bar ${barCls}" style="width:${Math.min(pct,100)}%"></div>
          </div>
          ${srcLabel}
        </div>
      </div>
      <div class="result-body">
        ${bodyHtml}
        ${link}
      </div>
    </div>`;
}

// ── 에러 카드 ──────────────────────────────────────────────────────────────
function appendErrorMessage(msg) {
  const msgs = document.getElementById('messages');
  const div  = document.createElement('div');
  div.className = 'msg-ai msg-animate';
  div.innerHTML = `
    <div class="error-card">
      <div class="error-card-title">❌ 오류 발생</div>
      <div style="font-size:13px;">${escHtml(msg)}</div>
    </div>`;
  msgs.appendChild(div);
  scrollToBottom();
}

// ── 뱃지 빌더 ──────────────────────────────────────────────────────────────
function buildModeBadge(mode) {
  const labels = {
    db_only:    '✅ DB 직출력',
    generation: '🤖 AI 생성',
    hybrid:     '⚡ 하이브리드',
  };
  const label = labels[mode] || mode || '';
  if (!label) return '';
  return `<span class="mode-badge mode-${mode || 'unknown'}">${label}</span>`;
}

function buildIntentBadge(intent) {
  if (!intent) return '';
  const type = intent.type || 'unknown';
  const conf = Math.round((intent.confidence || 0) * 100);

  const clsMap = {
    error_debug:  'intent-error',
    code_example: 'intent-example',
    concept_map:  'intent-concept',
    doc_lookup:   'intent-doc',
    unknown:      'intent-unknown',
  };
  const iconMap = {
    error_debug:  '🔴',
    code_example: '🟢',
    concept_map:  '🕸️',
    doc_lookup:   '📄',
    unknown:      '❓',
  };
  const labelMap = {
    error_debug:  '에러 디버깅',
    code_example: '코드 예제',
    concept_map:  '개념 탐색',
    doc_lookup:   '문서 검색',
    unknown:      '전방위',
  };

  const cls   = clsMap[type]   || 'intent-unknown';
  const icon  = iconMap[type]  || '❓';
  const label = labelMap[type] || type;

  return `<span class="intent-badge ${cls}">${icon} ${label} ${conf}%</span>`;
}

// ── 유틸 ───────────────────────────────────────────────────────────────────
function typeIconChar(type) {
  return { ERROR: '🔴', EXAMPLE: '🟢', DOC: '📄' }[type] || '•';
}

function methodIcon(m) {
  return { keyword: '🔑', vector: '🔍', graph: '🕸️' }[m] || '';
}

function modeLabelStr(mode) {
  return { db_only: 'DB 직출력', generation: 'LLM 생성', hybrid: '하이브리드' }[mode] || (mode || '');
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function scrollToBottom() {
  const msgs = document.getElementById('messages');
  requestAnimationFrame(() => { msgs.scrollTop = msgs.scrollHeight; });
}
