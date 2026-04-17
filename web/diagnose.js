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
    code: `import meep as mp\nimport meep.adjoint as mpa\nimport autograd.numpy as npa\n\nopt = mpa.OptimizationProblem(\n    simulation=sim,\n    objective_functions=[J],\n    objective_arguments=[monitor],\n    design_regions=[design_region],\n)\nx0 = npa.ones((Nx, Ny)) * 0.5\nopt.update_design([x0])\nf, dJ_deps = opt(x0, need_gradient=True)\n# 두 번 호출\nf2, dJ2 = opt(x1, need_gradient=True)`,
    error: `Traceback (most recent call last):\n  File "adjoint_test.py", line 31, in <module>\n    f, dJ_deps = opt(x0, need_gradient=True)\n  File ".../optimization_problem.py", line 552, in __call__\n    self.reset_meep()\nRuntimeError: changed_materials: cannot add new materials after simulation has run`
  },
  diverge: {
    code: `import meep as mp\ncell = mp.Vector3(10,10,0)\npml_layers = [mp.PML(1.0)]\nsources = [mp.Source(src=mp.GaussianSource(frequency=1.0,fwidth=0.5),\n           component=mp.Ez, center=mp.Vector3(-3,0,0))]\nsim = mp.Simulation(cell_size=cell, boundary_layers=pml_layers,\n                    sources=sources, resolution=20)\nsim.run(until=500)`,
    error: `meep: field decay is NaN; the simulation is probably diverging.\nIf this is unexpected, decreasing the time step (increasing resolution) may help.\nSimulation diverged at t=42.5 after 850 time steps.`
  },
  eigenmode: {
    code: `import meep as mp\nsources = [mp.EigenModeSource(\n    src=mp.GaussianSource(1/1.55, fwidth=0.2),\n    center=mp.Vector3(-3,0), size=mp.Vector3(0,2),\n    eig_band=1,\n    eig_kpoint=mp.Vector3(1,0,0)\n)]`,
    error: `meep: The eigenmode solver could not find a mode.\nAttributeError: 'NoneType' object has no attribute 'group_velocity'\n  at EigenModeSource initialization`
  },
  src_in_pml: {
    code: `import meep as mp\nsy = 10.0\ndpml = 2.0\ncell = mp.Vector3(0, sy, 0)\npml_layers = [mp.PML(thickness=dpml, direction=mp.Y)]\n# 소스가 PML 안에 들어가 있는 잘못된 코드\nsources = [mp.Source(\n    src=mp.GaussianSource(1.0, fwidth=0.1),\n    component=mp.Ex,\n    center=mp.Vector3(0, -4.5, 0),  # PML 경계(±3.0) 내부!\n    size=mp.Vector3(1, 0, 0)\n)]\nsim = mp.Simulation(cell_size=cell, boundary_layers=pml_layers,\n                    sources=sources, resolution=20)\nsim.run(until=100)`,
    error: `meep: field decay is NaN; the simulation is probably diverging.`
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

/* ── 실행 검증 버튼 ──────────────────────────────────────────────────────── */
async function runFixAndVerify() {
  const code  = document.getElementById('diag-code').value.trim();
  const error = document.getElementById('diag-error').value.trim();
  if (!code && !error) { alert('코드 또는 에러 메시지를 입력하세요.'); return; }

  const btn = document.getElementById('diag-run-btn');
  btn.disabled = true;
  btn.textContent = '실행 검증 중...';

  const runDiv = document.getElementById('diag-run-result');
  runDiv.style.display = 'block';
  runDiv.innerHTML = '<div class="diag-loading">수정 코드 생성 + Docker 실행 중 (최대 60초)...</div>';

  try {
    const res = await fetch(`${API_BASE}/api/diagnose/fix-and-run`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({code, error, run_timeout: 60}),
    });
    const data = await res.json();
    renderRunResult(data, runDiv);
  } catch (e) {
    runDiv.innerHTML = `<div class="diag-error-msg">요청 실패: ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = '⚡ 수정 + 실행 검증';
  }
}

/* ── 결과 렌더링 ─────────────────────────────────────────────────────────── */
function escHtml(str) {
  return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
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
  if (s.includes('unified'))  return `<span class="diag-origin-badge origin-unified">통합DB</span>`;
  if (s.includes('vector') || s.includes('sqlite') || s === 'kb') {
    return `<span class="diag-origin-badge origin-db">DB검증됨</span>`;
  }
  if (s.includes('github'))  return `<span class="diag-origin-badge origin-github">GitHub</span>`;
  if (s.includes('marl'))    return `<span class="diag-origin-badge origin-marl">MARL자동수정</span>`;
  if (s.includes('llm') || s.includes('generation')) {
    return `<span class="diag-origin-badge origin-llm">LLM생성</span>`;
  }
  return `<span class="diag-origin-badge origin-db">KB</span>`;
}

/* ── 물리 이슈 섹션 렌더링 ───────────────────────────────────────────────── */
function renderPhysicsIssues(physIssues) {
  if (!physIssues || physIssues.length === 0) return '';
  const sevIcon  = { critical: '🔴', warning: '🟡', info: '🔵' };
  const sevClass = { critical: 'phys-critical', warning: 'phys-warning', info: 'phys-info' };
  const items = physIssues.map(p => `
    <div class="diag-phys-issue ${sevClass[p.severity] || ''}">
      <div class="phys-rule">
        <span class="phys-icon">${sevIcon[p.severity] || '•'}</span>
        <span class="phys-rule-id">${escHtml(p.rule)}</span>
        <span class="phys-sev-tag">${escHtml(p.severity)}</span>
      </div>
      <div class="phys-msg">${escHtml(p.message)}</div>
      <pre class="phys-fix">${escHtml(p.fix_hint)}</pre>
    </div>`).join('');
  return `
    <div class="diag-physics-section">
      <div class="diag-section-label">⚡ 물리/수치 정적 분석 (${physIssues.length}건)</div>
      ${items}
    </div>`;
}

/* ── 수정된 전체 코드 블록 ───────────────────────────────────────────────── */
function renderFixedCode(fixedCode) {
  if (!fixedCode) return '';
  return `
    <div class="diag-fixed-code-section">
      <div class="diag-section-label">🔧 수정된 코드 (전체)</div>
      <pre class="diag-code-block diag-code-full"><code class="language-python">${escHtml(fixedCode)}</code></pre>
    </div>`;
}

/* ── 실행 결과 렌더링 ────────────────────────────────────────────────────── */
function renderRunResult(data, container) {
  const rr = data.run_result;
  if (!rr) {
    container.innerHTML = '<div class="diag-run-nocode">수정 코드를 생성하지 못했습니다.</div>';
    return;
  }
  const ok    = rr.success;
  const retry = data.retry_result;
  const retryOk = retry && retry.success;

  const statusHtml = ok
    ? `<div class="diag-run-status run-ok">✅ 실행 검증 통과 (${rr.elapsed_s}s)</div>`
    : (retryOk
        ? `<div class="diag-run-status run-retry">🔄 1차 실패 → 재시도 성공 (${retry.elapsed_s}s)</div>`
        : `<div class="diag-run-status run-fail">❌ 실행 검증 실패 (exit=${rr.exit_code})</div>`);

  const codeToShow = retryOk ? retry.fixed_code : data.fixed_code;
  const stdoutToShow = (retryOk ? retry.stdout : rr.stdout) || '';
  const stderrToShow = (retryOk ? retry.stderr : rr.stderr) || '';

  container.innerHTML = `
    ${statusHtml}
    ${codeToShow ? renderFixedCode(codeToShow) : ''}
    <div class="diag-run-output">
      <div class="diag-section-label">실행 출력</div>
      <pre class="diag-run-stdout">${escHtml(stdoutToShow.slice(-2000))}</pre>
      ${stderrToShow ? `<pre class="diag-run-stderr">${escHtml(stderrToShow.slice(-500))}</pre>` : ''}
    </div>
    ${renderPhysicsIssues(data.physics_issues)}`;
  container.querySelectorAll('pre code').forEach(el => {
    if (typeof hljs !== 'undefined') hljs.highlightElement(el);
  });
  addCopyButtons(container);
}

/* ── copy 버튼 공통 함수 ─────────────────────────────────────────────────── */
function addCopyButtons(root) {
  root.querySelectorAll('pre').forEach(pre => {
    if (pre.querySelector('.diag-copy-btn')) return; // 중복 방지
    pre.style.position = 'relative';
    const cb = document.createElement('button');
    cb.className = 'diag-copy-btn';
    cb.textContent = 'COPY';
    cb.style.cssText = 'position:absolute;top:7px;right:8px;padding:2px 8px;font-size:9px;font-family:monospace;letter-spacing:0.08em;background:#0d1428;color:#607098;border:1px solid #1a2a50;border-radius:3px;cursor:pointer;z-index:10;opacity:0;transition:opacity 0.15s;text-transform:uppercase;';
    pre.addEventListener('mouseenter', () => cb.style.opacity = '1');
    pre.addEventListener('mouseleave', () => cb.style.opacity = '0');
    cb.addEventListener('click', (e) => {
      e.stopPropagation();
      const codeEl = pre.querySelector('code');
      navigator.clipboard.writeText(codeEl ? codeEl.innerText : pre.innerText).then(() => {
        cb.textContent = 'OK'; cb.style.color = '#00E87A';
        setTimeout(() => { cb.textContent = 'COPY'; cb.style.color = '#607098'; }, 1500);
      });
    });
    pre.appendChild(cb);
  });
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

  // Physics context params
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
  if (phys.k_point_nonzero) physItems.push('k≠0');
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

      // symptom 정보 (unified 전용)
      const symptomHtml = (s.symptom_num || s.symptom_beh || s.symptom_err) ? `
        <div class="diag-section diag-section-symptom">
          <div class="diag-section-label">◐ 증상</div>
          <div class="diag-section-body">
            ${s.symptom_num  ? `<span class="sym-tag sym-num">수치: ${escHtml(s.symptom_num)}</span>`  : ''}
            ${s.symptom_beh  ? `<span class="sym-tag sym-beh">동작: ${escHtml(s.symptom_beh)}</span>`  : ''}
            ${s.symptom_err  ? `<span class="sym-tag sym-err">에러: ${escHtml(s.symptom_err)}</span>`  : ''}
          </div>
        </div>` : '';

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
          ${symptomHtml}
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
    ${renderPhysicsIssues(data.physics_issues)}
    ${renderFixedCode(data.fixed_code)}
    <div class="diag-suggestions">${suggHtml}</div>
    ${llmHtml}`;

  // 단계별 진단 가이드 삽입 (상단)
  if (data.diagnostic_stages && data.diagnostic_stages.length > 0) {
    let stagesHtml = `<div class="diag-stages-section">
      <div class="diag-stages-title">🔬 단계별 진단 가이드</div>`;

    data.diagnostic_stages.forEach((s, i) => {
      const stageNum = (s.stage_key || '').split('_')[0].replace('STAGE', '');
      stagesHtml += `
      <div class="diag-stage-card ${i === 0 ? 'primary' : ''}">
        <div class="diag-stage-header">
          <span class="diag-stage-badge">STAGE ${escHtml(stageNum)}</span>
          <span class="diag-stage-name">${escHtml(s.stage_name)}</span>
          <span class="diag-stage-score">관련도: ${s.match_score}</span>
        </div>

        <div class="diag-stage-section">
          <div class="diag-stage-label">✅ 확인 항목</div>
          <ul class="diag-checklist">
            ${(s.checklist || []).map(item => `<li>${escHtml(item)}</li>`).join('')}
          </ul>
        </div>

        <details class="diag-stage-details">
          <summary>💻 진단 스니펫 (복붙 실행)</summary>
          <div class="diag-code-wrap">
            <button class="concept-copy-btn" onclick="copyDiagCode(this)">복사</button>
            <pre><code class="language-python">${escHtml(s.diagnostic_code || '')}</code></pre>
          </div>
        </details>

        ${(s.pitfalls && s.pitfalls.length > 0) ? `
        <details class="diag-stage-details">
          <summary>⚠️ 주의사항 (${s.pitfalls.length}개)</summary>
          <ul class="diag-pitfalls">
            ${s.pitfalls.map(p => `<li>${escHtml(p)}</li>`).join('')}
          </ul>
        </details>` : ''}

        ${s.next_stage ? `<div class="diag-next-stage">다음: ${escHtml(s.next_stage)} →</div>` : ''}
      </div>`;
    });

    stagesHtml += `</div>`;
    resultDiv.insertAdjacentHTML('afterbegin', stagesHtml);

    // syntax highlight for stage code blocks
    resultDiv.querySelectorAll('.diag-code-wrap pre code').forEach(el => {
      if (typeof hljs !== 'undefined') hljs.highlightElement(el);
    });
  }

  resultDiv.querySelectorAll('pre code').forEach(el => {
    if (typeof hljs !== 'undefined') hljs.highlightElement(el);
  });
  addCopyButtons(resultDiv);
}

function copyDiagCode(btn) {
  const code = btn.closest('.diag-code-wrap').querySelector('code');
  if (!code) return;
  navigator.clipboard.writeText(code.innerText).then(() => {
    btn.textContent = '복사✅';
    setTimeout(() => btn.textContent = '복사', 1500);
  });
}
