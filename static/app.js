// ── maisuclaw — frontend logic v0.3 ──────────────────────
// Keeps all v0.2 functionality (streaming, voice, model select)
// and adds: file upload / drag-drop, Ctrl+V paste, ETA display,
// research mode, inline image display, enhanced markdown.
(function () {
  "use strict";

  // ═══════════════════════════════════════════════════════
  //  STATE
  // ═══════════════════════════════════════════════════════

  let sessionId = null;
  let isRecording = false;
  let mediaRecorder = null;
  let audioChunks = [];
  let isGenerating = false;   // prevent double-send
  let modelOptions = {};       // populated from /info

  /** Files queued for upload: [{file: File, dataUrl: string|null}] */
  let pendingFiles = [];

  /** Counter for unique preview IDs so we can remove individual items */
  let previewIdCounter = 0;

  // ═══════════════════════════════════════════════════════
  //  DOM REFERENCES
  // ═══════════════════════════════════════════════════════

  const $messages       = document.getElementById("messages");
  const $input          = document.getElementById("user-input");
  const $sendBtn        = document.getElementById("send-btn");
  const $voiceBtn       = document.getElementById("voice-btn");
  const $sidebar        = document.getElementById("sidebar");
  const $sidebarToggle  = document.getElementById("sidebar-toggle");
  const $newChatBtn     = document.getElementById("new-chat-btn");
  const $sessionList    = document.getElementById("session-list");
  const $modelSelect    = document.getElementById("model-select");
  const $sessionTitle   = document.getElementById("session-title");
  const $modelBadge     = document.getElementById("model-badge");
  const $chatContainer  = document.getElementById("chat-container");
  const $backupIndicator= document.getElementById("backup-indicator");

  // v0.3 DOM refs
  const $uploadBtn      = document.getElementById("upload-btn");
  const $fileInput      = document.getElementById("file-input");
  const $researchBtn    = document.getElementById("research-btn");
  const $dropZone       = document.getElementById("drop-zone");
  const $previewArea    = document.getElementById("preview-area");
  const $previewList    = document.getElementById("preview-list");

  // ═══════════════════════════════════════════════════════
  //  INIT
  // ═══════════════════════════════════════════════════════

  async function init() {
    showWelcome();
    await fetchServerInfo();
    setupEventListeners();
  }

  // ═══════════════════════════════════════════════════════
  //  WELCOME SCREEN
  // ═══════════════════════════════════════════════════════

  function showWelcome() {
    $messages.innerHTML = `
      <div class="welcome">
        <h1>maisuclaw</h1>
        <p>Your personal AI assistant running entirely on your laptop.<br>
        Streaming responses. Multiple models. Tools. Voice. File upload. Research. GitHub backup.</p>
        <div class="shortcuts">
          <div class="shortcut" data-msg="List the files on my Desktop">Browse files</div>
          <div class="shortcut" data-msg="Write a Python script that sorts a list">Code example</div>
          <div class="shortcut" data-msg="What is 15% of 2340?">Quick math</div>
          <div class="shortcut" data-msg="Explain quantum computing step by step">Deep answer</div>
          <div class="shortcut" data-msg="Research the latest developments in renewable energy" data-research="1">Research</div>
        </div>
      </div>
    `;

    document.querySelectorAll(".shortcut").forEach((el) => {
      el.addEventListener("click", () => {
        $input.value = el.dataset.msg;
        if (el.dataset.research) {
          startResearch(el.dataset.msg);
        } else {
          sendMessage();
        }
      });
    });
  }

  // ═══════════════════════════════════════════════════════
  //  SERVER INFO
  // ═══════════════════════════════════════════════════════

  async function fetchServerInfo() {
    try {
      const resp = await fetch("/info");
      const data = await resp.json();

      // Populate model selector
      modelOptions = data.model_options || {};
      $modelSelect.innerHTML = "";
      for (const [key, label] of Object.entries(modelOptions)) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = label;
        $modelSelect.appendChild(opt);
      }

      // Show available models in sidebar
      if (data.models && data.models.length > 0) {
        $modelBadge.innerHTML = data.models.map((m) => `<span>${m}</span>`).join("");
      } else {
        $modelBadge.textContent = "No models found — start Ollama";
      }

      // Backup status
      if (data.backup && data.backup.configured) {
        $backupIndicator.className = "backup-on";
        $backupIndicator.title = `GitHub backup: ${data.backup.repo}`;
      } else {
        $backupIndicator.className = "backup-off";
        $backupIndicator.title = "GitHub backup not configured";
      }
    } catch (e) {
      $modelBadge.textContent = "Cannot reach backend";
    }
  }

  // ═══════════════════════════════════════════════════════
  //  EVENT LISTENERS
  // ═══════════════════════════════════════════════════════

  function setupEventListeners() {
    // ── Core v0.2 ──
    $sendBtn.addEventListener("click", handleSend);
    $input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    $input.addEventListener("input", () => {
      $input.style.height = "auto";
      $input.style.height = Math.min($input.scrollHeight, 150) + "px";
    });

    $sidebarToggle.addEventListener("click", () => {
      $sidebar.classList.toggle("hidden");
    });

    $newChatBtn.addEventListener("click", () => {
      sessionId = null;
      $sessionTitle.textContent = "New Conversation";
      clearPendingFiles();
      showWelcome();
    });

    $voiceBtn.addEventListener("click", toggleVoiceRecording);

    // ── v0.3: Upload button → trigger hidden file input ──
    $uploadBtn.addEventListener("click", () => {
      $fileInput.click();
    });

    $fileInput.addEventListener("change", (e) => {
      const files = Array.from(e.target.files);
      if (files.length > 0) {
        addFilesToPreview(files);
      }
      // Reset so re-selecting the same file fires change again
      $fileInput.value = "";
    });

    // ── v0.3: Research button ──
    $researchBtn.addEventListener("click", () => {
      const text = $input.value.trim();
      if (!text) {
        $input.focus();
        $input.placeholder = "Type a research question first...";
        return;
      }
      startResearch(text);
    });

    // ── v0.3: Drag & drop ──
    let dragCounter = 0; // track nested drag enter/leave

    document.addEventListener("dragenter", (e) => {
      e.preventDefault();
      dragCounter++;
      $dropZone.classList.add("active");
    });

    document.addEventListener("dragleave", (e) => {
      e.preventDefault();
      dragCounter--;
      if (dragCounter <= 0) {
        dragCounter = 0;
        $dropZone.classList.remove("active");
      }
    });

    document.addEventListener("dragover", (e) => {
      e.preventDefault();
    });

    document.addEventListener("drop", (e) => {
      e.preventDefault();
      dragCounter = 0;
      $dropZone.classList.remove("active");

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        addFilesToPreview(files);
      }
    });

    // ── v0.3: Ctrl+V paste screenshots ──
    document.addEventListener("paste", handlePaste);
  }

  // ═══════════════════════════════════════════════════════
  //  FILE PREVIEW MANAGEMENT
  // ═══════════════════════════════════════════════════════

  /**
   * Add files (from upload or drop) to the preview area.
   * For images, we read a data URL for the thumbnail.
   * For other files, we just show the extension.
   */
  function addFilesToPreview(files) {
    files.forEach((file) => {
      const entry = { file, id: ++previewIdCounter, dataUrl: null };

      if (file.type.startsWith("image/")) {
        // Read image as data URL for thumbnail preview
        const reader = new FileReader();
        reader.onload = (e) => {
          entry.dataUrl = e.target.result;
          renderPreviewThumb(entry);
        };
        reader.readAsDataURL(file);
      } else {
        // Non-image: just show file icon
        renderPreviewThumb(entry);
      }

      pendingFiles.push(entry);
    });

    refreshPreviewArea();
  }

  /**
   * Render a single thumbnail into the preview list.
   */
  function renderPreviewThumb(entry) {
    // Remove existing thumb for this entry if re-rendering
    const existing = $previewList.querySelector(`[data-id="${entry.id}"]`);
    if (existing) existing.remove();

    const thumb = document.createElement("div");
    thumb.className = "preview-thumb";
    thumb.dataset.id = entry.id;

    if (entry.dataUrl) {
      // Image preview
      thumb.innerHTML = `
        <img src="${entry.dataUrl}" alt="${escapeAttr(entry.file.name)}">
        <button class="remove-btn" title="Remove">&times;</button>
      `;
    } else {
      // File preview (PDF, txt, etc.)
      const ext = entry.file.name.split(".").pop().toUpperCase();
      thumb.innerHTML = `
        <div class="file-icon">${ext}</div>
        <button class="remove-btn" title="Remove">&times;</button>
      `;
    }

    // Wire the remove button
    thumb.querySelector(".remove-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      removePendingFile(entry.id);
    });

    $previewList.appendChild(thumb);
  }

  /**
   * Remove a pending file by its preview ID.
   */
  function removePendingFile(id) {
    pendingFiles = pendingFiles.filter((f) => f.id !== id);
    const thumb = $previewList.querySelector(`[data-id="${id}"]`);
    if (thumb) thumb.remove();
    refreshPreviewArea();
  }

  /**
   * Show / hide the preview area based on whether there are pending files.
   */
  function refreshPreviewArea() {
    if (pendingFiles.length > 0) {
      $previewArea.style.display = "block";
    } else {
      $previewArea.style.display = "none";
    }
  }

  /**
   * Clear all pending file previews.
   */
  function clearPendingFiles() {
    pendingFiles = [];
    $previewList.innerHTML = "";
    refreshPreviewArea();
  }

  // ═══════════════════════════════════════════════════════
  //  CLIPBOARD PASTE (Ctrl+V)
  // ═══════════════════════════════════════════════════════

  function handlePaste(e) {
    // Don't intercept paste when user is typing in input (let default happen)
    // unless there's an image in the clipboard.
    const items = Array.from(e.clipboardData.items || []);
    const imageItem = items.find((item) => item.type.startsWith("image/"));

    if (!imageItem) return; // No image — let normal text paste happen

    e.preventDefault();

    const blob = imageItem.getAsFile();
    if (!blob) return;

    // Give the pasted image a descriptive name
    const now = new Date();
    const timestamp = `${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
    const file = new File([blob], `screenshot-${timestamp}.png`, { type: blob.type });

    addFilesToPreview([file]);
  }

  function pad(n) { return n < 10 ? "0" + n : "" + n; }

  // ═══════════════════════════════════════════════════════
  //  SEND HANDLER (dispatches to chat, upload, or research)
  // ═══════════════════════════════════════════════════════

  function handleSend() {
    if (isGenerating) return;

    const text = $input.value.trim();

    // If we have pending files, use the upload flow
    if (pendingFiles.length > 0) {
      sendWithFiles(text || "Analyze this file");
      return;
    }

    // If no text and no files, do nothing
    if (!text) return;

    sendMessage(text);
  }

  // ═══════════════════════════════════════════════════════
  //  SEND MESSAGE (STREAMING) — enhanced with ETA
  // ═══════════════════════════════════════════════════════

  async function sendMessage(text) {
    if (typeof text !== "string") text = $input.value.trim();
    if (!text || isGenerating) return;

    isGenerating = true;
    $input.value = "";
    $input.style.height = "auto";
    $input.placeholder = "Ask maisuclaw anything... (Ctrl+V to paste screenshot)";
    $sendBtn.disabled = true;

    // Remove welcome screen
    const welcome = $messages.querySelector(".welcome");
    if (welcome) welcome.remove();

    // Add user bubble
    appendMessage("user", text);

    // Create assistant bubble for streaming
    const bubbleDiv = createStreamingBubble();

    try {
      const resp = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          mode: $modelSelect.value,
        }),
      });

      if (!resp.ok) throw new Error(`Server error: ${resp.status}`);

      await processSSEStream(resp, bubbleDiv);
    } catch (e) {
      updateStreamingBubble(bubbleDiv, "Connection error — is the server running?");
      finalizeStreamingBubble(bubbleDiv, "Connection error", "");
    } finally {
      isGenerating = false;
      $sendBtn.disabled = false;
      $input.focus();
    }
  }

  // ═══════════════════════════════════════════════════════
  //  SEND WITH FILES (upload endpoint)
  // ═══════════════════════════════════════════════════════

  async function sendWithFiles(prompt) {
    if (isGenerating || pendingFiles.length === 0) return;

    isGenerating = true;
    const text = $input.value.trim() || prompt;
    $input.value = "";
    $input.style.height = "auto";
    $sendBtn.disabled = true;

    // Remove welcome screen
    const welcome = $messages.querySelector(".welcome");
    if (welcome) welcome.remove();

    // Collect the files and their data URLs for user bubble display
    const filesToSend = [...pendingFiles];
    const imageDataUrls = filesToSend
      .filter((f) => f.file.type.startsWith("image/"))
      .map((f) => f.dataUrl);
    const firstFileName = filesToSend[0].file.name;
    const firstFileType = filesToSend[0].file.type;

    // Build user bubble with optional inline image
    let userContent = text;
    if (imageDataUrls.length > 0) {
      // For simplicity, show the first image inline in the user bubble
      userContent = `<img class="chat-image" src="${imageDataUrls[0]}" alt="${escapeAttr(firstFileName)}">` +
                    (text !== "Analyze this file" ? escapeHtml(text) : `📎 ${escapeHtml(firstFileName)}`);
    } else {
      userContent = `📎 ${escapeHtml(firstFileName)}${text !== "Analyze this file" ? "\n" + escapeHtml(text) : ""}`;
    }

    appendMessage("user", userContent, null, true); // true = isHtml

    clearPendingFiles();

    // Create assistant bubble for streaming the response
    const bubbleDiv = createStreamingBubble();

    try {
      // Upload the first file (single-file endpoint)
      const formData = new FormData();
      formData.append("file", filesToSend[0].file);
      formData.append("prompt", text);

      const resp = await fetch("/upload", {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.error || `Upload error: ${resp.status}`);
      }

      const result = await resp.json();

      // Build response content based on file type
      let replyHtml = "";

      // Show a badge for the file type
      if (result.type === "pdf") {
        replyHtml += `<div class="file-badge">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          PDF &bull; ${result.pages || "?"} pages
        </div>`;
      } else if (result.type === "image") {
        replyHtml += `<div class="file-badge">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
          Image &bull; ${escapeHtml(result.filename || firstFileName)}
        </div>`;
      } else {
        replyHtml += `<div class="file-badge">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          File &bull; ${escapeHtml(result.filename || firstFileName)}
        </div>`;
      }

      // Show the image inline if it was an image analysis
      if (result.type === "image" && imageDataUrls.length > 0) {
        replyHtml += `<img class="chat-image" src="${imageDataUrls[0]}" alt="${escapeAttr(result.filename || "Uploaded image")}">`;
      }

      // The AI reply
      replyHtml += formatMessage(result.reply || "No response.");

      updateStreamingBubble(bubbleDiv, replyHtml);
      finalizeStreamingBubble(bubbleDiv, replyHtml, result.model || "");

    } catch (e) {
      updateStreamingBubble(bubbleDiv, `Error: ${e.message}`);
      finalizeStreamingBubble(bubbleDiv, `Error: ${e.message}`, "");
    } finally {
      isGenerating = false;
      $sendBtn.disabled = false;
      $input.focus();
    }
  }

  // ═══════════════════════════════════════════════════════
  //  SSE STREAM PROCESSOR (shared between chat & research)
  // ═══════════════════════════════════════════════════════

  /**
   * Read an SSE response body and dispatch events to update a streaming bubble.
   * Handles: eta, token, tool, tool_result, done, error.
   * Returns the full reply text and model used.
   */
  async function processSSEStream(resp, bubbleDiv) {
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullReply = "";
    let modelUsed = "";
    let etaShown = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";  // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const jsonStr = line.slice(6).trim();
        if (jsonStr === "[DONE]") break;

        try {
          const event = JSON.parse(jsonStr);

          switch (event.type) {
            case "eta":
              // Show ETA bar above the typing indicator
              if (!etaShown) {
                showEtaBar(bubbleDiv, event.seconds, event.label);
                etaShown = true;
              }
              break;

            case "token":
              // Hide ETA on first token
              if (etaShown) {
                hideEtaBar(bubbleDiv);
                etaShown = false;
              }
              fullReply += event.content;
              updateStreamingBubble(bubbleDiv, fullReply);
              scrollToBottom();
              break;

            case "tool":
              appendToolNotice(bubbleDiv, `Using tool: ${event.name}`);
              scrollToBottom();
              break;

            case "tool_result":
              appendToolNotice(bubbleDiv, `Tool result: ${(event.result || "").substring(0, 120)}...`);
              scrollToBottom();
              break;

            case "done":
              // Hide ETA if still visible
              hideEtaBar(bubbleDiv);
              modelUsed = event.model || "";
              if (!sessionId && event.session_id) {
                sessionId = event.session_id;
                $sessionTitle.textContent = `Chat ${sessionId}`;
              }
              break;

            case "error":
              hideEtaBar(bubbleDiv);
              fullReply = event.content;
              updateStreamingBubble(bubbleDiv, fullReply);
              break;
          }
        } catch (e) {
          // ignore malformed JSON lines
        }
      }
    }

    // Finalize the bubble
    hideEtaBar(bubbleDiv);
    finalizeStreamingBubble(bubbleDiv, fullReply, modelUsed);
  }

  // ═══════════════════════════════════════════════════════
  //  ETA BAR
  // ═══════════════════════════════════════════════════════

  /**
   * Show an estimated-time-remaining bar inside the streaming bubble.
   */
  function showEtaBar(container, seconds, label) {
    hideEtaBar(container); // remove any existing

    const etaBar = document.createElement("div");
    etaBar.className = "eta-bar";

    const duration = Math.max(1, seconds);
    etaBar.innerHTML = `
      <span>${escapeHtml(label || "~" + duration + "s")}</span>
      <div class="progress">
        <div class="bar" style="animation-duration: ${duration}s;"></div>
      </div>
    `;

    // Insert before the bubble content
    const contentDiv = container.querySelector(":scope > div:last-child");
    if (contentDiv) {
      contentDiv.insertBefore(etaBar, contentDiv.firstChild);
    }

    scrollToBottom();
  }

  /**
   * Remove the ETA bar from the container.
   */
  function hideEtaBar(container) {
    const etaBar = container.querySelector(".eta-bar");
    if (etaBar) etaBar.remove();
  }

  // ═══════════════════════════════════════════════════════
  //  RESEARCH MODE
  // ═══════════════════════════════════════════════════════

  /**
   * Start a deep research session for the given query.
   * Streams progress events from /research and shows them in chat.
   */
  async function startResearch(query) {
    if (isGenerating) return;

    isGenerating = true;
    $input.value = "";
    $input.style.height = "auto";
    $sendBtn.disabled = true;
    $researchBtn.classList.add("active");

    // Remove welcome screen
    const welcome = $messages.querySelector(".welcome");
    if (welcome) welcome.remove();

    // Add user bubble with research badge
    appendMessage("user", query);

    // Create assistant bubble for the research progress
    const bubbleDiv = createStreamingBubble();

    // Add research badge to the bubble
    const contentDiv = bubbleDiv.querySelector(":scope > div:last-child");
    const badge = document.createElement("div");
    badge.className = "research-badge";
    badge.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/>
        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        <line x1="8" y1="11" x2="14" y2="11"/>
        <line x1="11" y1="8" x2="11" y2="14"/>
      </svg>
      Research
    `;
    contentDiv.insertBefore(badge, contentDiv.firstChild);

    // Create research progress tracker
    const progressDiv = document.createElement("div");
    progressDiv.className = "research-progress";
    contentDiv.insertBefore(progressDiv, contentDiv.querySelector(".bubble"));

    const stages = [
      { key: "planning",    label: "Planning research..." },
      { key: "searching",   label: "Searching the web..." },
      { key: "extracting",  label: "Extracting content..." },
      { key: "synthesizing", label: "Synthesizing report..." },
      { key: "complete",    label: "Research complete" },
    ];

    // Render all stages as pending
    let stageElements = {};
    stages.forEach((s) => {
      const el = document.createElement("div");
      el.className = "research-stage";
      el.innerHTML = `
        <div class="stage-icon pending">${s.key === "complete" ? "✓" : s.key[0].toUpperCase()}</div>
        <span class="stage-label">${s.label}</span>
      `;
      progressDiv.appendChild(el);
      stageElements[s.key] = el;
    });

    try {
      const formData = new FormData();
      formData.append("query", query);

      const resp = await fetch("/research", {
        method: "POST",
        body: formData,
      });

      if (!resp.ok) throw new Error(`Research error: ${resp.status}`);

      // Read SSE stream
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (jsonStr === "[DONE]") break;

          try {
            const event = JSON.parse(jsonStr);
            const stage = event.stage;

            if (stage && stageElements[stage]) {
              // Mark all previous stages as done, current as active
              for (const s of stages) {
                const el = stageElements[s.key];
                const icon = el.querySelector(".stage-icon");
                const label = el.querySelector(".stage-label");

                if (stages.indexOf(s) < stages.findIndex((x) => x.key === stage)) {
                  // Already passed
                  icon.className = "stage-icon done";
                  icon.textContent = "✓";
                  label.className = "stage-label done";
                } else if (s.key === stage) {
                  // Current stage
                  icon.className = "stage-icon active";
                  label.className = "stage-label active";
                  // Update the label text if a specific message is provided
                  if (event.message && s.key !== "complete") {
                    label.textContent = event.message;
                  }
                }
              }
            }

            scrollToBottom();

            // Handle final result
            if (event.done && event.result) {
              // Mark all stages done
              for (const s of stages) {
                const el = stageElements[s.key];
                el.querySelector(".stage-icon").className = "stage-icon done";
                el.querySelector(".stage-icon").textContent = "✓";
                el.querySelector(".stage-label").className = "stage-label done";
              }

              // Remove progress div and show the final report
              progressDiv.remove();

              const report = event.result.report || "";
              const sources = event.result.sources || [];
              const subQuestions = event.result.sub_questions || [];

              // Build formatted report
              let reportHtml = "";

              // Research badge
              reportHtml += `<div class="research-badge">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="11" cy="11" r="8"/>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                  <line x1="8" y1="11" x2="14" y2="11"/>
                  <line x1="11" y1="8" x2="11" y2="14"/>
                </svg>
                Research Report
              </div>`;

              reportHtml += formatMessage(report);

              // Show sources
              if (sources.length > 0) {
                reportHtml += `<div style="margin-top:12px; padding-top:8px; border-top:1px solid var(--border);">`;
                reportHtml += `<div style="font-size:11px; color:var(--text-muted); margin-bottom:4px; font-family:var(--font-mono);">SOURCES:</div>`;
                sources.slice(0, 10).forEach((src) => {
                  reportHtml += `<div style="font-size:11px; color:var(--accent); margin:2px 0; word-break:break-all;">${escapeHtml(src)}</div>`;
                });
                reportHtml += `</div>`;
              }

              updateStreamingBubble(bubbleDiv, reportHtml);
              finalizeStreamingBubble(bubbleDiv, reportHtml, "");
            }

            // Handle error stage
            if (stage === "error") {
              progressDiv.remove();
              updateStreamingBubble(bubbleDiv, `Research error: ${event.message || "Unknown error"}`);
              finalizeStreamingBubble(bubbleDiv, `Research error`, "");
            }

          } catch (e) {
            // ignore malformed JSON
          }
        }
      }

      // If we never got a final done event, clean up
      if (progressDiv.parentNode) {
        progressDiv.remove();
      }

    } catch (e) {
      if (progressDiv.parentNode) {
        progressDiv.remove();
      }
      updateStreamingBubble(bubbleDiv, `Research failed: ${e.message}`);
      finalizeStreamingBubble(bubbleDiv, "Research failed", "");
    } finally {
      isGenerating = false;
      $sendBtn.disabled = false;
      $researchBtn.classList.remove("active");
      $input.focus();
    }
  }

  // ═══════════════════════════════════════════════════════
  //  STREAMING BUBBLE HELPERS
  // ═══════════════════════════════════════════════════════

  function createStreamingBubble() {
    const div = document.createElement("div");
    div.className = "message assistant";
    div.innerHTML = `
      <div class="avatar assistant">M</div>
      <div>
        <div class="bubble streaming">
          <div class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    `;
    $messages.appendChild(div);
    scrollToBottom();
    return div;
  }

  function updateStreamingBubble(container, text) {
    const bubble = container.querySelector(".bubble");
    bubble.innerHTML = formatMessage(text) + '<span class="cursor-blink">|</span>';
  }

  function finalizeStreamingBubble(container, text, model) {
    const bubble = container.querySelector(".bubble");
    bubble.classList.remove("streaming");
    // Remove cursor if present
    const cursor = bubble.querySelector(".cursor-blink");
    if (cursor) cursor.remove();

    if (!bubble.innerHTML.trim() || bubble.querySelector(".typing-indicator")) {
      bubble.innerHTML = formatMessage(text);
    }

    if (model) {
      const tag = document.createElement("div");
      tag.className = "model-tag";
      tag.textContent = model;
      container.querySelector(":scope > div:last-child").appendChild(tag);
    }
  }

  function appendToolNotice(container, text) {
    const notice = document.createElement("div");
    notice.className = "tool-notice";
    notice.textContent = text;
    container.querySelector(":scope > div:last-child").appendChild(notice);
  }

  // ═══════════════════════════════════════════════════════
  //  RENDER STATIC MESSAGES
  // ═══════════════════════════════════════════════════════

  /**
   * Append a message to the chat.
   * @param {string} role - "user" or "assistant"
   * @param {string} text - The message content (HTML or plain text)
   * @param {string} [model] - Optional model tag
   * @param {boolean} [isHtml] - If true, content is treated as raw HTML
   */
  function appendMessage(role, text, model, isHtml) {
    const div = document.createElement("div");
    div.className = `message ${role}`;

    const avatar = role === "user" ? "U" : "M";
    const avatarClass = role === "user" ? "user" : "assistant";

    const content = isHtml ? text : escapeHtml(text);

    div.innerHTML = `
      <div class="avatar ${avatarClass}">${avatar}</div>
      <div>
        <div class="bubble">${content}</div>
        ${model ? `<div class="model-tag">${model}</div>` : ""}
      </div>
    `;

    $messages.appendChild(div);
    scrollToBottom();

    // Attach click handlers for chat images (lightbox)
    div.querySelectorAll(".chat-image").forEach((img) => {
      img.addEventListener("click", () => openImageOverlay(img.src));
    });
  }

  // ═══════════════════════════════════════════════════════
  //  IMAGE LIGHTBOX OVERLAY
  // ═══════════════════════════════════════════════════════

  let imageOverlay = null;

  function openImageOverlay(src) {
    if (!imageOverlay) {
      imageOverlay = document.createElement("div");
      imageOverlay.className = "image-overlay";
      imageOverlay.addEventListener("click", () => {
        imageOverlay.classList.remove("active");
      });
      document.body.appendChild(imageOverlay);
    }
    imageOverlay.innerHTML = `<img src="${src}" alt="Full size image">`;
    imageOverlay.classList.add("active");
  }

  // ═══════════════════════════════════════════════════════
  //  MARKDOWN FORMATTING (enhanced)
  // ═══════════════════════════════════════════════════════

  /**
   * Convert plain text to formatted HTML.
   * Supports: code blocks, inline code, bold, italic, line breaks,
   * unordered lists, ordered lists.
   */
  function formatMessage(text) {
    // Escape HTML first to prevent injection
    let html = escapeHtml(text);

    // ── Code blocks (```lang ... ```) ──
    // Must be done before inline code to avoid conflicts
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, lang, code) => {
      const langLabel = lang ? ` data-lang="${escapeAttr(lang)}"` : "";
      return `<pre${langLabel}><code>${code.trim()}</code></pre>`;
    });

    // ── Inline code (`...`) ──
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");

    // ── Bold (**...**) ──
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

    // ── Italic (*...*) — single asterisk, not double ──
    html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>");

    // ── Line breaks ──
    // Convert double newlines to paragraph breaks
    html = html.replace(/\n\n/g, "<br><br>");

    // Convert remaining single newlines to <br>
    html = html.replace(/\n/g, "<br>");

    // ── Unordered lists (- item or * item at start of line) ──
    // Match lines that start with "- " or "* " (after any <br> or at start)
    html = html.replace(/(^|<br>)[\-\*] (.+?)(?=<br>|$)/g, (match, prefix, item) => {
      return `${prefix}<li>${item}</li>`;
    });

    // Wrap consecutive <li> in <ul>
    html = html.replace(/((?:<li>.*?<\/li>(?:<br>)*)+)/g, (match) => {
      // Remove trailing <br> between list items
      const cleaned = match.replace(/<\/li><br>/g, "</li>");
      return `<ul>${cleaned}</ul>`;
    });

    // ── Ordered lists (1. item, 2. item) ──
    html = html.replace(/(^|<br>)\d+\. (.+?)(?=<br>|$)/g, (match, prefix, item) => {
      return `${prefix}<li>${item}</li>`;
    });

    // Wrap consecutive <li> that aren't already in a <ul> into <ol>
    // This is a simple heuristic — if there are <li> not inside <ul>, wrap them
    html = html.replace(/(?:^|<br>)(?![^<]*<ul>)((?:<li>.*?<\/li>(?:<br>)*)+)/g, (_match, block, _offset, full) => {
      // Only wrap if the <li> elements aren't already children of <ul>
      if (full.substring(Math.max(0, _offset - 20), _offset).includes("<ul>")) {
        return block;
      }
      const cleaned = block.replace(/<\/li><br>/g, "</li>");
      return `<ol>${cleaned}</ol>`;
    });

    return html;
  }

  // ═══════════════════════════════════════════════════════
  //  UTILITIES
  // ═══════════════════════════════════════════════════════

  function scrollToBottom() {
    $chatContainer.scrollTop = $chatContainer.scrollHeight;
  }

  function escapeHtml(text) {
    const el = document.createElement("div");
    el.textContent = text;
    return el.innerHTML;
  }

  function escapeAttr(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // ═══════════════════════════════════════════════════════
  //  VOICE RECORDING (unchanged from v0.2)
  // ═══════════════════════════════════════════════════════

  async function toggleVoiceRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      audioChunks = [];

      mediaRecorder.ondataavailable = (e) => {
        audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(audioChunks, { type: "audio/webm" });
        await sendVoice(blob);
      };

      mediaRecorder.start();
      isRecording = true;
      $voiceBtn.classList.add("recording");
    } catch (e) {
      alert("Microphone access denied or unavailable.");
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    isRecording = false;
    $voiceBtn.classList.remove("recording");
  }

  async function sendVoice(blob) {
    if (isGenerating) return;
    try {
      const formData = new FormData();
      formData.append("file", blob, "recording.webm");

      const resp = await fetch("/stt", { method: "POST", body: formData });
      const data = await resp.json();

      if (data.text && data.text.trim()) {
        $input.value = data.text;
        sendMessage();
      } else {
        appendMessage("assistant", "Could not transcribe audio. Try speaking louder.");
      }
    } catch (e) {
      appendMessage("assistant", "Speech-to-text failed. Is Whisper running?");
    }
  }

  // ═══════════════════════════════════════════════════════
  //  START
  // ═══════════════════════════════════════════════════════

  init();
})();
