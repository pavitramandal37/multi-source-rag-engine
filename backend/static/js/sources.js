(function () {
  "use strict";

  const tbody        = document.getElementById("sources-tbody");
  const statusEl     = document.getElementById("sources-status");
  const spinner      = document.getElementById("ingest-spinner");
  const resultEl     = document.getElementById("ingest-result");

  function getCsrfToken() {
    const cookie = document.cookie.split(";")
      .map(c => c.trim())
      .find(c => c.startsWith("csrftoken="));
    return cookie ? cookie.split("=")[1] : "";
  }

  function formatDate(iso) {
    return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
  }

  function typeBadge(type) {
    return `<span class="type-badge type-${type}">${type}</span>`;
  }

  function showStatus(msg, isError = false) {
    statusEl.textContent = msg;
    statusEl.className = "status-msg" + (isError ? " error" : "");
    statusEl.classList.remove("hidden");
  }

  function showResult(msg, isError = false) {
    resultEl.textContent = msg;
    resultEl.className = "ingest-result" + (isError ? " error" : " success");
    resultEl.classList.remove("hidden");
    setTimeout(() => resultEl.classList.add("hidden"), 6000);
  }

  // ── Load sources table ──────────────────────────────────────────────────────
  async function loadSources() {
    try {
      const resp = await fetch("/api/sources/", {
        headers: { "X-CSRFToken": getCsrfToken() },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const sources = await resp.json();

      if (sources.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">No sources yet. Add one below.</td></tr>';
        return;
      }

      tbody.innerHTML = sources.map(s => `
        <tr data-id="${s.id}">
          <td title="${s.name}">${s.name}</td>
          <td>${typeBadge(s.type)}</td>
          <td title="${s.origin}" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.origin}</td>
          <td>${s.document_count}</td>
          <td>${formatDate(s.created_at)}</td>
          <td><button class="delete-btn" data-id="${s.id}">Delete</button></td>
        </tr>
      `).join("");

    } catch (err) {
      showStatus("Failed to load sources: " + err.message, true);
      tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Error loading sources.</td></tr>';
    }
  }

  // ── Delete source ───────────────────────────────────────────────────────────
  tbody.addEventListener("click", async (e) => {
    const btn = e.target.closest(".delete-btn");
    if (!btn) return;

    const id = btn.dataset.id;
    if (!confirm("Delete this source and all its documents?")) return;

    btn.disabled = true;
    try {
      const resp = await fetch(`/api/sources/${id}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCsrfToken() },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const row = tbody.querySelector(`tr[data-id="${id}"]`);
      if (row) row.remove();
      if (tbody.children.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">No sources yet.</td></tr>';
      }
    } catch (err) {
      btn.disabled = false;
      showStatus("Delete failed: " + err.message, true);
    }
  });

  // ── Tab switching ───────────────────────────────────────────────────────────
  const tabBtns   = document.querySelectorAll(".tab-btn");
  const tabPanels = document.querySelectorAll(".tab-panel");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      tabBtns.forEach(b => {
        b.classList.toggle("active", b.dataset.tab === target);
        b.setAttribute("aria-selected", String(b.dataset.tab === target));
      });
      tabPanels.forEach(p => {
        p.classList.toggle("hidden", p.dataset.tab !== target);
        p.classList.toggle("active", p.dataset.tab === target);
      });
      resultEl.classList.add("hidden");
    });
  });

  // ── Helper: lock/unlock submit buttons ─────────────────────────────────────
  function setFormsDisabled(disabled) {
    document.querySelectorAll(".submit-btn").forEach(b => (b.disabled = disabled));
  }

  function startIngest() {
    spinner.classList.remove("hidden");
    resultEl.classList.add("hidden");
    setFormsDisabled(true);
  }

  function endIngest() {
    spinner.classList.add("hidden");
    setFormsDisabled(false);
  }

  // ── URL ingest ──────────────────────────────────────────────────────────────
  document.getElementById("form-url").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name  = document.getElementById("url-name").value.trim();
    const url   = document.getElementById("url-url").value.trim();
    const depth = parseInt(document.getElementById("url-depth").value, 10);
    if (!name || !url) return;

    startIngest();
    try {
      const resp = await fetch("/api/sources/ingest/url/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ name, url, crawl_depth: depth }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || data.error || JSON.stringify(data));
      showResult(`Done! Created ${data.documents_created} documents, ${data.chunks_created} chunks.`);
      await loadSources();
    } catch (err) {
      showResult("Ingest failed: " + err.message, true);
    } finally {
      endIngest();
    }
  });

  // ── PDF / Markdown ingest ───────────────────────────────────────────────────
  async function handleFileIngest(formEl, nameInputId, fileInputId) {
    const name = document.getElementById(nameInputId).value.trim();
    const file = document.getElementById(fileInputId).files[0];
    if (!name || !file) return;

    startIngest();
    const formData = new FormData();
    formData.append("name", name);
    formData.append("file", file);

    try {
      const resp = await fetch("/api/sources/ingest/file/", {
        method: "POST",
        headers: { "X-CSRFToken": getCsrfToken() },
        // Do NOT set Content-Type — browser sets multipart boundary
        body: formData,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || data.error || JSON.stringify(data));
      showResult(`Done! Created ${data.documents_created} documents, ${data.chunks_created} chunks.`);
      await loadSources();
    } catch (err) {
      showResult("Ingest failed: " + err.message, true);
    } finally {
      endIngest();
    }
  }

  document.getElementById("form-pdf").addEventListener("submit", (e) => {
    e.preventDefault();
    handleFileIngest(e.target, "pdf-name", "pdf-file");
  });

  document.getElementById("form-md").addEventListener("submit", (e) => {
    e.preventDefault();
    handleFileIngest(e.target, "md-name", "md-file");
  });

  // ── Init ────────────────────────────────────────────────────────────────────
  loadSources();

})();
