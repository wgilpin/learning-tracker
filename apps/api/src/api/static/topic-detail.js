// Text selection → AI Assistant modal
(function () {
  var readingPanel = document.getElementById('reading-panel');
  var modal = document.getElementById('command-modal');
  var form = document.getElementById('modal-comment-form');
  var anchorInput = document.getElementById('modal-anchor');
  var previewText = document.getElementById('modal-sel-preview-text');
  var bodyInput = document.getElementById('modal-body-input');
  var aiBtn = document.getElementById('ai-selection-btn');
  var currentAnchor = null;
  var currentChapterId = null;

  function hideBtn() {
    aiBtn.style.display = 'none';
  }

  function clearSelection() {
    currentAnchor = null;
    currentChapterId = null;
  }

  document.addEventListener('mouseup', function (e) {
    if (modal.contains(e.target) || aiBtn.contains(e.target)) return;

    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.toString().trim() === '') {
      hideBtn(); clearSelection();
      return;
    }

    if (!readingPanel.contains(sel.anchorNode)) {
      hideBtn(); clearSelection();
      return;
    }

    var node = sel.anchorNode;
    var para = null;
    while (node && node !== readingPanel) {
      if (node.nodeType === 1 && node.classList && node.classList.contains('chapter-paragraph')) {
        para = node;
        break;
      }
      node = node.parentNode;
    }
    if (!para) { hideBtn(); clearSelection(); return; }

    var chapterEl = para.closest('[data-chapter-id]');
    if (!chapterEl) { hideBtn(); clearSelection(); return; }

    currentAnchor = para.id;
    currentChapterId = chapterEl.dataset.chapterId;

    var rect = para.getBoundingClientRect();
    aiBtn.style.display = 'flex';
    aiBtn.style.top = rect.top + 'px';
  });

  aiBtn.addEventListener('click', function () {
    var sel = window.getSelection();
    var selectedText = sel ? sel.toString().trim() : '';

    anchorInput.value = currentAnchor;
    document.getElementById('modal-selected-text').value = selectedText;
    previewText.textContent = selectedText
      ? '\u201c' + selectedText.slice(0, 120) + (selectedText.length > 120 ? '\u2026' : '') + '\u201d'
      : '';

    bodyInput.value = '';
    hideBtn();  // hide button but keep currentAnchor/currentChapterId alive
    modal.showModal();
    bodyInput.focus();
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var submitBtn = document.getElementById('modal-submit-btn');
    submitBtn.classList.add('modal-submit-btn--loading');

    htmx.ajax('POST', '/chapters/' + currentChapterId + '/comments', {
      target: '#comments-' + currentAnchor,
      swap: 'beforeend',
      values: {
        paragraph_anchor: anchorInput.value,
        selected_text: document.getElementById('modal-selected-text').value,
        content: bodyInput.value,
      },
    }).then(function () {
      submitBtn.classList.remove('modal-submit-btn--loading');
      modal.close();
      form.reset();
    });
  });

  modal.addEventListener('close', function () { hideBtn(); clearSelection(); });

  window.submitQuick = function (prompt) {
    bodyInput.value = prompt;
    form.requestSubmit();
  };
})();

// Syllabus edit toggle
(function () {
  var btn = document.getElementById('syllabus-edit-toggle');
  var nav = document.getElementById('syllabus-panel');
  btn.addEventListener('click', function () {
    nav.classList.toggle('is-editing');
    btn.classList.toggle('is-active');
  });
})();

// Chat panel: SSE streaming, message history, quiz handling
(function () {
  var topicId = document.getElementById('chat-panel').dataset.topicId;
  var chatPanel = document.getElementById('chat-panel');
  var chatForm = document.getElementById('chat-form');
  var chatInput = document.getElementById('chat-input');
  var chatMessages = document.getElementById('chat-messages');
  var chatSuggested = document.getElementById('chat-suggested');
  var chatLoading = document.getElementById('chat-loading');
  var messages = [];
  var streamTimeout = null;

  function resetChat() {
    messages = [];
    Array.from(chatMessages.children).forEach(function (child) {
      if (child.id !== 'chat-suggested' && child.id !== 'chat-loading') {
        chatMessages.removeChild(child);
      }
    });
    chatSuggested.style.display = '';
    chatLoading.style.display = 'none';
  }

  // Sync the real AtomicChapter ID into chatPanel after the reading panel loads
  document.getElementById('reading-panel').addEventListener('htmx:afterSettle', function () {
    var chapterEl = document.querySelector('.chapter-inline[data-chapter-id]');
    if (chapterEl) {
      chatPanel.dataset.chapterId = chapterEl.dataset.chapterId;
    }
    resetChat();
    if (chapterEl && chapterEl.dataset.hasQuiz) {
      var chapterId = chapterEl.dataset.chapterId;
      chatSuggested.style.display = 'none';
      var quizDiv = document.createElement('div');
      quizDiv.innerHTML = '<div class="chat-loading" style="display:flex"><span class="spinner"></span><span>Loading quiz…</span></div>';
      quizDiv.setAttribute('hx-get', '/chapters/' + chapterId + '/quiz');
      quizDiv.setAttribute('hx-trigger', 'load');
      quizDiv.setAttribute('hx-swap', 'outerHTML');
      chatMessages.appendChild(quizDiv);
      htmx.process(quizDiv);
    }
  });

  // Suggested button click: populate input and submit
  chatSuggested.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-message]');
    if (!btn) return;
    chatInput.value = btn.dataset.message;
    chatForm.requestSubmit();
  });

  function appendMessage(role, content) {
    var div = document.createElement('div');
    div.className = 'chat-message chat-message--' + role;
    var inner = document.createElement('div');
    inner.className = 'chat-message-content';
    if (role === 'assistant') {
      inner.innerHTML = content;
    } else {
      inner.textContent = content;
    }
    div.appendChild(inner);
    chatMessages.insertBefore(div, chatLoading);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return inner;
  }

  chatForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var text = chatInput.value.trim();
    if (!text) return;

    // Hide suggested buttons after first message
    if (messages.length === 0) {
      chatSuggested.style.display = 'none';
    }

    messages.push({ role: 'user', content: text });
    appendMessage('user', text);
    chatInput.value = '';
    chatLoading.style.display = 'flex';

    var chapterId = chatPanel.dataset.chapterId || null;
    var body = JSON.stringify({ messages: messages, chapter_id: chapterId || null });

    var assistantContent = '';
    var assistantEl = null;

    // Timeout guard: 15s with no event → show error
    streamTimeout = setTimeout(function () {
      chatLoading.style.display = 'none';
      appendMessage('assistant', 'No response received. Please try again.');
    }, 15000);

    fetch('/topics/' + topicId + '/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body,
    }).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      function read() {
        reader.read().then(function (r) {
          if (r.done) {
            chatLoading.style.display = 'none';
            clearTimeout(streamTimeout);
            return;
          }
          clearTimeout(streamTimeout);
          streamTimeout = null;

          buffer += decoder.decode(r.value, { stream: true });
          var lines = buffer.split('\n');
          buffer = lines.pop();

          lines.forEach(function (line) {
            if (!line.startsWith('data: ')) return;
            var payload;
            try { payload = JSON.parse(line.slice(6)); } catch (ex) { return; }

            if (payload.syllabus_extend_confirm) {
              chatLoading.style.display = 'none';
              var extPrompt = payload.extension_prompt;
              var confirmDiv = document.createElement('div');
              confirmDiv.className = 'chat-extend-confirm';
              confirmDiv.innerHTML =
                '<button class="btn-primary btn-sm chat-extend-ok">Confirm</button>' +
                ' <button class="btn-secondary btn-sm chat-extend-cancel">Cancel</button>';

              confirmDiv.querySelector('.chat-extend-ok').addEventListener('click', function () {
                confirmDiv.remove();
                var fd = new FormData();
                fd.append('extension_prompt', extPrompt);
                fetch('/topics/' + topicId + '/syllabus/extend', { method: 'POST', body: fd })
                  .then(function () {
                    appendMessage('assistant', 'Extending the syllabus\u2026');
                    var pollInterval = setInterval(function () {
                      fetch('/topics/' + topicId + '/extend-status')
                        .then(function (r) { return r.json(); })
                        .then(function (data) {
                          if (data.status === 'complete') {
                            clearInterval(pollInterval);
                            htmx.ajax('GET', '/topics/' + topicId + '/syllabus', {
                              target: '#syllabus-items-list',
                              swap: 'innerHTML',
                            });
                          }
                        });
                    }, 3000);
                  });
              });

              confirmDiv.querySelector('.chat-extend-cancel').addEventListener('click', function () {
                confirmDiv.remove();
              });

              chatMessages.insertBefore(confirmDiv, chatLoading);
              chatMessages.scrollTop = chatMessages.scrollHeight;
              return;
            }

            if (payload.quiz_redirect) {
              chatLoading.style.display = 'none';
              chatMessages.innerHTML = '';
              var quizDiv = document.createElement('div');
              quizDiv.innerHTML = '<div class="chat-loading" style="display:flex"><span class="spinner"></span><span>Generating quiz…</span></div>';
              quizDiv.setAttribute('hx-get', payload.quiz_redirect);
              quizDiv.setAttribute('hx-trigger', 'load');
              quizDiv.setAttribute('hx-swap', 'outerHTML');
              chatMessages.appendChild(quizDiv);
              htmx.process(quizDiv);
              return;
            }

            if (payload.done) {
              chatLoading.style.display = 'none';
              if (assistantEl) {
                messages.push({ role: 'assistant', content: assistantContent });
              }
              return;
            }

            if (!assistantEl) {
              chatLoading.style.display = 'none';
              assistantEl = appendMessage('assistant', '');
            }
            assistantContent += payload.chunk;
            assistantEl.innerHTML = marked.parse(assistantContent);
          });
          read();
        }).catch(function () {
          chatLoading.style.display = 'none';
          appendMessage('assistant', 'An error occurred. Please try again.');
        });
      }
      read();
    }).catch(function () {
      chatLoading.style.display = 'none';
      clearTimeout(streamTimeout);
      appendMessage('assistant', 'Failed to connect. Please try again.');
    });
  });

  // Listen for quizComplete HTMX event to load result banner
  document.addEventListener('quizComplete', function () {
    var banner = document.getElementById('quiz-result-banner');
    if (banner) {
      htmx.ajax('GET', '/chapters/' + (chatPanel.dataset.chapterId || '') + '/quiz/result', {
        target: '#quiz-result-banner',
        swap: 'outerHTML',
      });
    }
  });
})();

// Syllabus active state: track which chapter is open
(function () {
  document.addEventListener('htmx:beforeRequest', function (e) {
    var elt = (e.detail && e.detail.elt) || e.target;
    if (!elt || !elt.dataset || !elt.dataset.opensChapter) return;
    var li = elt.closest('li.syllabus-child');
    if (!li) return;
    document.querySelectorAll('li.syllabus-child.is-active').forEach(function (el) {
      el.classList.remove('is-active');
    });
    li.classList.add('is-active');
  });
})();
