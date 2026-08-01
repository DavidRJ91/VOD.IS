/* VOD → YouTube — dispara el workflow de GitHub Actions, sube la miniatura si hace falta, y sigue el progreso. */
(() => {
  "use strict";

  const STORAGE_KEY = "vod2youtube.connection";
  const MAX_THUMB_BYTES = 2 * 1024 * 1024;

  const els = {
    form: document.getElementById("vodForm"),
    submitBtn: document.getElementById("submitBtn"),
    retryLastBtn: document.getElementById("retryLastBtn"),
    vodUrl: document.getElementById("vodUrl"),
    title: document.getElementById("title"),
    description: document.getElementById("description"),
    loadTemplateBtn: document.getElementById("loadTemplateBtn"),
    saveTemplateBtn: document.getElementById("saveTemplateBtn"),
    trimStart: document.getElementById("trimStart"),
    trimEnd: document.getElementById("trimEnd"),
    playlistId: document.getElementById("playlistId"),
    quality: document.getElementById("quality"),
    clipCount: document.getElementById("clipCount"),
    clipTimestamps: document.getElementById("clipTimestamps"),
    clipDuration: document.getElementById("clipDuration"),
    scheduleRow: document.getElementById("scheduleRow"),
    scheduledAt: document.getElementById("scheduledAt"),
    thumbAutoHint: document.getElementById("thumbAutoHint"),
    thumbFileRow: document.getElementById("thumbFileRow"),
    thumbUrlRow: document.getElementById("thumbUrlRow"),
    dropzone: document.getElementById("dropzone"),
    thumbFileInput: document.getElementById("thumbFileInput"),
    thumbPreview: document.getElementById("thumbPreview"),
    thumbPreviewImg: document.getElementById("thumbPreviewImg"),
    thumbPreviewInfo: document.getElementById("thumbPreviewInfo"),
    thumbPreviewRemove: document.getElementById("thumbPreviewRemove"),
    thumbnailUrl: document.getElementById("thumbnailUrl"),
    ghOwner: document.getElementById("ghOwner"),
    ghRepo: document.getElementById("ghRepo"),
    ghBranch: document.getElementById("ghBranch"),
    ghToken: document.getElementById("ghToken"),
    rememberToken: document.getElementById("rememberToken"),
    connectionDetails: document.getElementById("connectionDetails"),
    status: document.getElementById("status"),
    stopwatchTime: document.getElementById("stopwatchTime"),
    resultsGallery: document.getElementById("resultsGallery"),
    resultsList: document.getElementById("resultsList"),
    historyList: document.getElementById("historyList"),
  };

  const TEMPLATE_KEY = "vod2youtube.template";
  const LAST_SUBMISSION_KEY = "vod2youtube.lastSubmission";

  const WORKFLOW_FILE = "process-vod.yml";
  const STEP_TO_LAMP = {
    "Descargar VOD": "descarga",
    "Subir a YouTube": "youtube",
    "Notificar éxito": "discord",
    "Notificar fallo": "discord",
  };

  let selectedFile = null; // { name, size, base64, dataUrl }
  let stopwatchHandle = null;
  let stopwatchStartMs = null;

  // ---------------------------------------------------------------- helpers
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function setLamp(key, state) {
    const el = document.getElementById(`lamp-${key}`);
    if (!el) return;
    el.classList.remove("idle", "active", "done", "error");
    el.classList.add(state);
  }

  function resetLamps() {
    ["origen", "descarga", "youtube", "discord"].forEach((k) => setLamp(k, "idle"));
  }

  function setStatus(text, kind) {
    els.status.textContent = text;
    els.status.classList.remove("state-success", "state-error");
    if (kind) els.status.classList.add(`state-${kind}`);
  }

  function setStatusHtml(html, kind) {
    els.status.innerHTML = html;
    els.status.classList.remove("state-success", "state-error");
    if (kind) els.status.classList.add(`state-${kind}`);
  }

  function detectPlatform(url) {
    const lowered = url.toLowerCase();
    if (lowered.includes("twitch.tv")) return "twitch";
    if (lowered.includes("kick.com")) return "kick";
    return null;
  }

  function localDatetimeToUtcIso(value) {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return null;
    return d.toISOString().replace(/\.\d{3}Z$/, "Z");
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // ------------------------------------------------------------- stopwatch
  function formatElapsed(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    const pad = (n) => String(n).padStart(2, "0");
    return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
  }

  function startStopwatch() {
    stopwatchStartMs = Date.now();
    els.stopwatchTime.classList.remove("state-success", "state-error");
    els.stopwatchTime.textContent = "00:00";
    if (stopwatchHandle) clearInterval(stopwatchHandle);
    stopwatchHandle = setInterval(() => {
      els.stopwatchTime.textContent = formatElapsed(Date.now() - stopwatchStartMs);
    }, 1000);
  }

  function stopStopwatch(kind) {
    if (stopwatchHandle) clearInterval(stopwatchHandle);
    stopwatchHandle = null;
    if (stopwatchStartMs) {
      els.stopwatchTime.textContent = formatElapsed(Date.now() - stopwatchStartMs);
    }
    if (kind) els.stopwatchTime.classList.add(`state-${kind}`);
  }

  // ------------------------------------------------------------ modo oculto
  function isConfigMode() {
    return new URLSearchParams(location.search).has("config");
  }

  function applyConfigModeVisibility() {
    els.connectionDetails.classList.toggle("config-visible", isConfigMode());
  }

  // -------------------------------------------------------- auto-detección
  function autodetectOwnerRepo() {
    const host = location.hostname;
    const parts = location.pathname.split("/").filter(Boolean);
    if (host.endsWith(".github.io")) {
      return { owner: host.split(".")[0], repo: parts[0] || "" };
    }
    return { owner: "", repo: "" };
  }

  // ------------------------------------------------------- conexión (guardar)
  function loadConnection() {
    const detected = autodetectOwnerRepo();
    let saved = {};
    try {
      saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch (_) {
      saved = {};
    }
    els.ghOwner.value = saved.owner || detected.owner || "";
    els.ghRepo.value = saved.repo || detected.repo || "";
    els.ghBranch.value = saved.branch || "main";
    if (saved.token) els.ghToken.value = saved.token;
  }

  function persistConnection() {
    if (!els.rememberToken.checked) {
      localStorage.removeItem(STORAGE_KEY);
      return;
    }
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        owner: els.ghOwner.value.trim(),
        repo: els.ghRepo.value.trim(),
        branch: els.ghBranch.value.trim() || "main",
        token: els.ghToken.value.trim(),
      })
    );
  }

  // ---------------------------------------------------------- plantillas
  function saveTemplate() {
    localStorage.setItem(
      TEMPLATE_KEY,
      JSON.stringify({ title: els.title.value, description: els.description.value })
    );
    const original = els.saveTemplateBtn.textContent;
    els.saveTemplateBtn.textContent = "Guardado ✓";
    setTimeout(() => { els.saveTemplateBtn.textContent = original; }, 1500);
  }

  function loadTemplate() {
    let saved = null;
    try {
      saved = JSON.parse(localStorage.getItem(TEMPLATE_KEY) || "null");
    } catch (_) {
      saved = null;
    }
    if (!saved) {
      setStatus("Todavía no has guardado ninguna plantilla.");
      return;
    }
    els.title.value = saved.title || "";
    els.description.value = saved.description || "";
  }

  // ------------------------------------------------- reintentar el último envío
  function currentFormStateForRetry() {
    return {
      vodUrl: els.vodUrl.value.trim(),
      title: els.title.value.trim(),
      description: els.description.value.trim(),
      trimStart: els.trimStart.value.trim(),
      trimEnd: els.trimEnd.value.trim(),
      playlistId: els.playlistId.value.trim(),
      privacy: els.form.querySelector('input[name="privacy"]:checked').value,
      scheduledAt: els.scheduledAt.value,
      quality: els.quality.value,
      clipCount: els.clipCount.value,
      clipTimestamps: els.clipTimestamps.value.trim(),
      clipDuration: els.clipDuration.value,
      // La fuente "file" no se puede recordar (el archivo no cabe en localStorage
      // de forma razonable); al reintentar, como mucho se recupera la URL.
      thumbSource: currentThumbSource() === "file" ? "auto" : currentThumbSource(),
      thumbnailUrl: els.thumbnailUrl.value.trim(),
    };
  }

  function saveLastSubmission() {
    localStorage.setItem(LAST_SUBMISSION_KEY, JSON.stringify(currentFormStateForRetry()));
  }

  function applyFormState(state) {
    els.vodUrl.value = state.vodUrl || "";
    els.title.value = state.title || "";
    els.description.value = state.description || "";
    els.trimStart.value = state.trimStart || "";
    els.trimEnd.value = state.trimEnd || "";
    els.playlistId.value = state.playlistId || "";
    els.quality.value = state.quality || "1080";
    els.clipCount.value = state.clipCount || "0";
    els.clipTimestamps.value = state.clipTimestamps || "";
    els.clipDuration.value = state.clipDuration || "30";
    els.thumbnailUrl.value = state.thumbnailUrl || "";

    const privacyInput = document.getElementById(`privacy-${state.privacy || "unlisted"}`);
    if (privacyInput) privacyInput.checked = true;
    if (state.scheduledAt) els.scheduledAt.value = state.scheduledAt;

    const thumbInput = document.getElementById(`thumb-${state.thumbSource || "auto"}`);
    if (thumbInput) thumbInput.checked = true;

    togglePrivacyFields();
    toggleThumbFields();
  }

  function initRetryButton() {
    let saved = null;
    try {
      saved = JSON.parse(localStorage.getItem(LAST_SUBMISSION_KEY) || "null");
    } catch (_) {
      saved = null;
    }
    if (!saved) return;
    els.retryLastBtn.hidden = false;
    els.retryLastBtn.addEventListener("click", () => applyFormState(saved));
  }

  // ------------------------------------------------------------- historial
  function formatHistoryDate(iso) {
    try {
      return new Date(iso).toLocaleString();
    } catch (_) {
      return iso || "";
    }
  }

  function historyItemHtml(entry) {
    const ok = entry.outcome === "success";
    const titleHtml = ok && entry.video_url
      ? `<a class="history-item-title" href="${entry.video_url}" target="_blank" rel="noopener">${entry.title || entry.vod_url}</a>`
      : `<span class="history-item-title">${entry.title || entry.vod_url}</span>`;
    const clipsText = entry.clip_count ? ` · ${entry.clip_count} clip(s)` : "";
    return `
      <div class="history-item">
        <div class="history-item-main">
          ${titleHtml}
          <div class="history-item-meta">${formatHistoryDate(entry.timestamp)}${clipsText}</div>
        </div>
        <span class="history-item-status ${ok ? "success" : "failure"}">${ok ? "OK" : "Falló"}</span>
      </div>`;
  }

  async function loadHistory(conn) {
    if (!conn.owner || !conn.repo || !conn.token) {
      els.historyList.textContent = "Configura la conexión con GitHub (añadiendo ?config al enlace) para ver el historial.";
      return;
    }
    try {
      const url = `https://api.github.com/repos/${conn.owner}/${conn.repo}/contents/run_status/history.json?ref=${conn.branch}`;
      const res = await fetch(url, { headers: ghHeaders(conn.token, false) });
      if (res.status === 404) {
        els.historyList.textContent = "Todavía no hay envíos registrados.";
        return;
      }
      if (!res.ok) throw new Error(`GitHub respondió ${res.status}`);
      const data = await res.json();
      const bytes = Uint8Array.from(atob(data.content.replace(/\n/g, "")), (c) => c.charCodeAt(0));
      const history = JSON.parse(new TextDecoder("utf-8").decode(bytes));
      if (!history.length) {
        els.historyList.textContent = "Todavía no hay envíos registrados.";
        return;
      }
      els.historyList.innerHTML = history.slice().reverse().map(historyItemHtml).join("");
    } catch (err) {
      els.historyList.textContent = `No se pudo cargar el historial: ${err.message}`;
    }
  }

  // --------------------------------------------------------- llamadas a GitHub
  function ghHeaders(token, withContentType) {
    const headers = { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" };
    if (withContentType) headers["Content-Type"] = "application/json";
    return headers;
  }

  async function uploadThumbnailToRepo(conn, file, base64Content) {
    const ext = file.type === "image/png" ? "png" : "jpg";
    const path = `uploads/thumb-${Date.now()}.${ext}`;
    const url = `https://api.github.com/repos/${conn.owner}/${conn.repo}/contents/${path}`;
    const res = await fetch(url, {
      method: "PUT",
      headers: ghHeaders(conn.token, true),
      body: JSON.stringify({
        message: `chore: subir miniatura temporal (${path})`,
        content: base64Content,
        branch: conn.branch,
      }),
    });
    if (!res.ok) {
      let detail = "";
      try {
        detail = (await res.json()).message || "";
      } catch (_) {
        /* sin cuerpo JSON */
      }
      throw new Error(`No se pudo subir la miniatura (GitHub respondió ${res.status}${detail ? `: ${detail}` : ""}).`);
    }
    return path;
  }

  async function dispatchWorkflow(conn, inputs) {
    const url = `https://api.github.com/repos/${conn.owner}/${conn.repo}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
    const res = await fetch(url, {
      method: "POST",
      headers: ghHeaders(conn.token, true),
      body: JSON.stringify({ ref: conn.branch, inputs }),
    });
    if (res.status !== 204) {
      let detail = "";
      try {
        detail = (await res.json()).message || "";
      } catch (_) {
        /* sin cuerpo JSON */
      }
      throw new Error(`GitHub respondió ${res.status}${detail ? `: ${detail}` : ""}.`);
    }
  }

  async function findLatestRun(conn, sinceMs) {
    const url = `https://api.github.com/repos/${conn.owner}/${conn.repo}/actions/workflows/${WORKFLOW_FILE}/runs?per_page=5`;
    const res = await fetch(url, { headers: ghHeaders(conn.token, false) });
    if (!res.ok) throw new Error(`GitHub respondió ${res.status} al buscar la ejecución.`);
    const data = await res.json();
    const candidates = (data.workflow_runs || []).filter(
      (r) => new Date(r.created_at).getTime() >= sinceMs - 5000
    );
    candidates.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    return candidates[0] || null;
  }

  async function fetchJobs(conn, runId) {
    const url = `https://api.github.com/repos/${conn.owner}/${conn.repo}/actions/runs/${runId}/jobs`;
    const res = await fetch(url, { headers: ghHeaders(conn.token, false) });
    if (!res.ok) throw new Error(`GitHub respondió ${res.status} al leer los pasos.`);
    return res.json();
  }

  function lampStateForStep(step) {
    if (step.status === "completed") return step.conclusion === "success" ? "done" : "error";
    if (step.status === "in_progress") return "active";
    return "idle";
  }

  async function fetchResultFromRepo(conn, runId) {
    const path = `run_status/${runId}.json`;
    const url = `https://api.github.com/repos/${conn.owner}/${conn.repo}/contents/${path}?ref=${conn.branch}`;
    const res = await fetch(url, { headers: ghHeaders(conn.token, false) });
    if (res.status === 404) return null; // el paso "Publicar resultado" no llegó a correr (p. ej. sin clips y sin querer galería)
    if (!res.ok) throw new Error(`GitHub respondió ${res.status} al leer el resultado.`);
    const data = await res.json();
    const bytes = Uint8Array.from(atob(data.content.replace(/\n/g, "")), (c) => c.charCodeAt(0));
    const decoded = new TextDecoder("utf-8").decode(bytes);
    return { payload: JSON.parse(decoded), sha: data.sha, path };
  }

  async function deleteFromRepo(conn, path, sha) {
    const url = `https://api.github.com/repos/${conn.owner}/${conn.repo}/contents/${path}`;
    await fetch(url, {
      method: "DELETE",
      headers: ghHeaders(conn.token, true),
      body: JSON.stringify({ message: `chore: limpiar archivo temporal (${path})`, sha, branch: conn.branch }),
    });
    // Si falla la limpieza no pasa nada grave: es un archivo temporal, y el próximo envío usa otra ruta.
  }

  function formatMB(bytes) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatClipTimestamp(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  async function loadClip(conn, clip, container) {
    const loadBtn = container.querySelector(".clip-load-btn");
    const originalText = loadBtn.textContent;
    loadBtn.disabled = true;
    loadBtn.textContent = "Cargando…";
    try {
      const url = `https://api.github.com/repos/${conn.owner}/${conn.repo}/contents/${clip.repo_path}?ref=${conn.branch}`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${conn.token}`, Accept: "application/vnd.github.raw+json" },
      });
      if (!res.ok) throw new Error(`GitHub respondió ${res.status} al cargar el clip.`);
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const filename = clip.repo_path.split("/").pop();

      const video = document.createElement("video");
      video.controls = true;
      video.src = objectUrl;
      video.className = "clip-player";

      const downloadLink = document.createElement("a");
      downloadLink.href = objectUrl;
      downloadLink.download = filename;
      downloadLink.className = "clip-download-link";
      downloadLink.textContent = "Descargar";

      loadBtn.remove();
      container.append(video, downloadLink);

      // Ya tenemos el clip en el navegador (como blob): no hace falta dejarlo
      // en el repositorio ni un segundo más.
      await deleteFromRepo(conn, clip.repo_path, clip.sha);
    } catch (err) {
      loadBtn.disabled = false;
      loadBtn.textContent = originalText;
      setStatus(`No se pudo cargar el clip: ${err.message}`, "error");
    }
  }

  function resultItemHtml(label, videoId, videoUrl, title) {
    const thumb = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
    return `
      <div class="result-item">
        <img src="${thumb}" alt="" loading="lazy" onerror="this.style.visibility='hidden'" />
        <div class="result-item-info">
          <p class="result-item-label">${label}</p>
          <a href="${videoUrl}" target="_blank" rel="noopener">${title || videoUrl}</a>
        </div>
      </div>`;
  }

  function buildClipItem(conn, clip, index) {
    const item = document.createElement("div");
    item.className = "result-item clip-item";

    const label = document.createElement("p");
    label.className = "result-item-label";
    label.textContent = `Clip ${index + 1} — empieza en ${formatClipTimestamp(clip.start_seconds)} · ${formatMB(clip.size_bytes || 0)}`;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "clip-load-btn";
    btn.textContent = "Cargar y reproducir";
    btn.addEventListener("click", () => loadClip(conn, clip, item));

    item.append(label, btn);
    return item;
  }

  function renderResults(conn, payload) {
    els.resultsList.innerHTML = "";
    let hasContent = false;

    if (payload.main) {
      const mainWrap = document.createElement("div");
      mainWrap.innerHTML = resultItemHtml(
        "Vídeo completo",
        payload.main.video_id,
        payload.main.video_url,
        payload.main.title
      );
      els.resultsList.appendChild(mainWrap.firstElementChild);
      hasContent = true;
    }

    (payload.clips || []).forEach((clip, i) => {
      els.resultsList.appendChild(buildClipItem(conn, clip, i));
      hasContent = true;
    });

    if (!hasContent) return;
    els.resultsGallery.hidden = false;
    els.resultsGallery.classList.add("visible");
  }

  async function loadAndShowResults(conn, runId) {
    try {
      const found = await fetchResultFromRepo(conn, runId);
      if (!found) {
        setStatus("Completado, pero no encontré datos de resultado para mostrar la galería (¿acabó bien el paso «Publicar resultado»?).");
        return;
      }
      renderResults(conn, found.payload);
      await deleteFromRepo(conn, found.path, found.sha);
    } catch (err) {
      setStatus(`Completado, pero no se pudo cargar la galería de resultados: ${err.message}`, "error");
    }
  }

  // ------------------------------------------------------------- seguimiento
  async function pollRun(conn, run) {
    setStatusHtml(`En marcha — <a href="${run.html_url}" target="_blank" rel="noopener">ver registro en GitHub</a>`);

    const maxIterations = 5100; // ~340 min a 4s por vuelta, igual que el timeout del workflow
    for (let i = 0; i < maxIterations; i += 1) {
      await sleep(4000);

      let jobs;
      try {
        jobs = await fetchJobs(conn, run.id);
      } catch (err) {
        setStatus(`Aviso: no se pudo leer el estado (${err.message}). Reintentando…`);
        continue;
      }

      const job = (jobs.jobs || [])[0];
      if (!job) continue;

      (job.steps || []).forEach((step) => {
        const lampKey = STEP_TO_LAMP[step.name];
        if (lampKey) setLamp(lampKey, lampStateForStep(step));
      });

      if (job.status === "completed") {
        const ok = job.conclusion === "success";
        stopStopwatch(ok ? "success" : "error");
        setStatusHtml(
          `${ok ? "Completado ✅" : "Falló ❌"} — <a href="${run.html_url}" target="_blank" rel="noopener">ver registro</a>. Discord ya debería tener el aviso.`,
          ok ? "success" : "error"
        );
        if (ok) await loadAndShowResults(conn, run.id);
        return;
      }
    }

    setStatus("Dejé de seguirlo tras un buen rato — revisa el enlace de arriba o Discord para el resultado final.");
  }

  // ---------------------------------------------------------- miniatura UI
  function currentThumbSource() {
    return els.form.querySelector('input[name="thumbSource"]:checked').value;
  }

  function toggleThumbFields() {
    const value = currentThumbSource();
    els.thumbAutoHint.style.display = value === "auto" ? "block" : "none";
    els.thumbFileRow.classList.toggle("visible", value === "file");
    els.thumbUrlRow.classList.toggle("visible", value === "url");
  }

  function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(",")[1]);
      reader.onerror = () => reject(new Error("No se pudo leer el archivo."));
      reader.readAsDataURL(file);
    });
  }

  async function handleFileSelected(file) {
    if (!file) return;
    if (!["image/jpeg", "image/png"].includes(file.type)) {
      setStatus("La imagen debe ser JPG o PNG.", "error");
      return;
    }
    if (file.size > MAX_THUMB_BYTES) {
      setStatus("La imagen pesa más de 2MB — elige una más ligera.", "error");
      return;
    }
    const base64 = await readFileAsBase64(file);
    selectedFile = { name: file.name, size: file.size, type: file.type, base64 };
    els.thumbPreviewImg.src = `data:${file.type};base64,${base64}`;
    els.thumbPreviewInfo.textContent = `${file.name} — ${formatBytes(file.size)}`;
    els.thumbPreview.classList.add("visible");
  }

  function clearSelectedFile() {
    selectedFile = null;
    els.thumbFileInput.value = "";
    els.thumbPreview.classList.remove("visible");
    els.thumbPreviewImg.src = "";
  }

  // ------------------------------------------------------------------ envío
  async function handleSubmit(event) {
    event.preventDefault();

    const vodUrl = els.vodUrl.value.trim();
    const platform = detectPlatform(vodUrl);
    if (!platform) {
      setStatus("Ese enlace no parece ser de Twitch ni de Kick.", "error");
      return;
    }

    const thumbSource = currentThumbSource();
    if (thumbSource === "file" && !selectedFile) {
      setStatus("Elige una imagen, o cambia a «Automática»/«Desde URL».", "error");
      return;
    }
    if (thumbSource === "url" && !els.thumbnailUrl.value.trim()) {
      setStatus("Pega una URL de imagen, o cambia a «Automática»/«Subir imagen».", "error");
      return;
    }

    const privacy = els.form.querySelector('input[name="privacy"]:checked').value;
    let scheduledAtIso = "";
    if (privacy === "scheduled") {
      if (!els.scheduledAt.value) {
        setStatus("Elige fecha y hora para la publicación programada.", "error");
        return;
      }
      scheduledAtIso = localDatetimeToUtcIso(els.scheduledAt.value);
      if (!scheduledAtIso || new Date(scheduledAtIso).getTime() <= Date.now()) {
        setStatus("La fecha/hora programada debe ser futura.", "error");
        return;
      }
    }

    const conn = {
      owner: els.ghOwner.value.trim(),
      repo: els.ghRepo.value.trim(),
      branch: els.ghBranch.value.trim() || "main",
      token: els.ghToken.value.trim(),
    };
    if (!conn.owner || !conn.repo || !conn.token) {
      setStatus("Completa usuario, repositorio y token en «Conexión con GitHub».", "error");
      els.connectionDetails.open = true;
      return;
    }
    persistConnection();
    saveLastSubmission();

    resetLamps();
    setLamp("origen", "done");
    els.submitBtn.disabled = true;
    els.resultsGallery.hidden = true;
    els.resultsGallery.classList.remove("visible");
    els.resultsList.innerHTML = "";
    startStopwatch();
    setStatus("Enviando a GitHub…");

    try {
      let thumbnailUrlInput = "";
      let thumbnailRepoPathInput = "";

      if (thumbSource === "file") {
        setStatus("Subiendo la miniatura a tu repositorio…");
        thumbnailRepoPathInput = await uploadThumbnailToRepo(conn, selectedFile, selectedFile.base64);
      } else if (thumbSource === "url") {
        thumbnailUrlInput = els.thumbnailUrl.value.trim();
      }

      const inputs = {
        vod_url: vodUrl,
        title: els.title.value.trim(),
        description: els.description.value.trim(),
        privacy,
        scheduled_at: scheduledAtIso,
        quality: els.quality.value,
        trim_start: els.trimStart.value.trim(),
        trim_end: els.trimEnd.value.trim(),
        playlist_id: els.playlistId.value.trim(),
        clip_count: String(Math.max(0, Math.min(10, parseInt(els.clipCount.value, 10) || 0))),
        clip_timestamps: els.clipTimestamps.value.trim(),
        clip_duration: els.clipDuration.value,
        thumbnail_url: thumbnailUrlInput,
        thumbnail_repo_path: thumbnailRepoPathInput,
      };

      setStatus("Enviando a GitHub…");
      const dispatchedAtMs = Date.now();
      await dispatchWorkflow(conn, inputs);

      let run = null;
      for (let attempt = 0; attempt < 10 && !run; attempt += 1) {
        await sleep(2000);
        run = await findLatestRun(conn, dispatchedAtMs);
      }
      if (!run) {
        stopStopwatch("error");
        setStatus(
          "Se envió, pero no encontré la ejecución en GitHub todavía. Revisa la pestaña Actions de tu repositorio.",
          "error"
        );
        return;
      }

      await pollRun(conn, run);
    } catch (err) {
      stopStopwatch("error");
      setStatus(`Error: ${err.message}`, "error");
    } finally {
      els.submitBtn.disabled = false;
    }
  }

  // ------------------------------------------------------------------- init
  function togglePrivacyFields() {
    const value = els.form.querySelector('input[name="privacy"]:checked').value;
    els.scheduleRow.classList.toggle("visible", value === "scheduled");
  }

  function initDropzone() {
    els.thumbFileInput.addEventListener("change", () => {
      handleFileSelected(els.thumbFileInput.files[0]);
    });
    ["dragenter", "dragover"].forEach((evt) => {
      els.dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        els.dropzone.classList.add("dragover");
      });
    });
    ["dragleave", "drop"].forEach((evt) => {
      els.dropzone.addEventListener(evt, (e) => {
        e.preventDefault();
        els.dropzone.classList.remove("dragover");
      });
    });
    els.dropzone.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) handleFileSelected(file);
    });
    els.thumbPreviewRemove.addEventListener("click", clearSelectedFile);
  }

  function init() {
    loadConnection();
    applyConfigModeVisibility();
    resetLamps();
    els.stopwatchTime.textContent = "00:00";

    els.form.querySelectorAll('input[name="privacy"]').forEach((el) => {
      el.addEventListener("change", togglePrivacyFields);
    });
    togglePrivacyFields();

    els.form.querySelectorAll('input[name="thumbSource"]').forEach((el) => {
      el.addEventListener("change", toggleThumbFields);
    });
    toggleThumbFields();
    initDropzone();

    els.saveTemplateBtn.addEventListener("click", saveTemplate);
    els.loadTemplateBtn.addEventListener("click", loadTemplate);
    initRetryButton();

    els.form.addEventListener("submit", handleSubmit);

    loadHistory({
      owner: els.ghOwner.value.trim(),
      repo: els.ghRepo.value.trim(),
      branch: els.ghBranch.value.trim() || "main",
      token: els.ghToken.value.trim(),
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
