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

  function buildCitationBar(sources) {
    if (!sources || sources.length === 0) return null;
    const bar = document.createElement("div");
    bar.className = "citation-bar";

    sources.forEach(s => {
      const wrapper = document.createElement("div");

      const chip = document.createElement("button");
      chip.className = "citation-chip";
      chip.setAttribute("aria-expanded", "false");
      chip.textContent = s.document_title || "Source";
      chip.type = "button";

      const detail = document.createElement("div");
      detail.className = "citation-detail hidden";

      const snippet = document.createElement("p");
      snippet.className = "snippet";
      snippet.textContent = s.snippet || "";
      detail.appendChild(snippet);

      if (s.citation_url) {
        const link = document.createElement("a");
        link.href = s.citation_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.className = "open-source-btn";
        link.textContent = "Open source ↗";
        detail.appendChild(link);
      }

      chip.addEventListener("click", () => {
        const expanded = chip.getAttribute("aria-expanded") === "true";
        chip.setAttribute("aria-expanded", String(!expanded));
        detail.classList.toggle("hidden");
      });

      wrapper.appendChild(chip);
      wrapper.appendChild(detail);
      bar.appendChild(wrapper);
    });

    return bar;
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

  // Submit on Ctrl+Enter / Cmd+Enter
  queryInput.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  });

})();
