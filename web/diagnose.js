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

function renderDiagnoseResult(data) {
  const resultDiv  = document.getElementById('diag-result');
  const info       = data.error_info || {};
  const suggestions= data.suggestions || [];
  const dbSuf      = data.db_sufficient;
  const topScore   = data.top_score || 0;

  const modeBadge = dbSuf
    ? `<span class="diag-mode-badge diag-mode-db">DB 기반 답변 (${Math.round(topScore*100)}%)</span>`
    : `<span class="diag-mode-badge diag-mode-llm">DB+LLM 혼합 (DB 매칭 부족)</span>`;

  const types = (info.detected_types||[]).map(t =>
    `<span class="diag-type-badge">${t.type}: ${t.description}</span>`
  ).join(' ');

  let suggHtml = '';
  if (suggestions.length > 0) {
    suggestions.forEach((s,i) => {
      const pct = Math.round((s.score||0)*100);
      const srcIcon = s.source==='kb_vector' ? '[벡터]' : s.source==='kb_sqlite' ? '[DB]' : '[KB]';
      suggHtml += `
        <div class="diag-card">
          <div class="diag-card-header">
            <span class="diag-card-num">#${i+1}</span>
            <span class="diag-card-title">${s.title||'관련 항목'}</span>
            <span class="diag-card-score">${srcIcon} ${pct}%</span>
          </div>
          ${s.cause    ? `<div class="diag-section"><div class="diag-section-label">원인</div><div class="diag-section-body">${escHtml(s.cause)}</div></div>` : ''}
          ${s.solution ? `<div class="diag-section"><div class="diag-section-label">해결 방법</div><div class="diag-section-body">${escHtml(s.solution)}</div></div>` : ''}
          ${s.code     ? `<div class="diag-section"><div class="diag-section-label">수정 코드</div><pre class="diag-code-block"><code class="language-python">${escHtml(s.code)}</code></pre></div>` : ''}
          ${s.url      ? `<div class="diag-section"><a class="diag-url" href="${s.url}" target="_blank">참고 문서 →</a></div>` : ''}
        </div>`;
    });
  } else {
    suggHtml = '<div class="diag-no-result">DB에서 관련 항목을 찾지 못했습니다.</div>';
  }

  // ── 물리 파라미터 컨텍스트 표시 ──────────────────────────────────────────
  let physHtml = '';
  const phys = data.physics_context || {};
  const physItems = [];
  if (phys.resolution)    physItems.push(`🔲 resolution=${phys.resolution}`);
  if (phys.cell_size)     physItems.push(`📐 cell=${phys.cell_size}`);
  if (phys.pml_thickness) physItems.push(`🛡️ PML=${phys.pml_thickness}`);
  if (phys.fcen)          physItems.push(`🌊 fcen=${phys.fcen}`);
  if (phys.epsilons)      physItems.push(`⚡ ε=${phys.epsilons.join(',')}`);
  if (phys.uses_adjoint)  physItems.push(`🔄 adjoint최적화`);
  if (phys.uses_mpi)      physItems.push(`⚙️ MPI병렬`);
  if (physItems.length > 0) {
    physHtml = `<div class="diag-phys-ctx">
      <span class="diag-phys-label">🔬 코드 물리 파라미터</span>
      ${physItems.map(p => `<span class="diag-phys-tag">${p}</span>`).join('')}
    </div>`;
  }

  let llmHtml = '';
  if (data.llm_result && data.llm_result.available && data.llm_result.answer) {
    llmHtml = `
      <div class="diag-llm-section">
        <div class="diag-llm-header">🧠 MEEP 물리 도메인 분석 (DB 참고 + 물리 추론)</div>
        <div class="diag-llm-body">${marked.parse(data.llm_result.answer)}</div>
      </div>`;
  }

  resultDiv.innerHTML = `
    <div class="diag-result-header">
      ${modeBadge}
      ${physHtml}
      <div class="diag-detected-types">${types}</div>
      ${info.last_error_line ? `<div class="diag-last-err">핵심 에러: <code>${escHtml(info.last_error_line)}</code></div>` : ''}
    </div>
    <div class="diag-suggestions">${suggHtml}</div>
    ${llmHtml}`;

  resultDiv.querySelectorAll('pre code').forEach(el => {
    if (typeof hljs !== 'undefined') hljs.highlightElement(el);
  });
}
