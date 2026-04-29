(function () {
  "use strict";

  let conversationId = null;
  const messageList = document.getElementById("message-list");
  const chatForm    = document.getElementById("chat-form");
  const queryInput  = document.getElementById("query-input");
  const sendBtn     = document.getElementById("send-btn");

  function getCsrfToken() {
    const cookie = document.cookie.split(";")
      .map(c => c.trim())
      .find(c => c.startsWith("csrftoken="));
    return cookie ? cookie.split("=")[1] : "";
  }

  function getSelectedSourceIds() {
    const select = document.getElementById("source-select");
    return Array.from(select.selectedOptions)
      .map(o => o.value)
      .filter(v => v !== "")
      .map(Number);
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  const SOURCE_TYPE_LABELS = { url: "URL", pdf: "PDF", markdown: "MD", json: "JSON" };
  const SOURCE_TYPE_CLASSES = { url: "src-url", pdf: "src-pdf", markdown: "src-md", json: "src-json" };

  function buildCitationBar(sources) {
    if (!sources || sources.length === 0) return null;

    const section = document.createElement("div");
    section.className = "citation-section";

    const header = document.createElement("div");
    header.className = "citation-section-header";
    header.textContent = "Sources";
    section.appendChild(header);

    const bar = document.createElement("div");
    bar.className = "citation-bar";

    sources.forEach((s, idx) => {
      const wrapper = document.createElement("div");
      wrapper.className = "citation-wrapper";

      // Chip — expanded by default
      const chip = document.createElement("button");
      chip.className = "citation-chip";
      chip.setAttribute("aria-expanded", "true");
      chip.type = "button";

      // Source-type dot badge
      const typeKey = (s.source_type || "").toLowerCase();
      const typeLabel = SOURCE_TYPE_LABELS[typeKey] || "SRC";
      const typeClass = SOURCE_TYPE_CLASSES[typeKey] || "src-url";
      const badge = document.createElement("span");
      badge.className = `src-badge ${typeClass}`;
      badge.textContent = typeLabel;

      const titleSpan = document.createElement("span");
      titleSpan.textContent = s.document_title || "Source";

      const chevron = document.createElement("span");
      chevron.className = "citation-chevron";
      chevron.textContent = "▴";

      chip.appendChild(badge);
      chip.appendChild(titleSpan);
      chip.appendChild(chevron);

      // Detail — visible by default
      const detail = document.createElement("div");
      detail.className = "citation-detail";

      if (s.snippet) {
        const snippet = document.createElement("p");
        snippet.className = "citation-snippet";
        snippet.textContent = s.snippet;
        detail.appendChild(snippet);
      }

      const footer = document.createElement("div");
      footer.className = "citation-footer";

      if (s.source_origin) {
        const origin = document.createElement("span");
        origin.className = "citation-origin";
        try {
          origin.textContent = new URL(s.source_origin).hostname;
        } catch {
          origin.textContent = s.source_origin;
        }
        footer.appendChild(origin);
      }

      if (s.citation_url) {
        const link = document.createElement("a");
        link.href = s.citation_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.className = "open-source-btn";
        link.textContent = "Open source ↗";
        footer.appendChild(link);
      }

      if (footer.hasChildNodes()) detail.appendChild(footer);

      chip.addEventListener("click", () => {
        const expanded = chip.getAttribute("aria-expanded") === "true";
        chip.setAttribute("aria-expanded", String(!expanded));
        detail.classList.toggle("collapsed");
        chevron.textContent = expanded ? "▾" : "▴";
      });

      wrapper.appendChild(chip);
      wrapper.appendChild(detail);
      bar.appendChild(wrapper);
    });

    section.appendChild(bar);
    return section;
  }

  function appendMessage(role, htmlContent, sources, confidence) {
    const wrapper = document.createElement("div");
    wrapper.className = `message message-${role}`;

    const header = document.createElement("div");
    header.className = "message-header";
    header.textContent = role === "user" ? "You" : "Assistant";

    if (role === "assistant" && confidence) {
      const badge = document.createElement("span");
      if (confidence === "low") {
        badge.className = "badge badge-low";
        badge.textContent = "⚠ Low confidence";
        header.appendChild(badge);
      } else if (confidence === "none") {
        badge.className = "badge badge-none";
        badge.textContent = "✗ Not found";
        header.appendChild(badge);
      }
    }

    const body = document.createElement("div");
    body.className = "message-body";
    body.innerHTML = htmlContent;

    wrapper.appendChild(header);
    wrapper.appendChild(body);

    if (role === "assistant") {
      const bar = buildCitationBar(sources);
      if (bar) wrapper.appendChild(bar);
    }

    messageList.appendChild(wrapper);
    wrapper.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  function appendThinking() {
    const wrapper = document.createElement("div");
    wrapper.className = "message message-assistant";
    wrapper.id = "thinking-msg";

    const header = document.createElement("div");
    header.className = "message-header";
    header.textContent = "Assistant";

    const body = document.createElement("div");
    body.className = "message-body";
    body.style.color = "var(--text-muted)";
    body.textContent = "Thinking…";

    wrapper.appendChild(header);
    wrapper.appendChild(body);
    messageList.appendChild(wrapper);
    wrapper.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  function removeThinking() {
    const el = document.getElementById("thinking-msg");
    if (el) el.remove();
  }

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = queryInput.value.trim();
    if (!question) return;

    queryInput.value = "";
    sendBtn.disabled = true;

    // Show user message
    appendMessage("user", `<p>${escapeHtml(question)}</p>`, null, null);
    appendThinking();

    const payload = {
      query: question,
      conversation_id: conversationId,
      source_ids: getSelectedSourceIds(),
    };

    try {
      const resp = await fetch("/api/chat/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(payload),
      });

      removeThinking();

      if (!resp.ok) {
        let friendlyMsg;
        if (resp.status === 503) {
          // LLM backend is down — show the specific message from the server
          try {
            const errData = await resp.json();
            friendlyMsg = errData.error || "The language model is unavailable.";
          } catch {
            friendlyMsg = "The language model is unavailable. Make sure Ollama is running (`ollama serve`) and the model is pulled.";
          }
        } else {
          friendlyMsg = `Something went wrong (HTTP ${resp.status}). Check the server logs for details.`;
        }
        appendMessage("assistant", `<p style="color:var(--danger)">${escapeHtml(friendlyMsg)}</p>`, null, "none");
        return;
      }

      const data = await resp.json();
      conversationId = data.conversation_id;

      const renderedHtml = marked.parse(data.answer || "");
      appendMessage("assistant", renderedHtml, data.sources, data.confidence);

    } catch (err) {
      removeThinking();
      appendMessage("assistant", `<p style="color:var(--danger)">Network error: ${escapeHtml(err.message)}</p>`, null, "none");
    } finally {
      sendBtn.disabled = false;
      queryInput.focus();
    }
  });

  // Enter submits; Shift+Enter inserts a newline
  queryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  });

})();
