// Client-side UI Controller for NexusStream Collaboration App
let currentChannel = "ALL";
let selectedFile = null;
let isConnected = false;
let lastRenderedChannel = null;
let lastRenderedMsgCount = -1;
let lastPeersKey = "";

document.addEventListener("DOMContentLoaded", () => {
  fetchState();
  setInterval(fetchState, 1000);
});

function toggleConnectModal() {
  const modal = document.getElementById("modal-connect");
  modal.classList.toggle("hidden");
  if (!modal.classList.contains("hidden")) {
    document.getElementById("input-username").focus();
  }
}

async function connectToServer() {
  const username = document.getElementById("input-username").value.trim();
  const host = (document.getElementById("input-host") ? document.getElementById("input-host").value : "127.0.0.1").trim() || "127.0.0.1";
  const port = parseInt(document.getElementById("input-port") ? document.getElementById("input-port").value : "8888", 10) || 8888;

  if (!username) {
    alert("Please enter your username!");
    return;
  }

  try {
    const res = await fetch("/api/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, host, port })
    });
    const data = await res.json();
    if (data.success) {
      toggleConnectModal();
      fetchState();
    } else {
      alert("Connection failed: " + data.message);
    }
  } catch (err) {
    alert("Error reaching local client server: " + err);
  }
}

async function disconnectFromServer() {
  try {
    await fetch("/api/disconnect", { method: "POST" });
    fetchState();
  } catch (err) {
    console.error(err);
  }
}

async function fetchState() {
  try {
    const res = await fetch("/api/state");
    const state = await res.json();

    isConnected = state.is_connected;
    updateStatusHeader(state);
    updatePeersList(state.active_users, state.username);
    updateMessages(state.messages, state.username);
    updateTransfers(state.transfers);
  } catch (err) {
    console.warn("Error fetching client state:", err);
  }
}

function updateStatusHeader(state) {
  const statusInd = document.getElementById("status-indicator");
  const statusText = document.getElementById("status-text");
  const userChip = document.getElementById("current-user-info");
  const btnToggle = document.getElementById("btn-toggle-connect");

  if (state.is_connected) {
    statusInd.className = "status-indicator connected";
    statusText.textContent = "Online";
    userChip.classList.remove("hidden");
    document.getElementById("my-username").textContent = state.username;
    document.getElementById("my-avatar").textContent = state.username.charAt(0).toUpperCase();
    document.getElementById("my-udp-port").textContent = "UDP: " + state.udp_port;

    btnToggle.textContent = "Disconnect";
    btnToggle.className = "btn btn-secondary";
    btnToggle.onclick = disconnectFromServer;
  } else {
    statusInd.className = "status-indicator disconnected";
    statusText.textContent = "Disconnected";
    userChip.classList.add("hidden");

    btnToggle.textContent = "Connect";
    btnToggle.className = "btn btn-primary";
    btnToggle.onclick = toggleConnectModal;
  }
}

function updatePeersList(peers, myUsername) {
  const container = document.getElementById("peers-container");
  const targetSelect = document.getElementById("file-target-select");
  const userCountEl = document.getElementById("user-count");

  const otherPeers = peers.filter(p => p.username !== myUsername);
  userCountEl.textContent = peers.length;

  const peersKey = JSON.stringify(otherPeers.map(p => ({ u: p.username, ip: p.ip, port: p.udp_port }))) + "_" + currentChannel;
  if (peersKey === lastPeersKey) {
    return;
  }
  lastPeersKey = peersKey;

  const currentSelectVal = targetSelect.value;
  targetSelect.innerHTML = '<option value="">Select a peer...</option>';

  if (otherPeers.length === 0) {
    container.innerHTML = '<div class="empty-hint">No other peers online</div>';
    return;
  }

  container.innerHTML = "";
  otherPeers.forEach(peer => {
    const item = document.createElement("div");
    item.className = "peer-item" + (currentChannel === peer.username ? " active" : "");
    item.onclick = () => selectChannel(peer.username);

    item.innerHTML = `
      <span class="avatar">${peer.username.charAt(0).toUpperCase()}</span>
      <div class="peer-meta">
        <span class="peer-name">${escapeHtml(peer.username)}</span>
        <span class="peer-status">${peer.ip}:${peer.udp_port}</span>
      </div>
    `;
    container.appendChild(item);

    const opt = document.createElement("option");
    opt.value = peer.username;
    opt.textContent = `${peer.username} (${peer.ip}:${peer.udp_port})`;
    targetSelect.appendChild(opt);
  });

  if (currentSelectVal) {
    targetSelect.value = currentSelectVal;
  }
}

function selectChannel(channel) {
  if (currentChannel === channel) return;
  currentChannel = channel;
  lastPeersKey = "";
  lastRenderedChannel = null;

  document.getElementById("channel-global").className = "channel-item" + (channel === "ALL" ? " active" : "");

  document.querySelectorAll(".peer-item").forEach(el => {
    const nameEl = el.querySelector(".peer-name");
    if (nameEl && nameEl.textContent === channel) {
      el.classList.add("active");
    } else {
      el.classList.remove("active");
    }
  });

  const headerIcon = document.getElementById("chat-header-icon");
  const headerName = document.getElementById("chat-target-name");

  if (channel === "ALL") {
    headerIcon.textContent = "🌐";
    headerName.textContent = "Global Chat";
  } else {
    headerIcon.textContent = "💬";
    headerName.textContent = "@" + channel;
  }

  fetchState();
}

function createBubbleElement(m, myUsername, isNew = false) {
  const isMine = m.sender === myUsername;
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble " + (isMine ? "mine" : "other") + (isNew ? " new-arrival" : "");

  const timeStr = new Date(m.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  bubble.innerHTML = `
    <div class="bubble-meta">
      <span class="sender-name">${escapeHtml(m.sender)}</span>
      <span>•</span>
      <span class="timestamp">${timeStr}</span>
    </div>
    <div class="bubble-content">${escapeHtml(m.text)}</div>
  `;
  return bubble;
}

function updateMessages(messages, myUsername) {
  const viewport = document.getElementById("messages-viewport");

  const filtered = messages.filter(m => {
    if (currentChannel === "ALL") {
      return m.is_broadcast === true;
    } else {
      return (
        (!m.is_broadcast && m.sender === currentChannel && m.target === myUsername) ||
        (!m.is_broadcast && m.sender === myUsername && m.target === currentChannel)
      );
    }
  });

  if (lastRenderedChannel !== currentChannel) {
    lastRenderedChannel = currentChannel;
    lastRenderedMsgCount = filtered.length;
    viewport.innerHTML = "";

    if (filtered.length === 0) {
      viewport.innerHTML = `<div class="message-notice">No messages in ${currentChannel === "ALL" ? "Global Chat" : "@" + currentChannel} yet.</div>`;
      return;
    }

    filtered.forEach(m => {
      viewport.appendChild(createBubbleElement(m, myUsername, false));
    });
    viewport.scrollTop = viewport.scrollHeight;
    return;
  }

  if (filtered.length === lastRenderedMsgCount) {
    return;
  }

  if (lastRenderedMsgCount === 0 || viewport.querySelector(".message-notice")) {
    viewport.innerHTML = "";
  }

  const existingBubbles = viewport.querySelectorAll(".chat-bubble");
  const startIndex = existingBubbles.length;

  for (let i = startIndex; i < filtered.length; i++) {
    viewport.appendChild(createBubbleElement(filtered[i], myUsername, true));
  }

  lastRenderedMsgCount = filtered.length;
  viewport.scrollTop = viewport.scrollHeight;
}

async function sendMessage() {
  const input = document.getElementById("input-message");
  const text = input.value.trim();
  if (!text) return;

  if (!isConnected) {
    alert("Please connect to the collaboration server first.");
    return;
  }

  input.value = "";
  try {
    await fetch("/api/send_message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target: currentChannel,
        text: text
      })
    });
    fetchState();
  } catch (err) {
    console.error("Failed to send message:", err);
  }
}

function handleChatKey(e) {
  if (e.key === "Enter") {
    sendMessage();
  }
}

function handleFileSelected(e) {
  const file = e.target.files[0];
  if (file) {
    selectedFile = file;
    const label = document.getElementById("file-picker-label");
    if (label) {
      label.textContent = `${file.name} (${formatBytes(file.size)})`;
    }
    const sendBtn = document.getElementById("btn-send-file");
    if (sendBtn) {
      sendBtn.disabled = false;
    }
  }
}

async function uploadAndSendFile() {
  const target = document.getElementById("file-target-select").value;
  if (!target) {
    alert("Please choose a recipient peer for the file transfer.");
    return;
  }
  if (!selectedFile) {
    alert("Please select a file to transfer.");
    return;
  }

  const btn = document.getElementById("btn-send-file");
  btn.disabled = true;
  btn.textContent = "Streaming over UDP...";

  const reader = new FileReader();
  reader.onload = async function () {
    const base64Content = reader.result.split(",")[1];
    try {
      const res = await fetch("/api/upload_and_send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target: target,
          filename: selectedFile.name,
          content_b64: base64Content
        })
      });
      const data = await res.json();
      if (!data.success) {
        alert("Transfer failed: " + data.message);
      }
    } catch (err) {
      alert("Error initiating file stream: " + err);
    } finally {
      btn.textContent = "Start UDP Streaming Transfer";
      btn.disabled = false;
      fetchState();
    }
  };
  reader.readAsDataURL(selectedFile);
}

function updateTransfers(transfers) {
  const container = document.getElementById("transfers-container");
  if (!transfers || transfers.length === 0) {
    container.innerHTML = '<div class="empty-hint">No active transfers</div>';
    return;
  }

  container.innerHTML = "";
  transfers.forEach(t => {
    const card = document.createElement("div");
    card.className = "transfer-card";

    const isDone = t.progress >= 100.0;
    const roleIcon = t.role === "sender" ? "⬆" : "⬇";
    const statusText = isDone ? "Completed" : (t.role === "sender" ? "Sending..." : "Receiving...");
    const downloadName = t.saved_filename || t.filename;

    card.innerHTML = `
      <div class="transfer-meta">
        <span class="transfer-filename" title="${escapeHtml(t.filename)}">${roleIcon} ${escapeHtml(t.filename)}</span>
        <span class="transfer-pct">${t.progress}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-bar" style="width: ${t.progress}%;"></div>
      </div>
      <div class="transfer-footer">
        <span>${statusText} ${isDone && t.role === "receiver" ? `<a href="/downloads/${encodeURIComponent(downloadName)}" target="_blank" class="download-link">Open</a>` : ''}</span>
        <span>${formatBytes(t.file_size)}</span>
      </div>
    `;
    container.appendChild(card);
  });
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function escapeHtml(text) {
  if (!text) return "";
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return text.replace(/[&<>"']/g, m => map[m]);
}
