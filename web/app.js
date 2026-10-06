/* ============================================================
   TRUSTLENS — CLIENT APPLICATION
   SSE-powered real-time analysis with animated rendering
   ============================================================ */

(function () {
  'use strict';

  // ── DOM References ───────────────────────────────────────
  const searchForm     = document.getElementById('searchForm');
  const domainInput    = document.getElementById('domainInput');
  const analyzeBtn     = document.getElementById('analyzeBtn');
  const progressSection = document.getElementById('progressSection');
  const stepper        = document.getElementById('stepper');
  const resultsSection = document.getElementById('resultsSection');
  const errorCard      = document.getElementById('errorCard');
  const errorMessage   = document.getElementById('errorMessage');
  const errorRetryBtn  = document.getElementById('errorRetryBtn');
  const toastContainer = document.getElementById('toastContainer');

  // Score elements
  const scoreRing      = document.getElementById('scoreRing');
  const scoreValue     = document.getElementById('scoreValue');
  const scoreCompany   = document.getElementById('scoreCompany');
  const scoreBadges    = document.getElementById('scoreBadges');
  const scoreSummary   = document.getElementById('scoreSummary');

  // Section containers
  const positiveSection  = document.getElementById('positiveSection');
  const positiveGrid     = document.getElementById('positiveGrid');
  const positiveCount    = document.getElementById('positiveCount');
  const neutralSection   = document.getElementById('neutralSection');
  const neutralGrid      = document.getElementById('neutralGrid');
  const neutralCount     = document.getElementById('neutralCount');
  const riskSection      = document.getElementById('riskSection');
  const riskGrid         = document.getElementById('riskGrid');
  const riskCount        = document.getElementById('riskCount');
  const evidenceTrailSection = document.getElementById('evidenceTrailSection');
  const evidenceList     = document.getElementById('evidenceList');
  const evidenceCount    = document.getElementById('evidenceCount');
  const missingSection   = document.getElementById('missingSection');
  const missingList      = document.getElementById('missingList');
  const reasoningSection = document.getElementById('reasoningSection');
  const reasoningText    = document.getElementById('reasoningText');
  const rawEvidenceSection = document.getElementById('rawEvidenceSection');
  const rawToggleBtn     = document.getElementById('rawToggleBtn');
  const rawDrawer        = document.getElementById('rawDrawer');
  const rawTabs          = document.getElementById('rawTabs');
  const rawPre           = document.getElementById('rawPre');

  // State
  let currentEventSource = null;
  let fullResultData = null;


  // ── Utility: Escape HTML ─────────────────────────────────
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }


  // ── Toast Notifications ──────────────────────────────────
  function showToast(message, type = 'info', duration = 4000) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('removing');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }


  // ── Reset UI ─────────────────────────────────────────────
  function resetUI() {
    resultsSection.classList.remove('visible');
    resultsSection.style.display = 'none';
    errorCard.classList.remove('visible');
    errorCard.style.display = 'none';
    progressSection.classList.remove('visible');

    // Reset stepper
    stepper.querySelectorAll('.step').forEach(step => {
      step.classList.remove('active', 'done', 'error');
      const circle = step.querySelector('.step-circle');
      circle.innerHTML = circle.textContent.replace(/[✓✗]/g, '');
    });

    // Reset steps numbers
    const steps = stepper.querySelectorAll('.step');
    steps.forEach((s, i) => {
      s.querySelector('.step-circle').textContent = i + 1;
    });

    // Clear sections
    positiveGrid.innerHTML = '';
    neutralGrid.innerHTML = '';
    riskGrid.innerHTML = '';
    evidenceList.innerHTML = '';
    missingList.innerHTML = '';
    reasoningText.textContent = '';
    rawPre.textContent = '';
    scoreBadges.innerHTML = '';
    scoreSummary.textContent = '';
    scoreCompany.textContent = '—';
    scoreValue.textContent = '0';
    scoreRing.style.background = '';

    [positiveSection, neutralSection, riskSection,
     evidenceTrailSection, missingSection, reasoningSection,
     rawEvidenceSection].forEach(el => el.style.display = 'none');

    fullResultData = null;
  }


  // ── Stepper Control ──────────────────────────────────────
  const STEP_MAP = {
    'whois': 0,
    'website': 1,
    'github': 2,
    'tavily': 3,
    'normalize': 4,
    'analysis': 5
  };

  function setStepActive(stepName) {
    const idx = STEP_MAP[stepName];
    if (idx === undefined) return;
    const steps = stepper.querySelectorAll('.step');
    steps[idx].classList.add('active');
    steps[idx].classList.remove('done', 'error');
  }

  function setStepDone(stepName) {
    const idx = STEP_MAP[stepName];
    if (idx === undefined) return;
    const steps = stepper.querySelectorAll('.step');
    steps[idx].classList.remove('active');
    steps[idx].classList.add('done');
    steps[idx].querySelector('.step-circle').textContent = '✓';
  }

  function setStepError(stepName) {
    const idx = STEP_MAP[stepName];
    if (idx === undefined) return;
    const steps = stepper.querySelectorAll('.step');
    steps[idx].classList.remove('active');
    steps[idx].classList.add('error');
    steps[idx].querySelector('.step-circle').textContent = '✗';
  }


  // ── Animate Score Ring ───────────────────────────────────
  function animateScore(targetScore) {
    const duration = 1500;
    const startTime = performance.now();

    // Color thresholds
    let color1, color2;
    if (targetScore >= 70) {
      color1 = '#34d399'; color2 = '#38bdf8';
    } else if (targetScore >= 40) {
      color1 = '#fbbf24'; color2 = '#f59e0b';
    } else {
      color1 = '#f87171'; color2 = '#ef4444';
    }

    function update(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(eased * targetScore);

      scoreValue.textContent = current;

      const angle = (eased * targetScore / 100) * 360;
      scoreRing.style.background =
        `conic-gradient(${color1} 0deg, ${color2} ${angle}deg, rgba(255,255,255,0.05) ${angle}deg)`;

      if (progress < 1) {
        requestAnimationFrame(update);
      }
    }

    requestAnimationFrame(update);
  }


  // ── Render Signal Cards ──────────────────────────────────
  function renderSignalCard(signal, type) {
    const iconMap = { positive: '✓', neutral: '•', risk: '!' };
    const labelKey = type === 'risk' ? 'evidence' : (type === 'neutral' ? 'explanation' : 'evidence');
    const body = signal[labelKey] || signal.explanation || signal.evidence || '';

    return `
      <div class="signal-card glass-card">
        <div class="signal-header">
          <div class="signal-icon ${type}">${iconMap[type]}</div>
          <div class="signal-title">${escapeHtml(signal.signal || '')}</div>
        </div>
        <div class="signal-body">
          ${signal.source ? `<div class="signal-source">${escapeHtml(signal.source)}</div>` : ''}
          ${body ? `<div class="signal-evidence">${escapeHtml(body)}</div>` : ''}
        </div>
      </div>
    `;
  }


  // ── Render Evidence Trail ────────────────────────────────
  function renderEvidenceItem(item) {
    const strength = (item.strength || 'low').toLowerCase();
    return `
      <div class="evidence-item glass-card">
        <div class="evidence-claim">${escapeHtml(item.claim || '')}</div>
        <div class="evidence-source-tag">${escapeHtml(item.source || '')}</div>
        <div class="evidence-strength ${strength}">${escapeHtml(strength)}</div>
      </div>
    `;
  }


  // ── Render Full Results ──────────────────────────────────
  function renderResults(data) {
    fullResultData = data;
    const analysis = data.analysis?.analysis || data.analysis || {};

    // Company name
    scoreCompany.textContent = analysis.company || data.company_domain || '—';

    // Badges
    const assessment = analysis.assessment || 'unknown';
    const confidence = analysis.confidence || 'low';
    const trustScore = analysis.trust_score || 0;

    let assessmentClass = '';
    if (trustScore >= 70) assessmentClass = 'high-trust';
    else if (trustScore < 40) assessmentClass = 'low-trust';

    const assessmentLabel = assessment.replace(/_/g, ' ');

    scoreBadges.innerHTML = `
      <span class="badge badge-assessment ${assessmentClass}">${escapeHtml(assessmentLabel)}</span>
      <span class="badge badge-confidence">Confidence: ${escapeHtml(confidence)}</span>
    `;

    // Summary
    scoreSummary.textContent = analysis.summary || '';

    // Animate score
    animateScore(trustScore);

    // Positive Signals
    const positiveSignals = analysis.positive_signals || [];
    if (positiveSignals.length) {
      positiveSection.style.display = 'block';
      positiveCount.textContent = positiveSignals.length;
      positiveGrid.innerHTML = positiveSignals.map(s => renderSignalCard(s, 'positive')).join('');
    }

    // Neutral Signals
    const neutralSignals = analysis.neutral_signals || [];
    if (neutralSignals.length) {
      neutralSection.style.display = 'block';
      neutralCount.textContent = neutralSignals.length;
      neutralGrid.innerHTML = neutralSignals.map(s => renderSignalCard(s, 'neutral')).join('');
    }

    // Risk Signals
    const riskSignals = analysis.risk_signals || [];
    if (riskSignals.length) {
      riskSection.style.display = 'block';
      riskCount.textContent = riskSignals.length;
      riskGrid.innerHTML = riskSignals.map(s => renderSignalCard(s, 'risk')).join('');
    }

    // Evidence Trail
    const trail = analysis.evidence_trail || [];
    if (trail.length) {
      evidenceTrailSection.style.display = 'block';
      evidenceCount.textContent = trail.length;
      evidenceList.innerHTML = trail.map(renderEvidenceItem).join('');
    }

    // Missing Information
    const missing = analysis.missing_information || [];
    if (missing.length) {
      missingSection.style.display = 'block';
      missingList.innerHTML = missing.map(item =>
        `<div class="missing-item glass-card">
          <div class="missing-item-dot"></div>
          <div>${escapeHtml(item)}</div>
        </div>`
      ).join('');
    }

    // Reasoning
    const reasoning = analysis.reasoning || '';
    if (reasoning) {
      reasoningSection.style.display = 'block';
      reasoningText.textContent = reasoning;
    }

    // Raw evidence
    rawEvidenceSection.style.display = 'block';
    showRawTab('whois');

    // Show results
    resultsSection.style.display = 'block';
    // Force reflow then add class for animation
    resultsSection.offsetHeight;
    resultsSection.classList.add('visible');

    // Scroll to results
    setTimeout(() => {
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 200);
  }


  // ── Raw Evidence Tabs ────────────────────────────────────
  function showRawTab(tabName) {
    if (!fullResultData) return;

    const evidence = fullResultData.evidence_packet?.evidence || {};
    let content;

    switch (tabName) {
      case 'whois':
        content = evidence.whois || {};
        break;
      case 'website':
        content = evidence.website || {};
        break;
      case 'github':
        content = evidence.github || {};
        break;
      case 'search':
        content = evidence.external_search || {};
        break;
      case 'full':
        content = fullResultData;
        break;
      default:
        content = {};
    }

    rawPre.textContent = JSON.stringify(content, null, 2);

    // Update tab active state
    rawTabs.querySelectorAll('.raw-tab').forEach(tab => {
      tab.classList.toggle('active', tab.dataset.tab === tabName);
    });
  }

  rawToggleBtn.addEventListener('click', () => {
    rawToggleBtn.classList.toggle('open');
    rawDrawer.classList.toggle('open');
  });

  rawTabs.addEventListener('click', (e) => {
    const tab = e.target.closest('.raw-tab');
    if (tab) showRawTab(tab.dataset.tab);
  });


  // Backend URL: Modal when hosted on Vercel, otherwise the Flask
  // server that served this page (localhost, 127.0.0.1, LAN IP).
  const MODAL_API_URL = 'https://yakshmajas--trustlens-analyze.modal.run';
  const API_BASE = window.location.hostname.endsWith('vercel.app')
    ? MODAL_API_URL
    : '/api/analyze/stream';

  // ── SSE Analysis ─────────────────────────────────────────
  function startAnalysis(domain) {
    resetUI();

    analyzeBtn.classList.add('loading');
    analyzeBtn.disabled = true;
    progressSection.classList.add('visible');

    const url = `${API_BASE}?domain=${encodeURIComponent(domain)}`;

    currentEventSource = new EventSource(url);

    currentEventSource.addEventListener('resolved', (e) => {
      try {
        const data = JSON.parse(e.data);
        showToast(`Resolved "${data.input}" → ${data.domain}`, 'info', 6000);
      } catch (err) { /* ignore */ }
    });

    currentEventSource.addEventListener('step_start', (e) => {
      try {
        const data = JSON.parse(e.data);
        setStepActive(data.step);
      } catch (err) { /* ignore parse errors */ }
    });

    currentEventSource.addEventListener('step_done', (e) => {
      try {
        const data = JSON.parse(e.data);
        setStepDone(data.step);
      } catch (err) { /* ignore */ }
    });

    currentEventSource.addEventListener('step_error', (e) => {
      try {
        const data = JSON.parse(e.data);
        setStepError(data.step);
        const detail = data.error ? `: ${data.error}` : '';
        showToast(`Step "${data.step}" failed${detail}`, 'error', 8000);
      } catch (err) { /* ignore */ }
    });

    currentEventSource.addEventListener('complete', (e) => {
      try {
        const data = JSON.parse(e.data);
        currentEventSource.close();
        currentEventSource = null;
        analyzeBtn.classList.remove('loading');
        analyzeBtn.disabled = false;

        if (data.success && data.result?.analysis?.success === false) {
          // Collectors ran but the AI step failed: show why instead of a 0 score
          showError(`AI analysis failed: ${data.result.analysis.error || 'Unknown error'}`);
        } else if (data.success) {
          showToast('Analysis complete!', 'success');
          renderResults(data.result);
        } else {
          showError(data.error || 'Analysis failed');
        }
      } catch (err) {
        showError('Failed to parse analysis results');
      }
    });

    currentEventSource.addEventListener('error_event', (e) => {
      try {
        const data = JSON.parse(e.data);
        currentEventSource.close();
        currentEventSource = null;
        analyzeBtn.classList.remove('loading');
        analyzeBtn.disabled = false;
        showError(data.error || 'Analysis failed');
      } catch (err) {
        showError('Connection lost');
      }
    });

    currentEventSource.onerror = () => {
      if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
      }
      analyzeBtn.classList.remove('loading');
      analyzeBtn.disabled = false;
      showError('Connection to server lost. Make sure the server is running.');
    };
  }


  // ── Show Error ───────────────────────────────────────────
  function showError(message) {
    errorMessage.textContent = message;
    errorCard.style.display = 'block';
    errorCard.classList.add('visible');
    progressSection.classList.remove('visible');
    showToast(message, 'error', 6000);
  }


  // ── Event Listeners ──────────────────────────────────────
  // The server accepts a domain or a company name and normalizes it
  searchForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = domainInput.value.trim();
    if (!query) {
      showToast('Please enter a company name or domain', 'error');
      return;
    }
    startAnalysis(query);
  });

  errorRetryBtn.addEventListener('click', () => {
    const query = domainInput.value.trim();
    if (query) {
      startAnalysis(query);
    }
  });

  // Keyboard shortcut: Ctrl+K focuses search
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      domainInput.focus();
      domainInput.select();
    }
  });

})();
