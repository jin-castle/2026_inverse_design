/* ── MEEP-KB App ───────────────────────────────────────────────────────── */

const API_BASE = window.location.origin === 'null' || window.location.origin === '' 
  ? 'http://localhost:8765' 
  : window.location.origin;
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
    appendAIMessage(data, query);

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
function appendAIMessage(data, query_text = '') {
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

  // 코드 하이라이팅 + 복사버튼 + 클릭시 전체선택
  div.querySelectorAll('pre code').forEach(block => {
    hljs.highlightElement(block);
  });
  div.querySelectorAll('pre').forEach(pre => {
    pre.style.position = 'relative';
    pre.title = '클릭: 전체 선택 | 복사 버튼: 클립보드 복사';
    // 클릭시 코드 전체 선택
    pre.addEventListener('click', (e) => {
      if (e.target.tagName === 'BUTTON') return;
      const range = document.createRange();
      range.selectNodeContents(pre.querySelector('code') || pre);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    });
    // 복사 버튼
    const copyBtn = document.createElement('button');
    copyBtn.textContent = '복사';
    copyBtn.style.cssText = 'position:absolute;top:6px;right:8px;padding:2px 8px;font-size:11px;background:#30363d;color:#8b949e;border:1px solid #444;border-radius:4px;cursor:pointer;z-index:10;opacity:0;transition:opacity 0.15s;';
    pre.addEventListener('mouseenter', () => copyBtn.style.opacity = '1');
    pre.addEventListener('mouseleave', () => copyBtn.style.opacity = '0');
    copyBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const code = pre.querySelector('code');
      navigator.clipboard.writeText(code ? code.innerText : pre.innerText).then(() => {
        copyBtn.textContent = '✓';
        copyBtn.style.color = '#3fb950';
        setTimeout(() => { copyBtn.textContent = '복사'; copyBtn.style.color = '#8b949e'; }, 1500);
      });
    });
    pre.appendChild(copyBtn);
  });

  // 피드백 UI 추가
  if (data.results && data.results.length > 0) {
    appendFeedbackUI(div, data, query_text);
  }

  scrollToBottom();
}

// ── 피드백 UI ──────────────────────────────────────────────────────────────
function appendFeedbackUI(parentDiv, data, query) {
  const answerId = 'ans-' + Date.now();
  const results  = data.results || [];

  const section = document.createElement('div');
  section.className = 'feedback-section';
  section.dataset.answerId = answerId;

  // 버튼 목록 (자료별 + 해결 안됨)
  const btnHtml = results.slice(0, 5).map((r, i) => `
    <button class="feedback-btn" data-idx="${i+1}"
      data-title="${escHtml(r.title || '')}"
      data-url="${escHtml(r.url || '')}">
      ${i+1}번 자료
    </button>
  `).join('');

  section.innerHTML = `
    <div class="feedback-label">💡 어떤 방법이 도움이 됐나요?</div>
    <div class="feedback-btns">
      ${btnHtml}
      <button class="feedback-btn feedback-btn-none" data-idx="0"
        data-title="" data-url="">
        해결 안됨
      </button>
    </div>
    <div class="feedback-thanks" style="display:none;"></div>
  `;

  // 버튼 클릭 이벤트
  section.querySelectorAll('.feedback-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const idx   = parseInt(btn.dataset.idx);
      const title = btn.dataset.title;
      const url   = btn.dataset.url;

      // UI 즉시 반응
      section.querySelectorAll('.feedback-btn').forEach(b => b.disabled = true);
      btn.classList.add('feedback-btn-selected');

      const thanks = section.querySelector('.feedback-thanks');
      thanks.style.display = 'block';
      thanks.textContent   = idx === 0
        ? '😅 피드백 감사합니다. 검색 개선에 활용하겠습니다.'
        : `✅ ${idx}번 자료 피드백 감사합니다! 점수가 올라갑니다 🚀`;

      // 서버에 전송
      try {
        await fetch(`${API_BASE}/api/feedback`, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query,
            answer_id:    answerId,
            result_index: idx,
            result_title: title,
            result_url:   url,
            answer_text:  (data.answer || '').slice(0, 2000),
          }),
        });
      } catch (e) {
        console.warn('피드백 전송 실패:', e);
      }
    });
  });

  // AI 카드 내부 맨 아래에 추가
  const card = parentDiv.querySelector('.ai-card');
  if (card) card.appendChild(section);
  else parentDiv.appendChild(section);
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
    if (r.solution) bodyHtml += `<div class="result-field"><span class="result-field-label">해결</span><span class="result-field-val">${escHtml(r.solution.slice(0, 260))}</span></div>`;
  } else if (r.type === 'EXAMPLE') {
    if (r.code) {
      const snippet = escHtml(r.code.slice(0, 300).trim());
      bodyHtml += `<pre><code class="language-python">${snippet}</code></pre>`;
    }
  } else if (r.type === 'DOC') {
    if (r.cause) bodyHtml += `<div class="result-field"><span class="result-field-val">${escHtml(r.cause.slice(0, 220))}</span></div>`;
  } else if (r.type === 'PATTERN') {
    if (r.cause) bodyHtml += `<div class="result-field"><span class="result-field-label">설명</span><span class="result-field-val">${escHtml(r.cause.slice(0, 300))}</span></div>`;
    if (r.category) bodyHtml += `<div class="result-field"><span class="result-field-label">용도</span><span class="result-field-val">${escHtml(r.category.slice(0, 200))}</span></div>`;
    if (r.code) {
      const snippet = escHtml(r.code.slice(0, 400).trim());
      bodyHtml += `<pre><code class="language-python">${snippet}</code></pre>`;
    }
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
  return { ERROR: '🔴', EXAMPLE: '🟢', DOC: '📄', PATTERN: '🔷' }[type] || '•';
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

/* ── 탭 전환 ────────────────────────────────────────────────────────────── */
function switchTab(tab) {
  document.getElementById('panel-chat').style.display     = tab === 'chat'     ? '' : 'none';
  document.getElementById('panel-diagnose').style.display = tab === 'diagnose' ? '' : 'none';
  document.getElementById('panel-dict').style.display     = tab === 'dict'     ? '' : 'none';
  document.getElementById('tab-chat').classList.toggle('active',     tab === 'chat');
  document.getElementById('tab-diagnose').classList.toggle('active', tab === 'diagnose');
  document.getElementById('tab-dict').classList.toggle('active',     tab === 'dict');
  // Dictionary 탭 최초 클릭 시 iframe 로드 (lazy loading)
  if (tab === 'dict') {
    const frame = document.getElementById('dict-frame');
    if (frame.src === 'about:blank' || frame.src === '') {
      frame.src = '/dict';
    }
  }
}

/* ── 코드 진단 ──────────────────────────────────────────────────────────── */
const DIAG_EXAMPLES = {
  adjoint: {
    code: `import meep as mp
import meep.adjoint as mpa
import autograd.numpy as npa

opt = mpa.OptimizationProblem(
    simulation=sim,
    objective_functions=[J],
    objective_arguments=[monitor],
    design_regions=[design_region],
)
x0 = np.ones((Nx, Ny)) * 0.5
opt.update_design([x0])
f, dJ_deps = opt(x0, need_gradient=True)`,
    error: `Traceback (most recent call last):
  File "adjoint_test.py", line 31, in <module>
    f, dJ_deps = opt(x0, need_gradient=True)
  File "/opt/conda/lib/python3.10/site-packages/meep/adjoint/optimization_problem.py", line 552, in __call__
    self.reset_meep()
RuntimeError: changed_materials: cannot add new materials to a simulation after it has been run`
  },
  diverge: {
    code: `import meep as mp

cell = mp.Vector3(10, 10, 0)
pml_layers = [mp.PML(1.0)]
sources = [mp.Source(src=mp.GaussianSource(frequency=1.0, fwidth=0.5),
                     component=mp.Ez, center=mp.Vector3(-3, 0, 0))]
sim = mp.Simulation(cell_size=cell, boundary_layers=pml_layers,
                    sources=sources, resolution=20)
sim.run(until=500)`,
    error: `meep: field decay is NaN; the simulation is probably diverging.
If this is unexpected, decreasing the time step (e.g. by increasing the resolution) may help.
Simulation diverged at t=42.5 after 850 time steps.`
  },
  eigenmode: {
    code: `import meep as mp

sources = [mp.EigenModeSource(
    src=mp.GaussianSource(1/1.55, fwidth=0.2),
    center=mp.Vector3(-3, 0),
    size=mp.Vector3(0, 2),
    eig_band=1,
    eig_parity=mp.EVEN_Y+mp.ODD_Z,
    eig_kpoint=mp.Vector3(1, 0, 0)
)]
sim = mp.Simulation(cell_size=mp.Vector3(10, 4, 0),
                    geometry=[...], sources=sources, resolution=30)
sim.run(until=100)`,
    error: `meep: The eigenmode solver could not find a mode.
AttributeError: 'NoneType' object has no attribute 'group_velocity'
  at EigenModeSource initialization`
  }
};

function fillDiagExample(key) {
  const ex = DIAG_EXAMPLES[key];
  if (!ex) return;
  document.getElementById('diag-code').value  = ex.code;
  document.getElementById('diag-error').value = ex.error;
  document.getElementById('diag-result').style.display = 'none';
}

function clearDiagnose() {
  document.getElementById('diag-code').value  = '';
  document.getElementById('diag-error').value = '';
  document.getElementById('diag-result').style.display = 'none';
}

async function runDiagnose() {
  const code  = document.getElementById('diag-code').value.trim();
  const error = document.getElementById('diag-error').value.trim();
  if (!code && !error) {
    alert('코드 또는 에러 메시지를 입력하세요.');
    return;
  }

  const btn = document.getElementById('diag-submit');
  btn.disabled = true;
  btn.textContent = '🔍 분석 중...';

  const resultDiv = document.getElementById('diag-result');
  resultDiv.style.display = 'block';
  resultDiv.innerHTML = `<div class="diag-loading">⏳ meep-kb DB 검색 중...</div>`;

  try {
    const res = await fetch(`${API_BASE}/api/diagnose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, error, n: 5 }),
    });
    const data = await res.json();
    renderDiagnoseResult(data);
  } catch (e) {
    resultDiv.innerHTML = `<div class="diag-error-msg">❌ 요청 실패: ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '🔍 진단 시작';
  }
}

/* ── Diagnose error type → CSS class mapping ─────────────────────────── */
function diagErrorTypeClass(typeStr) {
  const t = (typeStr || '').toLowerCase();
  if (t.includes('runtime'))   return 'type-runtime';
  if (t.includes('attribute')) return 'type-attribute';
  if (t.includes('nan') || t.includes('diverg')) return 'type-diverge';
  if (t.includes('eigen'))     return 'type-eigenmode';
  if (t.includes('mpi'))       return 'type-mpi';
  if (t.includes('adjoint'))   return 'type-adjoint';
  return 'type-general';
}

function diagOriginBadge(source) {
  const s = (source || '').toLowerCase();
  if (s.includes('vector') || s.includes('sqlite') || s === 'kb') {
    return `<span class="diag-origin-badge origin-db">DB검증됨</span>`;
  }
  if (s.includes('github')) {
    return `<span class="diag-origin-badge origin-github">GitHub</span>`;
  }
  if (s.includes('marl')) {
    return `<span class="diag-origin-badge origin-marl">MARL자동수정</span>`;
  }
  if (s.includes('llm') || s.includes('generation')) {
    return `<span class="diag-origin-badge origin-llm">LLM생성</span>`;
  }
  return `<span class="diag-origin-badge origin-db">KB</span>`;
}

function renderDiagnoseResult(data) {
  const resultDiv  = document.getElementById('diag-result');
  const info       = data.error_info || {};
  const suggestions= data.suggestions || [];
  const dbSuf      = data.db_sufficient;
  const topScore   = data.top_score || 0;

  // ── Mode badge ────────────────────────────────────────────────────────
  const modeBadge = dbSuf
    ? `<span class="diag-mode-badge diag-mode-db">DB 기반 · ${Math.round(topScore*100)}% 신뢰도</span>`
    : `<span class="diag-mode-badge diag-mode-llm">DB+LLM 혼합</span>`;

  // ── Detected error type badges ─────────────────────────────────────────
  const types = (info.detected_types || []).map(t => {
    const cls = diagErrorTypeClass(t.type || '');
    const label = t.type || '';
    return `<span class="diag-type-badge">${label}</span>`;
  }).join('');

  // ── Physics context ────────────────────────────────────────────────────
  let physHtml = '';
  const phys = data.physics_context || {};
  const physItems = [];
  if (phys.resolution)    physItems.push(`res=${phys.resolution}`);
  if (phys.cell_size)     physItems.push(`cell=${phys.cell_size}`);
  if (phys.pml_thickness) physItems.push(`PML=${phys.pml_thickness}`);
  if (phys.fcen)          physItems.push(`fcen=${phys.fcen}`);
  if (phys.epsilons)      physItems.push(`ε=[${phys.epsilons.join(',')}]`);
  if (phys.uses_adjoint)  physItems.push('adjoint');
  if (phys.uses_mpi)      physItems.push('MPI');
  if (physItems.length > 0) {
    physHtml = `<div class="diag-phys-ctx">
      <span class="diag-phys-label">PARAMS</span>
      ${physItems.map(p => `<span class="diag-phys-tag">${p}</span>`).join('')}
    </div>`;
  }

  // ── Suggestion cards ──────────────────────────────────────────────────
  let suggHtml = '';
  if (suggestions.length > 0) {
    suggestions.forEach((s, i) => {
      const pct      = Math.round((s.score || 0) * 100);
      const confCls  = pct >= 70 ? 'conf-high' : pct >= 45 ? 'conf-mid' : 'conf-low';
      const pctCls   = pct >= 70 ? 'pct-high'  : pct >= 45 ? 'pct-mid'  : 'pct-low';

      // Error type from title or detected types
      const rawType  = (info.detected_types && info.detected_types[0])
        ? info.detected_types[0].type : '';
      const errClass = diagErrorTypeClass(rawType || s.title || '');
      const errLabel = rawType || 'ERROR';

      const originBadge = diagOriginBadge(s.source || '');

      suggHtml += `
        <div class="diag-card">

          <!-- Header: badges + title -->
          <div class="diag-card-header">
            <div class="diag-card-badges">
              <span class="diag-error-type ${errClass}">${escHtml(errLabel)}</span>
              ${originBadge}
            </div>
            <span class="diag-card-num">#${i+1}</span>
            <span class="diag-card-title" title="${escHtml(s.title || '관련 항목')}">${escHtml(s.title || '관련 항목')}</span>
          </div>

          <!-- Confidence meter -->
          <div class="diag-confidence">
            <span class="diag-confidence-label">CONF</span>
            <div class="diag-confidence-track">
              <div class="diag-confidence-fill ${confCls}" style="width:${Math.min(pct,100)}%"></div>
            </div>
            <span class="diag-confidence-pct ${pctCls}">${pct}%</span>
          </div>

          ${s.cause ? `
          <!-- 원인 -->
          <div class="diag-section diag-section-cause">
            <div class="diag-section-label">◈ 원인</div>
            <div class="diag-section-body">${escHtml(s.cause)}</div>
          </div>` : ''}

          ${s.solution ? `
          <!-- 해결방법 -->
          <div class="diag-section diag-section-solution">
            <div class="diag-section-label">◉ 해결방법</div>
            <div class="diag-section-body">${escHtml(s.solution)}</div>
          </div>` : ''}

          ${s.code ? `
          <!-- 수정 코드 -->
          <div class="diag-section diag-section-code">
            <div class="diag-section-label">⟨/⟩ 수정 코드</div>
            <pre class="diag-code-block"><code class="language-python">${escHtml(s.code)}</code></pre>
          </div>` : ''}

          ${s.url ? `
          <!-- 참고 -->
          <div class="diag-section diag-section-ref">
            <div class="diag-section-label">↗ 참고 문서</div>
            <a class="diag-url" href="${escHtml(s.url)}" target="_blank">${escHtml(s.url)}</a>
          </div>` : ''}

        </div>`;
    });
  } else {
    suggHtml = `<div class="diag-no-result">DB에서 관련 항목을 찾지 못했습니다.</div>`;
  }

  // ── LLM section ────────────────────────────────────────────────────────
  let llmHtml = '';
  if (data.llm_result && data.llm_result.available && data.llm_result.answer) {
    llmHtml = `
      <div class="diag-llm-section">
        <div class="diag-llm-header">LLM 도메인 분석 — DB 보조 + 물리 추론</div>
        <div class="diag-llm-body">${marked.parse(data.llm_result.answer)}</div>
      </div>`;
  }

  resultDiv.innerHTML = `
    <div class="diag-result-header">
      ${modeBadge}
      ${physHtml}
      ${types ? `<div class="diag-detected-types">${types}</div>` : ''}
      ${info.last_error_line ? `<div class="diag-last-err">핵심 에러: <code>${escHtml(info.last_error_line)}</code></div>` : ''}
    </div>
    <div class="diag-suggestions">${suggHtml}</div>
    ${llmHtml}`;

  // ── Syntax highlighting + copy buttons ────────────────────────────────
  resultDiv.querySelectorAll('pre code').forEach(el => {
    if (typeof hljs !== 'undefined') hljs.highlightElement(el);
  });
  resultDiv.querySelectorAll('pre').forEach(pre => {
    pre.style.position = 'relative';
    pre.addEventListener('click', (e) => {
      if (e.target.tagName === 'BUTTON') return;
      const range = document.createRange();
      range.selectNodeContents(pre.querySelector('code') || pre);
      const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
    });
    const cb = document.createElement('button');
    cb.textContent = 'COPY';
    cb.style.cssText = 'position:absolute;top:7px;right:8px;padding:2px 8px;font-size:9px;font-family:var(--font-mono,monospace);letter-spacing:0.08em;background:#0d1428;color:#607098;border:1px solid #1a2a50;border-radius:3px;cursor:pointer;z-index:10;opacity:0;transition:opacity 0.15s;text-transform:uppercase;';
    pre.addEventListener('mouseenter', () => cb.style.opacity = '1');
    pre.addEventListener('mouseleave', () => cb.style.opacity = '0');
    cb.addEventListener('click', (e) => {
      e.stopPropagation();
      const code = pre.querySelector('code');
      navigator.clipboard.writeText(code ? code.innerText : pre.innerText).then(() => {
        cb.textContent = 'OK';
        cb.style.color = '#00E87A';
        setTimeout(() => { cb.textContent = 'COPY'; cb.style.color = '#607098'; }, 1500);
      });
    });
    pre.appendChild(cb);
  });
}

function escHtml(str) {
  return (str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
