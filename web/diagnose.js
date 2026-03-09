/* ── 탭 전환 ─────────────────────────────────────────────────────────────── */
function switchTab(tab) {
  document.getElementById('panel-chat').style.display     = tab === 'chat'     ? '' : 'none';
  document.getElementById('panel-diagnose').style.display = tab === 'diagnose' ? '' : 'none';
  document.getElementById('tab-chat').classList.toggle('active',     tab === 'chat');
  document.getElementById('tab-diagnose').classList.toggle('active', tab === 'diagnose');
}

/* ── 예시 데이터 ─────────────────────────────────────────────────────────── */
const DIAG_EXAMPLES = {
  adjoint: {
    code: `import meep as mp\nimport meep.adjoint as mpa\nimport autograd.numpy as npa\n\nopt = mpa.OptimizationProblem(\n    simulation=sim,\n    objective_functions=[J],\n    objective_arguments=[monitor],\n    design_regions=[design_region],\n)\nx0 = npa.ones((Nx, Ny)) * 0.5\nopt.update_design([x0])\nf, dJ_deps = opt(x0, need_gradient=True)`,
    error: `Traceback (most recent call last):\n  File "adjoint_test.py", line 31, in <module>\n    f, dJ_deps = opt(x0, need_gradient=True)\n  File ".../optimization_problem.py", line 552, in __call__\n    self.reset_meep()\nRuntimeError: changed_materials: cannot add new materials after simulation has run`
  },
  diverge: {
    code: `import meep as mp\ncell = mp.Vector3(10,10,0)\npml_layers = [mp.PML(1.0)]\nsources = [mp.Source(src=mp.GaussianSource(frequency=1.0,fwidth=0.5),\n           component=mp.Ez, center=mp.Vector3(-3,0,0))]\nsim = mp.Simulation(cell_size=cell, boundary_layers=pml_layers,\n                    sources=sources, resolution=20)\nsim.run(until=500)`,
    error: `meep: field decay is NaN; the simulation is probably diverging.\nIf this is unexpected, decreasing the time step (increasing resolution) may help.\nSimulation diverged at t=42.5 after 850 time steps.`
  },
  eigenmode: {
    code: `import meep as mp\nsources = [mp.EigenModeSource(\n    src=mp.GaussianSource(1/1.55, fwidth=0.2),\n    center=mp.Vector3(-3,0), size=mp.Vector3(0,2),\n    eig_band=1, eig_parity=mp.EVEN_Y+mp.ODD_Z,\n    eig_kpoint=mp.Vector3(1,0,0)\n)]`,
    error: `meep: The eigenmode solver could not find a mode.\nAttributeError: 'NoneType' object has no attribute 'group_velocity'\n  at EigenModeSource initialization`
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

/* ── 진단 실행 ───────────────────────────────────────────────────────────── */
async function runDiagnose() {
  const code  = document.getElementById('diag-code').value.trim();
  const error = document.getElementById('diag-error').value.trim();
  if (!code && !error) { alert('코드 또는 에러 메시지를 입력하세요.'); return; }

  const btn = document.getElementById('diag-submit');
  btn.disabled = true;
  btn.textContent = '분석 중...';

  const resultDiv = document.getElementById('diag-result');
  resultDiv.style.display = 'block';
  resultDiv.innerHTML = '<div class="diag-loading">meep-kb DB 검색 중...</div>';

  try {
    const res = await fetch(`${API_BASE}/api/diagnose`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({code, error, n: 5}),
    });
    const data = await res.json();
    renderDiagnoseResult(data);
  } catch (e) {
    resultDiv.innerHTML = `<div class="diag-error-msg">요청 실패: ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '진단 시작';
  }
}

/* ── 결과 렌더링 ─────────────────────────────────────────────────────────── */
function escHtml(str) {
  return (str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

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

  // Mode badge
  const modeBadge = dbSuf
    ? `<span class="diag-mode-badge diag-mode-db">DB 기반 · ${Math.round(topScore*100)}% 신뢰도</span>`
    : `<span class="diag-mode-badge diag-mode-llm">DB+LLM 혼합</span>`;

  // Error type badges
  const types = (info.detected_types||[]).map(t =>
    `<span class="diag-type-badge">${escHtml(t.type||'')}</span>`
  ).join('');

  // Physics context
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

  // Suggestion cards
  let suggHtml = '';
  if (suggestions.length > 0) {
    suggestions.forEach((s, i) => {
      const pct     = Math.round((s.score||0)*100);
      const confCls = pct >= 70 ? 'conf-high' : pct >= 45 ? 'conf-mid' : 'conf-low';
      const pctCls  = pct >= 70 ? 'pct-high'  : pct >= 45 ? 'pct-mid'  : 'pct-low';

      const rawType  = (info.detected_types && info.detected_types[0])
        ? info.detected_types[0].type : '';
      const errClass = diagErrorTypeClass(rawType || s.title || '');
      const errLabel = rawType || 'ERROR';
      const originBadge = diagOriginBadge(s.source || '');

      suggHtml += `
        <div class="diag-card">
          <div class="diag-card-header">
            <div class="diag-card-badges">
              <span class="diag-error-type ${errClass}">${escHtml(errLabel)}</span>
              ${originBadge}
            </div>
            <span class="diag-card-num">#${i+1}</span>
            <span class="diag-card-title" title="${escHtml(s.title||'관련 항목')}">${escHtml(s.title||'관련 항목')}</span>
          </div>
          <div class="diag-confidence">
            <span class="diag-confidence-label">CONF</span>
            <div class="diag-confidence-track">
              <div class="diag-confidence-fill ${confCls}" style="width:${Math.min(pct,100)}%"></div>
            </div>
            <span class="diag-confidence-pct ${pctCls}">${pct}%</span>
          </div>
          ${s.cause ? `<div class="diag-section diag-section-cause"><div class="diag-section-label">◈ 원인</div><div class="diag-section-body">${escHtml(s.cause)}</div></div>` : ''}
          ${s.solution ? `<div class="diag-section diag-section-solution"><div class="diag-section-label">◉ 해결방법</div><div class="diag-section-body">${escHtml(s.solution)}</div></div>` : ''}
          ${s.code ? `<div class="diag-section diag-section-code"><div class="diag-section-label">⟨/⟩ 수정 코드</div><pre class="diag-code-block"><code class="language-python">${escHtml(s.code)}</code></pre></div>` : ''}
          ${s.url ? `<div class="diag-section diag-section-ref"><div class="diag-section-label">↗ 참고 문서</div><a class="diag-url" href="${escHtml(s.url)}" target="_blank">${escHtml(s.url)}</a></div>` : ''}
        </div>`;
    });
  } else {
    suggHtml = '<div class="diag-no-result">DB에서 관련 항목을 찾지 못했습니다.</div>';
  }

  let llmHtml = '';
  if (data.llm_result && data.llm_result.available && data.llm_result.answer) {
    llmHtml = `
      <div class="diag-llm-section">
        <div class="diag-llm-header">LLM 도메인 분석 — DB 보조 + 물리 추론</div>
        <div class="diag-llm-body">${(typeof marked !== 'undefined') ? marked.parse(data.llm_result.answer) : escHtml(data.llm_result.answer)}</div>
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
    cb.style.cssText = 'position:absolute;top:7px;right:8px;padding:2px 8px;font-size:9px;font-family:monospace;letter-spacing:0.08em;background:#0d1428;color:#607098;border:1px solid #1a2a50;border-radius:3px;cursor:pointer;z-index:10;opacity:0;transition:opacity 0.15s;text-transform:uppercase;';
    pre.addEventListener('mouseenter', () => cb.style.opacity = '1');
    pre.addEventListener('mouseleave', () => cb.style.opacity = '0');
    cb.addEventListener('click', (e) => {
      e.stopPropagation();
      const code = pre.querySelector('code');
      navigator.clipboard.writeText(code ? code.innerText : pre.innerText).then(() => {
        cb.textContent = 'OK'; cb.style.color = '#00E87A';
        setTimeout(() => { cb.textContent = 'COPY'; cb.style.color = '#607098'; }, 1500);
      });
    });
    pre.appendChild(cb);
  });
}
