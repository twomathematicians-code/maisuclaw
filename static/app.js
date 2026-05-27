// ── maisuclaw — frontend logic ─────────────────────────────
(function () {
  "use strict";

  // ── State ───────────────────────────────────────────────
  let sessionId = null;
  let isRecording = false;
  let mediaRecorder = null;
  let audioChunks = [];

  // ── DOM references ───────────────────────────────────────
  const $messages = document.getElementById("messages");
  const $input = document.getElementById("user-input");
  const $sendBtn = document.getElementById("send-btn");
  const $voiceBtn = document.getElementById("voice-btn");
  const $sidebar = document.getElementById("sidebar");
  const $sidebarToggle = document.getElementById("sidebar-toggle");
  const $newChatBtn = document.getElementById("new-chat-btn");
  const $sessionList = document.getElementById("session-list");
  const $modeSelect = document.getElementById("mode-select");
  const $sessionTitle = document.getElementById("session-title");
  const $modelBadge = document.getElementById("model-badge");
  const $chatContainer = document.getElementById("chat-container");

  // ── Init ─────────────────────────────────────────────────
  async function init() {
    showWelcome();
    await fetchServerInfo();
    setupEventListeners();
  }

  // ── Welcome screen ───────────────────────────────────────
  function showWelcome() {
    $messages.innerHTML = `
      <div class="welcome">
        <h1>maisuclaw</h1>
        <p>Your personal AI assistant running entirely on your laptop.<br>
        Ask anything — code, notes, files, web search, and more.</p>
        <div class="shortcuts">
          <div class="shortcut" data-msg="List the files on my Desktop">Browse files</div>
          <div class="shortcut" data-msg="Write a Python script that sorts a list and explain how it works">Code example</div>
          <div class="shortcut" data-msg="Save a note: title='Ideas', content='Build a weather dashboard with charts'">Save a note</div>
          <div class="shortcut" data-msg="What is 15% of 2340?">Quick math</div>
        </div>
      </div>
    `;

    // Bind shortcut clicks
    document.querySelectorAll(".shortcut").forEach((el) => {
      el.addEventListener("click", () => {
        $input.value = el.dataset.msg;
        sendMessage();
      });
    });
  }

  // ── Server info ─────────────────────────────────────────
  async function fetchServerInfo() {
    try {
      const resp = await fetch("/info");
      const data = await resp.json();
      if (data.models && data.models.length > 0) {
        $modelBadge.innerHTML = data.models.map((m) => `<span>${m}</span>`).join("");
      } else {
        $modelBadge.textContent = "No models found — start Ollama first";
      }
    } catch (e) {
      $modelBadge.textContent = "Cannot reach backend";
    }
  }

  // ── Event listeners ─────────────────────────────────────
  function setupEventListeners() {
    $sendBtn.addEventListener("click", sendMessage);
    $input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Auto-resize textarea
    $input.addEventListener("input", () => {
      $input.style.height = "auto";
      $input.style.height = Math.min($input.scrollHeight, 150) + "px";
    });

    // Sidebar toggle
    $sidebarToggle.addEventListener("click", () => {
      $sidebar.classList.toggle("hidden");
    });

    // New chat
    $newChatBtn.addEventListener("click", () => {
      sessionId = null;
      $sessionTitle.textContent = "New Conversation";
      showWelcome();
    });

    // Voice
    $voiceBtn.addEventListener("click", toggleVoiceRecording);
  }

  // ── Send message ────────────────────────────────────────
  async function sendMessage() {
    const text = $input.value.trim();
    if (!text) return;

    $input.value = "";
    $input.style.height = "auto";

    // Remove welcome screen
    const welcome = $messages.querySelector(".welcome");
    if (welcome) welcome.remove();

    // Add user bubble
    appendMessage("user", text);
    showTyping();

    try {
      const resp = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          mode: $modeSelect.value,
        }),
      });

      const data = await resp.json();
      removeTyping();
      appendMessage("assistant", data.reply, data.model);

      // Update session
      if (!sessionId && data.session_id) {
        sessionId = data.session_id;
        $sessionTitle.textContent = `Chat ${sessionId}`;
      }
    } catch (e) {
      removeTyping();
      appendMessage("assistant", "Connection error — is the server running? (`uvicorn main:app --reload`)");
    }
  }

  // ── Render messages ─────────────────────────────────────
  function appendMessage(role, text, model) {
    const div = document.createElement("div");
    div.className = `message ${role}`;

    const avatar = role === "user" ? "U" : "M";
    const avatarClass = role === "user" ? "user" : "assistant";

    div.innerHTML = `
      <div class="avatar ${avatarClass}">${avatar}</div>
      <div>
        <div class="bubble">${escapeHtml(text)}</div>
        ${model ? `<div class="model-tag">${model}</div>` : ""}
      </div>
    `;

    $messages.appendChild(div);
    scrollToBottom();
  }

  function showTyping() {
    const div = document.createElement("div");
    div.className = "message assistant";
    div.id = "typing";
    div.innerHTML = `
      <div class="avatar assistant">M</div>
      <div class="bubble">
        <div class="typing-indicator"><span></span><span></span><span></span></div>
      </div>
    `;
    $messages.appendChild(div);
    scrollToBottom();
  }

  function removeTyping() {
    const el = document.getElementById("typing");
    if (el) el.remove();
  }

  function scrollToBottom() {
    $chatContainer.scrollTop = $chatContainer.scrollHeight;
  }

  function escapeHtml(text) {
    const el = document.createElement("div");
    el.textContent = text;
    return el.innerHTML;
  }

  // ── Voice recording ─────────────────────────────────────
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
    showTyping();
    try {
      const formData = new FormData();
      formData.append("file", blob, "recording.webm");

      const resp = await fetch("/stt", { method: "POST", body: formData });
      const data = await resp.json();

      if (data.text && data.text.trim()) {
        $input.value = data.text;
        sendMessage();
      } else {
        removeTyping();
        appendMessage("assistant", "Could not transcribe audio. Try speaking louder or closer to the mic.");
      }
    } catch (e) {
      removeTyping();
      appendMessage("assistant", "Speech-to-text failed. Is Ollama Whisper running?");
    }
  }

  // ── Start ───────────────────────────────────────────────
  init();
})();
