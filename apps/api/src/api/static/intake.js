function selectTab(btn, panelId) {
  document.querySelectorAll('.source-tab').forEach(function(t) {
    t.classList.remove('source-tab--active');
    t.setAttribute('aria-selected', 'false');
  });
  document.querySelectorAll('.source-tab-panel').forEach(function(p) {
    p.classList.add('source-tab-panel--hidden');
  });
  btn.classList.add('source-tab--active');
  btn.setAttribute('aria-selected', 'true');
  document.getElementById(panelId).classList.remove('source-tab-panel--hidden');
}

var _inflight = 0;

function disableGenerate() {
  _inflight++;
  var btn = document.getElementById('generate-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Extracting…'; }
}

function enableGenerate() {
  _inflight = Math.max(0, _inflight - 1);
  if (_inflight === 0) {
    var btn = document.getElementById('generate-btn');
    if (btn) { btn.disabled = false; btn.textContent = 'Generate syllabus →'; }
  }
}

function refreshGenerateBtn() {
  if (_inflight === 0) {
    var btn = document.getElementById('generate-btn');
    if (btn) { btn.disabled = false; }
  }
}

function confirmGenerate() {
  var cards = document.querySelectorAll('.source-cards-list .source-card:not(.source-card--error)');
  if (cards.length === 0) { return true; }
  return confirm('Skip added sources and generate from scratch?');
}

function dismissSuggestion(btn) {
  btn.closest('li').remove();
}

document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('generate-form');
  if (!form) { return; }
  form.addEventListener('submit', function () {
    var btn = document.getElementById('generate-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Generating…'; }
  });
});
