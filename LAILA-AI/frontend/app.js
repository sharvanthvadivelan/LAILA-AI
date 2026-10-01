"use strict";
const $ = (s) => document.querySelector(s),
  $$ = (s) => [...document.querySelectorAll(s)];
const E = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let token = "",
  cid = null,
  current = null,
  page = "chat",
  settings = {},
  busy = false,
  localModelReady = false,
  assistantState = "idle",
  attached = [],
  image = null,
  aborter = null,
  recorder = null,
  recordStream = null,
  audio = null,
  voiceTurn = false,
  speechSerial = 0;
let conversationList = [],
  models = [],
  docList = [],
  dailyTargets = [];
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => ($("#toast").hidden = true), 6500);
}
function setAssistantState(state, label) {
  assistantState = state;
  const text =
    label ||
    ({
      idle: "Ready when you are",
      recording: "Recording on this device",
      transcribing: "Transcribing your recording",
      generating: "Generating a response",
      speaking: "Speaking response",
      approval: "Your approval is needed",
      offline: "Local model unavailable",
    }[state] || "Ready when you are");
  $("#assistant-face").dataset.state = state;
  $("#assistant-status").dataset.state = state;
  $("#assistant-status-text").textContent = text;
}
function syncClock() {
  $("#local-clock").textContent = new Intl.DateTimeFormat([], {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date());
}
function setMotionOff(value) {
  document.body.classList.toggle("motion-off", value);
  $("#motion-toggle").setAttribute("aria-pressed", String(value));
  $("#motion-toggle").textContent = value ? "Motion off" : "Motion on";
  $("#motion-toggle").title = value
    ? "Turn decorative animation on"
    : "Turn decorative animation off";
  localStorage.setItem("laila-motion-off", value ? "on" : "off");
  const video = $("#laila-video");
  if (value) video.pause();
  else if (!document.hidden) video.play().catch(() => {});
}
async function api(path, method = "GET", body) {
  const headers = { "X-Laila-Token": token };
  if (body !== undefined && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  let r;
  try {
    r = await fetch("/api" + path, {
      method,
      headers,
      body:
        body === undefined
          ? undefined
          : body instanceof FormData
            ? body
            : JSON.stringify(body),
    });
  } catch (error) {
    $("#model-badge").textContent = "Backend unavailable";
    $("#model-badge").dataset.state = "offline";
    setAssistantState("offline", "Start the local server to reconnect");
    throw error;
  }
  if (!r.ok) {
    let data;
    try {
      data = await r.json();
    } catch {
      data = { detail: "Local server error (" + r.status + ")" };
    }
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  }
  return r.json();
}
function action(fn) {
  return async (...args) => {
    try {
      await fn(...args);
    } catch (e) {
      toast(e.message);
    }
  };
}
const date = (x) =>
  x
    ? new Date(x).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";
function setBusy(value) {
  busy = value;
  $("#send").hidden = value;
  $("#stop").hidden = !value;
  $("#prompt").disabled = value;
  [
    "#new-chat",
    "#mode",
    "#pin-chat",
    "#rename-chat",
    "#clear-chat",
    "#delete-chat",
    "#attach-button",
    "#mic",
  ].forEach((s) => ($(s).disabled = value));
  $$("#history button").forEach((b) => (b.disabled = value));
  if (value) setAssistantState("generating");
  else if (assistantState === "generating")
    setAssistantState(localModelReady ? "idle" : "offline");
}
async function refreshModels() {
  const data = await api("/models");
  models = data.models;
  localModelReady = Boolean(data.running && data.available);
  $("#model-badge").textContent = localModelReady
    ? "Local · " + data.selected
    : data.running
      ? "Ollama online · model missing"
      : "Ollama offline";
  $("#model-badge").dataset.state = localModelReady
    ? "online"
    : data.running
      ? "warning"
      : "offline";
  $("#rail-model").innerHTML = `<span class="status-indicator" aria-hidden="true"></span><span>${E($("#model-badge").textContent)}</span>`;
  if (!busy && !["recording", "transcribing", "speaking", "approval"].includes(assistantState))
    setAssistantState(localModelReady ? "idle" : "offline", localModelReady ? "Ready when you are" : "Notes and tasks work offline");
  $("#alert").hidden = data.running && data.available;
  $("#alert").textContent = data.running
    ? "Selected model is not installed. Open Models & system to choose a local model."
    : data.error ||
      "Start Ollama on this laptop to enable AI chat. Notes, tasks and calculator remain available.";
  return data;
}
async function refreshDailyRail() {
  const results = await Promise.allSettled([
    api("/personal/dashboard"),
    api("/desktop/targets"),
  ]);
  const dashboard = results[0].status === "fulfilled" ? results[0].value : null;
  const desktop = results[1].status === "fulfilled" ? results[1].value : null;
  if (dashboard) {
    const day = new Date(dashboard.date + "T12:00:00");
    $("#rail-date").textContent = day.toLocaleDateString([], {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
    const now = Date.now();
    const upcoming = dashboard.plan
      .filter((item) => !item.completed && new Date(item.starts_at).getTime() + item.minutes * 60000 > now)
      .slice(0, 3);
    $("#rail-schedule").replaceChildren();
    if (!upcoming.length) {
      $("#rail-schedule").innerHTML = '<p class="rail-empty">No upcoming blocks today.</p>';
    }
    for (const item of upcoming) {
      const row = document.createElement("div");
      row.className = "rail-item schedule-item";
      const time = new Date(item.starts_at).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
        timeZone: dashboard.timezone,
      });
      row.innerHTML = `<time>${E(time)}</time><div><b>${E(item.title)}</b><small>${E(item.category)} · ${item.minutes} min</small></div>`;
      $("#rail-schedule").append(row);
    }
    $("#rail-tasks").replaceChildren();
    const tasks = dashboard.tasks.slice(0, 3);
    if (!tasks.length) $("#rail-tasks").innerHTML = '<p class="rail-empty">Nothing open. You have room to choose.</p>';
    for (const task of tasks) {
      const row = document.createElement("div");
      row.className = "rail-item task-item";
      row.innerHTML = `<span class="task-mark" aria-hidden="true"></span><div><b>${E(task.title)}</b><small>${E(task.priority)}${task.due_date ? " · due " + E(task.due_date) : ""}</small></div>`;
      $("#rail-tasks").append(row);
    }
  } else {
    $("#rail-schedule").innerHTML = '<p class="rail-empty">Schedule could not be loaded.</p>';
    $("#rail-tasks").innerHTML = '<p class="rail-empty">Tasks could not be loaded.</p>';
  }
  if (desktop) {
    dailyTargets = desktop.targets;
    $("#rail-targets").replaceChildren();
    if (!desktop.supported) {
      $("#rail-targets").innerHTML = '<p class="rail-empty">Desktop launches are available on Windows.</p>';
    } else if (!dailyTargets.length) {
      $("#rail-targets").innerHTML = '<p class="rail-empty">No approved shortcuts yet.</p>';
    }
    for (const target of dailyTargets.slice(0, 3)) {
      const row = document.createElement("div");
      row.className = "rail-target";
      row.innerHTML = `<b>${E(target.name)}</b><code>${E(target.path)}</code>`;
      const launch = document.createElement("button");
      launch.type = "button";
      launch.className = "rail-launch";
      launch.textContent = "Request launch";
      launch.setAttribute("aria-label", `Request launch for ${target.name}`);
      launch.onclick = action(() => requestDesktopLaunch(target));
      row.append(launch);
      $("#rail-targets").append(row);
    }
  } else {
    $("#rail-targets").innerHTML = '<p class="rail-empty">Approved shortcuts could not be loaded.</p>';
  }
}
async function history() {
  conversationList = await api(
    "/conversations?q=" + encodeURIComponent($("#chat-search").value),
  );
  $("#history").replaceChildren();
  if (!conversationList.length) {
    $("#history").innerHTML =
      '<p class="empty-small">Your conversations will appear here.</p>';
    return;
  }
  for (const c of conversationList) {
    const b = document.createElement("button");
    b.textContent = (c.pinned ? "⌁  " : "") + c.title;
    b.title = c.title + " · " + date(c.updated_at);
    b.classList.toggle("selected", c.id === cid);
    b.disabled = busy;
    b.onclick = action(() => openChat(c.id));
    $("#history").append(b);
  }
}
function showChat() {
  $(".toolbar-actions").hidden = !cid;
  page = "chat";
  $("#chat-page").hidden = false;
  $("#workspace-page").hidden = true;
  $("#page-title").textContent = current?.title || "Conversation";
  $("#chat-page").classList.toggle("has-messages", Boolean($("#messages").childElementCount));
  $$("[data-page]").forEach((b) =>
     b.classList.toggle("active", b.dataset.page === "chat"),
  );
  $("#sidebar").classList.remove("open");
  $("#daily-rail").classList.remove("open");
  $("#drawer-scrim").hidden = true;
  $("#menu").setAttribute("aria-expanded", "false");
  $("#day-toggle").setAttribute("aria-expanded", "false");
}
function attachments() {
  const box = $("#attachments");
  box.replaceChildren();
  for (const d of attached) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = "▤ " + d.filename + " ";
    const b = document.createElement("button");
    b.textContent = "×";
    b.ariaLabel = "Remove " + d.filename;
    b.onclick = () => {
      attached = attached.filter((x) => x.id !== d.id);
      attachments();
    };
    chip.append(b);
    box.append(chip);
  }
  if (image) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = "◈ " + image.name + " ";
    const b = document.createElement("button");
    b.textContent = "×";
    b.ariaLabel = "Remove image";
    b.onclick = () => {
      image = null;
      attachments();
    };
    chip.append(b);
    box.append(chip);
  }
}
async function newChat() {
  if (busy) return;
  cid = null;
  current = null;
  if (assistantState === "approval")
    setAssistantState(localModelReady ? "idle" : "offline");
  attached = [];
  image = null;
  attachments();
  $("#messages").replaceChildren();
  $("#welcome").hidden = false;
  showChat();
  await history();
  $("#prompt").focus();
}
async function openChat(id) {
  if (busy) return;
  cid = id;
  const data = await api("/conversations/" + id);
  current = data.conversation;
  attached = [];
  image = null;
  attachments();
  showChat();
  await renderConversation(data.messages);
  await history();
  $("#pin-chat").textContent = current.pinned ? "Unpin" : "Pin";
  const lastUser = data.messages.filter((m) => m.role === "user").at(-1);
  if (lastUser?.meta?.mode) $("#mode").value = lastUser.meta.mode;
  await pendingApprovals();
}
function messageElement(role, content = "", stamp = "") {
  const el = document.createElement("article");
  el.className = "message " + role;
  el.innerHTML = `<div class="avatar">${role === "user" ? "SV" : "✦"}</div><div><div class="message-name">${role === "user" ? "You" : "Laila"}<small>${E(stamp)}</small></div><div class="message-content"></div><div class="message-extra"></div><div class="message-actions"></div></div>`;
  el.querySelector(".message-content").textContent = content;
  $("#messages").append(el);
  return el;
}
async function markdown(el, text) {
  const result = await api("/render", "POST", { text });
  el.innerHTML = result.html;
  el.querySelectorAll("a").forEach((a) => {
    a.target = "_blank";
    a.rel = "noreferrer noopener";
  });
  el.querySelectorAll("pre").forEach((pre) => {
    const b = document.createElement("button");
    b.className = "copy-code";
    b.textContent = "Copy";
    b.onclick = action(async () => {
      await navigator.clipboard.writeText(
        pre.querySelector("code")?.textContent || "",
      );
      toast("Code copied");
    });
    pre.append(b);
  });
}
function sourcePanel(parent, sources) {
  if (!sources?.length) return;
  const details = document.createElement("details");
  details.className = "sources";
  details.innerHTML = `<summary>${sources.length} retrieved excerpts · inspect sources</summary>`;
  for (const s of sources) {
    const item = document.createElement("div");
    item.innerHTML = `<p><b>[${E(s.label)}] ${E(s.filename)}</b> · ${E(s.location)} · similarity ${Number(s.score).toFixed(2)}</p><pre>${E(s.content)}</pre>`;
    details.append(item);
  }
  parent.append(details);
}
function msgButton(parent, label, fn) {
  const b = document.createElement("button");
  b.textContent = label;
  b.onclick = action(fn);
  parent.append(b);
}
async function renderConversation(list) {
  $("#messages").replaceChildren();
  $("#welcome").hidden = list.length > 0;
  $("#chat-page").classList.toggle("has-messages", list.length > 0);
  for (const [i, m] of list.entries()) {
    const el = messageElement(m.role, m.content, date(m.created_at));
    if (m.role === "assistant" && m.content)
      await markdown(el.querySelector(".message-content"), m.content);
    const extras = el.querySelector(".message-extra");
    if (m.meta?.error) {
      const e = document.createElement("p");
      e.className = "message-error";
      e.textContent = m.meta.error;
      extras.append(e);
    }
    if (m.meta?.status === "stopped") {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = "Generation stopped. This answer may be incomplete.";
      extras.append(p);
    }
    if (m.meta?.has_image) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent =
        "Image was used for this turn; image bytes are not retained.";
      extras.append(p);
    }
    sourcePanel(extras, m.meta?.sources);
    const buttons = el.querySelector(".message-actions");
    msgButton(buttons, "Copy", async () => {
      await navigator.clipboard.writeText(m.content);
      toast("Copied");
    });
    if (m.role === "user") {
      msgButton(buttons, "Edit", () => editMessage(m));
    } else {
      if (m.content) msgButton(buttons, "Speak", () => speak(m.content));
      if (i === list.length - 1) {
        msgButton(buttons, "Regenerate", () => send("regenerate"));
        msgButton(buttons, "Continue", () => send("continue"));
      }
    }
  }
  scrollBottom();
}
function scrollBottom() {
  const el = $("#chat-scroll");
  el.scrollTop = el.scrollHeight;
}
function editor(title, body, save) {
  $("#editor-title").textContent = title;
  $("#editor-body").innerHTML = body;
  $("#editor-form").onsubmit = action(async (e) => {
    e.preventDefault();
    await save(new FormData(e.target));
    $("#editor").close();
  });
  $("#editor").showModal();
}
function field(name, label, value = "", type = "text") {
  return `<label class="field">${E(label)}<input name="${name}" type="${type}" value="${E(value)}" required></label>`;
}
function editMessage(m) {
  if (busy) return;
  editor(
    "Edit message",
    `<p class="muted">Later messages will be removed. Completed tool actions will remain.</p><label class="field">Message<textarea name="content" rows="7" required>${E(m.content)}</textarea></label>`,
    async (f) => {
      await api(`/conversations/${cid}/messages/${m.id}`, "PATCH", {
        content: f.get("content"),
      });
      await send("regenerate");
    },
  );
}
async function pendingApprovals() {
  if (!cid) return;
  const pending = await api("/approvals?cid=" + cid);
  if (pending.length) setAssistantState("approval");
  else if (assistantState === "approval")
    setAssistantState(localModelReady ? "idle" : "offline");
  const target =
    $("#messages").lastElementChild?.querySelector(".message-extra");
  if (!target) return;
  for (const p of pending) {
    const desktopTarget =
      p.name === "desktop_open"
        ? dailyTargets.find((item) => item.id === p.arguments.target_id)
        : null;
    const box = document.createElement("div");
    box.className = "approval-card";
    box.innerHTML = `<b>Approval needed · ${E(desktopTarget?.name || p.name.replaceAll("_", " "))}</b>${p.arguments.expected_path ? `<p class="target-path">Exact target: ${E(p.arguments.expected_path)}</p>` : ""}<pre>${E(JSON.stringify(p.arguments, null, 2))}</pre><p>This action has not run. Review the details before continuing.</p>`;
    for (const yes of [true, false]) {
      const b = document.createElement("button");
      b.textContent = yes ? "Approve action" : "Reject";
      b.className = yes ? "primary" : "subtle";
      b.onclick = action(async () => {
        if (busy) {
          toast("Wait for generation to finish");
          return;
        }
        b.disabled = true;
        try {
          await api("/approvals/" + p.id, "POST", { approve: yes });
          await openChat(cid);
          toast(yes ? "Action completed" : "Action rejected");
        } finally {
          b.disabled = false;
        }
      });
      box.append(b);
    }
    target.append(box);
  }
}
async function send(kind = "send") {
  if (busy) return;
  const prompt = $("#prompt");
  const text = prompt.value.trim();
  if (kind === "send" && !text) return;
  showChat();
  stopSpeaking();
  if (!cid) {
    const c = await api("/conversations", "POST");
    cid = c.id;
  }
  const payload = {
    text,
    action: kind,
    mode: $("#mode").value,
    document_ids: attached.map((d) => d.id),
    images: image ? [image.base64] : [],
  };
  setBusy(true);
  $("#welcome").hidden = true;
  $("#activity").textContent = "Connecting to local engine…";
  if (kind === "send") messageElement("user", text);
  const el = messageElement("assistant");
  $("#chat-page").classList.add("has-messages");
  let output = "",
    lastStatus = "",
    queuedFrame = 0;
  const renderOutput = () => {
    el.querySelector(".message-content").textContent = output;
    const scroll = $("#chat-scroll");
    if (scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 140)
      scrollBottom();
    queuedFrame = 0;
  };
  aborter = new AbortController();
  try {
    const r = await fetch("/api/conversations/" + cid + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Laila-Token": token },
      body: JSON.stringify(payload),
      signal: aborter.signal,
    });
    if (!r.ok) {
      const err = await r.json();
      throw Error(
        typeof err.detail === "string"
          ? err.detail
          : JSON.stringify(err.detail),
      );
    }
    prompt.value = "";
    const reader = r.body.getReader(),
      decoder = new TextDecoder();
    let buffer = "";
    const event = (data) => {
      if (data.type === "token") {
        output += data.text;
        if (!queuedFrame) queuedFrame = requestAnimationFrame(renderOutput);
      }
      if (data.type === "activity")
        $("#activity").textContent = data.text + "…";
      if (data.type === "error") {
        toast(data.text);
        lastStatus = "error";
        setAssistantState("offline", "Model error · check local setup");
      }
      if (data.type === "approval") {
        lastStatus = "approval";
        setAssistantState("approval");
      }
      if (data.type === "done") lastStatus = data.status;
    };
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      let index;
      while ((index = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, index);
        buffer = buffer.slice(index + 1);
        if (line.trim()) event(JSON.parse(line));
      }
      if (done) {
        if (buffer.trim()) event(JSON.parse(buffer));
        break;
      }
    }
  } catch (e) {
    if (e.name !== "AbortError") {
      toast(e.message);
      setAssistantState("offline", "Connection interrupted · check the local model");
    }
  } finally {
    if (queuedFrame) cancelAnimationFrame(queuedFrame);
    if (output) renderOutput();
    setBusy(false);
    aborter = null;
    $("#activity").textContent = "";
    const docs = attached;
    const img = image;
    await openChat(cid);
    attached = docs;
    image = img;
    attachments();
    if (
      output &&
      lastStatus === "complete" &&
      (settings.auto_speech || voiceTurn)
    ) {
      speak(output).catch((e) => toast(e.message));
    }
    voiceTurn = false;
    if (document.activeElement === prompt || document.activeElement === document.body)
      prompt.focus();
  }
}
function pageHead(title, sub, button = "") {
  return `<div class="page-head"><div><h1>${title}</h1><p>${sub}</p></div>${button}</div>`;
}
function empty(title, sub) {
  return `<div class="empty-state"><h2>${title}</h2><p>${sub}</p></div>`;
}
async function navigate(target) {
  if (target === "chat") {
    showChat();
    return;
  }
  page = target;
  $("#chat-page").hidden = true;
  $("#workspace-page").hidden = false;
  $("#page-title").textContent = target[0].toUpperCase() + target.slice(1);
  $("#sidebar").classList.remove("open");
  $$("[data-page]").forEach((b) =>
    b.classList.toggle("active", b.dataset.page === target),
  );
  $("#workspace-page").innerHTML =
    '<p class="muted">Loading your workspace…</p>';
  await {
    today: todayPage,
    profile: profilePage,
    desktop: desktopPage,
    documents: documentsPage,
    tasks: tasksPage,
    notes: notesPage,
    memory: memoryPage,
    models: modelsPage,
    settings: settingsPage,
  }[target]();
  if (["today", "tasks", "desktop"].includes(target))
    await refreshDailyRail();
}
async function documentsPage() {
  docList = await api("/documents");
  const p = $("#workspace-page");
  p.innerHTML =
    pageHead(
      "Your knowledge, connected.",
      "Upload documents, index them locally, and inspect the excerpts behind each answer.",
      '<button class="primary" id="add-doc">+ Add documents</button>',
    ) +
    '<div class="search-row"><input id="doc-query" placeholder="Search indexed document contents" aria-label="Search documents"><button id="search-docs" class="subtle">Search</button></div><div id="doc-results"></div><div id="doc-list"></div>';
  $("#add-doc").onclick = () => $("#file-input").click();
  $("#search-docs").onclick = action(async () => {
    const result = await api("/documents/search", "POST", {
      query: $("#doc-query").value,
    });
    $("#doc-results").replaceChildren();
    sourcePanel($("#doc-results"), result);
    if (!result.length) toast("No indexed documents matched");
  });
  const list = $("#doc-list");
  if (!docList.length)
    list.innerHTML = empty(
      "A home for your knowledge",
      "PDF, DOCX, TXT, MD, CSV, JSON and XLSX · up to 10 MB per file",
    );
  for (const d of docList) {
    const c = document.createElement("article");
    c.className = "card";
    c.innerHTML = `<div class="card-row"><div><h3>${E(d.filename)}</h3><span class="small">${E(date(d.created_at))} ${d.embedding_model ? "· " + E(d.embedding_model) : ""}</span></div><span class="status ${E(d.status)}">${E(d.status)}</span></div>${d.error ? '<p class="message-error">' + E(d.error) + "</p>" : ""}<div class="actions"></div>`;
    const a = c.querySelector(".actions");
    msgButton(
      a,
      d.status === "indexed" ? "Reindex" : "Index locally",
      async () => {
        toast("Indexing with your local embedding model…");
        await api("/documents/" + d.id + "/index", "POST");
        await documentsPage();
        toast("Document indexed");
      },
    );
    msgButton(a, "Ask about this", () => {
      attached = [d];
      attachments();
      showChat();
      $("#prompt").focus();
    });
    if (/\.(csv|json|xlsx)$/i.test(d.filename))
      msgButton(a, "Analyze data", () => dataDialog(d));
    msgButton(a, "Delete", async () => {
      if (confirm("Delete this document and its retrieval index?")) {
        await api("/documents/" + d.id, "DELETE");
        attached = attached.filter((x) => x.id !== d.id);
        attachments();
        await documentsPage();
      }
    });
    list.append(c);
  }
}
async function upload(file) {
  if (busy) throw Error("Wait for generation before attaching a file.");
  if (/\.(png|jpe?g|webp)$/i.test(file.name)) {
    if (file.size > 8_000_000) throw Error("Image limit is 8 MB.");
    const encoded = await new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result.split(",")[1]);
      r.onerror = reject;
      r.readAsDataURL(file);
    });
    image = { name: file.name, base64: encoded };
    attachments();
    showChat();
    toast("Image attached for the next turn");
    return;
  }
  const form = new FormData();
  form.append("file", file);
  toast("Saving document locally…");
  const d = await api("/documents", "POST", form);
  if (page === "documents") await documentsPage();
  else {
    attached.push(d);
    attachments();
  }
  try {
    toast("Indexing document locally…");
    await api("/documents/" + d.id + "/index", "POST");
    toast("Document ready");
  } catch (e) {
    toast("File saved. Indexing needs attention: " + e.message);
  }
  if (page === "documents") await documentsPage();
}
async function notesPage(query = "") {
  const notes = await api("/notes?q=" + encodeURIComponent(query));
  $("#workspace-page").innerHTML =
    pageHead(
      "Keep a good thought.",
      "Notes are stored on your laptop. Agent-created notes require your approval.",
      '<button id="add-note" class="primary">+ New note</button>',
    ) +
    '<div class="search-row"><input id="note-query" placeholder="Search notes" value="' +
    E(query) +
    '"><button id="note-search" class="subtle">Search</button></div><div id="notes-list" class="card-grid"></div>';
  $("#add-note").onclick = () => noteEditor();
  $("#note-search").onclick = action(() => notesPage($("#note-query").value));
  if (!notes.length)
    $("#notes-list").innerHTML = empty(
      "Space for your ideas",
      "Capture something you want to come back to.",
    );
  for (const n of notes) {
    const c = document.createElement("article");
    c.className = "card";
    c.innerHTML = `<h3>${E(n.title)}</h3><p class="note-content">${E(n.content)}</p><span class="small">${E(date(n.updated_at))}</span><div class="actions"></div>`;
    msgButton(c.querySelector(".actions"), "Edit", () => noteEditor(n));
    msgButton(c.querySelector(".actions"), "Delete", async () => {
      if (confirm("Delete this note?")) {
        await api("/notes/" + n.id, "DELETE");
        await notesPage();
      }
    });
    $("#notes-list").append(c);
  }
}
function noteEditor(n = {}) {
  editor(
    n.id ? "Edit note" : "New note",
    field("title", "Title", n.title || "") +
      `<label class="field">Note<textarea name="content" rows="7" required>${E(n.content || "")}</textarea></label>`,
    async (f) => {
      await api("/notes" + (n.id ? "/" + n.id : ""), n.id ? "PUT" : "POST", {
        title: f.get("title"),
        content: f.get("content"),
      });
      await notesPage();
    },
  );
}
async function tasksPage() {
  const tasks = await api("/tasks");
  const pending = tasks.filter((t) => !t.completed).length;
  $("#workspace-page").innerHTML =
    pageHead(
      "Make room for progress.",
      `${pending} open tasks · Due dates are tracked locally. Notifications are not enabled in this release.`,
      '<button id="add-task" class="primary">+ New task</button>',
    ) + '<div id="tasks-list"></div>';
  $("#add-task").onclick = () => taskEditor();
  if (!tasks.length)
    $("#tasks-list").innerHTML = empty(
      "Start with one small step",
      "Create a task and give it a place in your day.",
    );
  for (const t of tasks) {
    const c = document.createElement("article");
    c.className = "card";
    c.innerHTML = `<div class="card-row"><h3 class="${t.completed ? "task-complete" : ""}">${E(t.title)}</h3><span class="status">${E(t.priority)}</span></div><span class="small">${t.due_date ? "Due " + E(t.due_date) : "No due date"}</span><div class="actions"></div>`;
    const a = c.querySelector(".actions");
    msgButton(a, t.completed ? "Reopen" : "Mark complete", async () => {
      await api("/tasks/" + t.id, "PUT", {
        title: t.title,
        due_date: t.due_date,
        priority: t.priority,
        completed: !t.completed,
      });
      await tasksPage();
    });
    msgButton(a, "Edit", () => taskEditor(t));
    msgButton(a, "Delete", async () => {
      if (confirm("Delete this task?")) {
        await api("/tasks/" + t.id, "DELETE");
        await tasksPage();
      }
    });
    $("#tasks-list").append(c);
  }
  await refreshDailyRail();
}
function taskEditor(t = {}) {
  editor(
    t.id ? "Edit task" : "New task",
    field("title", "Task", t.title || "") +
      `<label class="field">Due date<input name="due_date" type="date" value="${E(t.due_date?.slice(0, 10) || "")}"></label><label class="field">Priority<select name="priority">${["low", "normal", "high"].map((x) => `<option ${x === (t.priority || "normal") ? "selected" : ""}>${x}</option>`).join("")}</select></label>`,
    async (f) => {
      await api("/tasks" + (t.id ? "/" + t.id : ""), t.id ? "PUT" : "POST", {
        title: f.get("title"),
        due_date: f.get("due_date") || null,
        priority: f.get("priority"),
        completed: !!t.completed,
      });
      await tasksPage();
    },
  );
}
async function memoryPage() {
  const memories = await api("/memories");
  settings = await api("/settings");
  $("#workspace-page").innerHTML =
    pageHead(
      "Remember, on your terms.",
      "Only memories you explicitly add here are retained as long-term preferences. Chat history is stored separately.",
      '<button id="add-memory" class="primary">+ Add memory</button>',
    ) +
    `<div class="card"><label class="check-field"><input type="checkbox" id="memory-enabled" ${settings.memory_enabled ? "checked" : ""}>Use these memories in new responses</label><p class="small">Disabling memory stops its use in prompts; it does not delete it.</p><button id="clear-memory" class="subtle danger-text">Clear all memories</button></div><div id="memory-list"></div>`;
  $("#memory-enabled").onchange = action(async (e) => {
    settings.memory_enabled = e.target.checked;
    settings = await api("/settings", "PUT", settings);
  });
  const edit = (m) =>
    editor(
      m.id ? "Edit memory" : "Add memory",
      `<label class="field">What should Laila remember?<textarea name="content" maxlength="1000" rows="4" required>${E(m.content || "")}</textarea></label>`,
      async (f) => {
        await api(
          "/memories" + (m.id ? "/" + m.id : ""),
          m.id ? "PUT" : "POST",
          { content: f.get("content") },
        );
        await memoryPage();
      },
    );
  $("#add-memory").onclick = () => edit({});
  $("#clear-memory").onclick = action(async () => {
    if (confirm("Clear all long-term memories?")) {
      await api("/memories", "DELETE");
      await memoryPage();
    }
  });
  for (const m of memories) {
    const c = document.createElement("article");
    c.className = "card";
    c.innerHTML = `<p class="note-content">${E(m.content)}</p><div class="actions"></div>`;
    msgButton(c.querySelector(".actions"), "Edit", () => edit(m));
    msgButton(c.querySelector(".actions"), "Delete", async () => {
      await api("/memories/" + m.id, "DELETE");
      await memoryPage();
    });
    $("#memory-list").append(c);
  }
}
async function modelsPage() {
  const data = await api("/system");
  settings = await api("/settings");
  const s = data.system;
  $("#workspace-page").innerHTML =
    pageHead(
      "Your local engine.",
      "Models run through Ollama. Download models separately before going offline.",
      '<button id="refresh-models" class="subtle">Refresh status</button>',
    ) +
    `<div class="card-grid"><div class="card"><h3>Machine</h3><p class="muted">${E(s.os)}<br>${E(s.cpu)} · ${s.cpu_threads} threads<br>${s.ram_gb} GB RAM · ${s.available_ram_gb} GB available<br>GPU: ${E(s.gpu)}<br>Python ${E(s.python)}</p></div><div class="card"><h3>Ollama</h3><p class="muted">Service: ${data.ollama.running ? "Running" : "Not reachable"}<br>Executable on PATH: ${data.ollama.installed_on_path ? "Found" : "Not found (installation may still exist)"}<br>Selected model: ${E(settings.model)}<br>Embedding model: ${E(settings.embedding_model)}</p></div></div><div id="models-list"></div><div class="card"><h3>First-time model setup</h3><p class="muted">In PowerShell after installing Ollama:</p><pre>ollama pull llama3.2\nollama pull nomic-embed-text</pre><p class="muted">Downloads need internet. Laila never pulls models automatically. Run <code>ollama serve</code> if the Ollama service is not running. Set <code>OLLAMA_NO_CLOUD=1</code> for the Ollama service and restart it to enforce local-only Ollama operation.</p></div>`;
  $("#refresh-models").onclick = action(async () => {
    await refreshModels();
    await modelsPage();
  });
  for (const m of data.ollama.models) {
    const c = document.createElement("article");
    c.className = "card card-row";
    c.innerHTML = `<div><h3>${E(m.name)}</h3><span class="small">${(m.size / 1e9).toFixed(2)} GB · ${E(m.details?.parameter_size || "")}</span></div>`;
    const b = document.createElement("button");
    b.className = "primary";
    b.textContent = settings.model === m.name ? "Selected" : "Use model";
    b.disabled = settings.model === m.name;
    b.onclick = action(async () => {
      settings.model = m.name;
      settings = await api("/settings", "PUT", settings);
      await refreshModels();
      await modelsPage();
    });
    c.append(b);
    $("#models-list").append(c);
  }
}
async function settingsPage() {
  settings = await api("/settings");
  let voices = [],
    voiceStatus = "";
  try {
    const v = await api("/voice/status");
    voices = v.voices;
    voiceStatus = `Transcription package: ${v.stt_installed ? "installed" : "not installed"} · Local model folder: ${v.stt_model_present ? "found" : "not configured"} · Windows speech: ${v.tts_platform_supported ? "supported" : "unavailable on this OS"}`;
  } catch (e) {
    voiceStatus = e.message;
  }
  const check = (key, label) =>
    `<label class="check-field"><input type="checkbox" name="${key}" ${settings[key] ? "checked" : ""}>${label}</label>`;
  $("#workspace-page").innerHTML =
    pageHead(
      "A workspace that fits you.",
      "Settings stay on this device. No cloud API keys are needed.",
    ) +
    `<form id="settings-form" class="settings-form"><div class="card"><h2>Local intelligence</h2><div class="form-grid">${field("model", "Chat model", settings.model)}${field("embedding_model", "Embedding model", settings.embedding_model)}${field("temperature", "Temperature (0–2)", settings.temperature, "number")}${field("context_length", "Context length (2,048–65,536)", settings.context_length, "number")}<label class="field full">Personality / system prompt<textarea name="system_prompt" rows="6" required>${E(settings.system_prompt)}</textarea></label></div>${check("tools_enabled", "Enable safe agent tools and approval requests")}${check("rag_enabled", "Enable retrieval for attached documents")}${check("memory_enabled", "Use explicit long-term memories")}<p class="muted">Changing embedding models requires reindexing existing documents.</p></div><div class="card"><h2>Approved folders</h2><label class="field">One absolute path per line<textarea name="approved_directories" rows="3" placeholder="D:\\LailaWorkspace">${E(settings.approved_directories.join("\n"))}</textarea><small>Only add dedicated folders. No entire drives, home folders or system directories. File tools can read supported documents; they cannot modify your files.</small></label></div><div class="card"><h2>Offline voice</h2><p class="muted">${E(voiceStatus)}</p><label class="field">Local faster-whisper model folder<input name="stt_model_path" value="${E(settings.stt_model_path)}" placeholder="C:\\Laila-AI\\data\\models\\whisper-base"></label><label class="field">Windows voice<select name="voice"><option value="">Windows default</option>${voices.map((v) => `<option value="${E(v)}" ${v === settings.voice ? "selected" : ""}>${E(v)}</option>`).join("")}</select></label><div class="form-grid">${field("speech_rate", "Speaking rate (−10 to 10)", settings.speech_rate, "number")}${field("speech_volume", "Volume (0–100)", settings.speech_volume, "number")}</div>${check("auto_speech", "Speak every completed response automatically")}</div><button class="primary" type="submit">Save settings</button> <button class="subtle" id="export-data" type="button">Export personal data</button><p class="muted">Local data is stored as unencrypted files. Use Windows device encryption for protection at rest.</p></form>`;
  $('#settings-form [name="temperature"]').step = "0.1";
  $("#settings-form").onsubmit = action(async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const updated = { ...settings };
    for (const k of [
      "model",
      "embedding_model",
      "system_prompt",
      "stt_model_path",
      "voice",
    ])
      updated[k] = f.get(k);
    for (const k of [
      "temperature",
      "context_length",
      "speech_rate",
      "speech_volume",
    ])
      updated[k] = Number(f.get(k));
    for (const k of [
      "tools_enabled",
      "rag_enabled",
      "memory_enabled",
      "auto_speech",
    ])
      updated[k] = f.has(k);
    updated.approved_directories = f
      .get("approved_directories")
      .split("\n")
      .map((x) => x.trim())
      .filter(Boolean);
    settings = await api("/settings", "PUT", updated);
    toast("Settings saved");
    await refreshModels();
  });
  $("#export-data").onclick = action(async () => {
    const data = await api("/export");
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "laila-export.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}
async function dataDialog(d) {
  editor(
    "Analyze " + d.filename,
    `<p class="muted">Safe built-in analysis. No generated code is executed. Optional column names must match the file.</p>${field("document_id", "Document ID", d.id)}<div class="form-grid"><label class="field">Group by<input name="group_by"></label><label class="field">Value column<input name="value_column"></label><label class="field">Aggregate<select name="aggregate"><option>mean</option><option>sum</option><option>count</option><option>min</option><option>max</option></select></label><label class="field">Sort by<input name="sort_by"></label><label class="field">Filter column<input name="filter_column"></label><label class="field">Filter equals<input name="filter_value"></label></div>`,
    async (f) => {
      const args = Object.fromEntries(f.entries());
      for (const k of [
        "group_by",
        "value_column",
        "sort_by",
        "filter_column",
        "filter_value",
      ])
        if (!args[k]) args[k] = null;
      const result = await api("/analysis", "POST", args);
      $("#workspace-page").innerHTML =
        pageHead(
          E(d.filename),
          "Computed locally from your uploaded data. Preview and chart show up to 30 rows.",
          '<button id="back-docs" class="subtle">Back to documents</button>',
        ) +
        `<div class="card"><h3>${result.rows} rows · ${result.columns.length} columns</h3><table class="data-table"><thead><tr><th>Column</th><th>Type</th><th>Missing</th></tr></thead><tbody>${result.columns.map((c) => `<tr><td>${E(c.name)}</td><td>${E(c.dtype)}</td><td>${c.missing}</td></tr>`).join("")}</tbody></table></div><canvas id="chart" class="data-chart" width="1000" height="300" aria-label="Bar chart of computed values"></canvas><div class="card"><h3>Preview</h3><table class="data-table"><thead><tr>${result.columns.map((c) => "<th>" + E(c.name) + "</th>").join("")}</tr></thead><tbody>${result.preview.map((r) => "<tr>" + result.columns.map((c) => "<td>" + E(r[c.name]) + "</td>").join("") + "</tr>").join("")}</tbody></table></div><details class="card"><summary>Statistics and correlations</summary><pre class="note-content">${E(JSON.stringify({ statistics: result.statistics, correlations: result.correlations }, null, 2))}</pre></details>`;
      $("#back-docs").onclick = action(documentsPage);
      drawChart(result.chart);
    },
  );
}
function drawChart(data) {
  const c = $("#chart"),
    g = c.getContext("2d");
  g.fillStyle = "#0c1420";
  g.fillRect(0, 0, c.width, c.height);
  g.font = "13px Segoe UI";
  g.fillStyle = "#a8bddb";
  if (!data.length) {
    g.fillText("No numeric values to chart.", 30, 50);
    return;
  }
  const hi = Math.max(0, ...data.map((x) => x.value)),
    lo = Math.min(0, ...data.map((x) => x.value)),
    range = hi - lo || 1;
  const y = (v) => 240 - ((v - lo) / range) * 190;
  const width = 850 / data.length;
  g.strokeStyle = "#334c6c";
  g.beginPath();
  g.moveTo(80, y(0));
  g.lineTo(940, y(0));
  g.stroke();
  g.fillText(hi.toFixed(2), 8, 50);
  g.fillText(lo.toFixed(2), 8, 242);
  data.forEach((d, i) => {
    const x = 85 + i * width;
    g.fillStyle = "#709ffc";
    g.fillRect(
      x,
      Math.min(y(d.value), y(0)),
      Math.max(2, width - 7),
      Math.max(1, Math.abs(y(d.value) - y(0))),
    );
    g.fillStyle = "#a8bddb";
    g.save();
    g.translate(x, 265);
    g.rotate(-0.25);
    g.fillText(d.label.slice(0, 12), 0, 0);
    g.restore();
  });
}
async function speak(text) {
  stopSpeaking();
  const serial = speechSerial;
  $("#activity").textContent = "Preparing speech locally…";
  $("#stop-speaking").hidden = false;
  try {
    const r = await fetch("/api/voice/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Laila-Token": token },
      body: JSON.stringify({ text: text.slice(0, 6000) }),
    });
    if (!r.ok) {
      const e = await r.json();
      throw Error(e.detail);
    }
    const blob = await r.blob();
    if (serial !== speechSerial) return;
    const url = URL.createObjectURL(blob);
    audio = new Audio(url);
    audio.onplay = () => {
      if (serial === speechSerial) setAssistantState("speaking");
    };
    audio.onended = () => {
      URL.revokeObjectURL(url);
      if (serial === speechSerial) stopSpeaking();
    };
    audio._url = url;
    await audio.play();
    $("#activity").textContent = "Laila is speaking…";
  } catch (e) {
    stopSpeaking();
    throw e;
  }
}
function stopSpeaking() {
  speechSerial++;
  if (audio) {
    audio.pause();
    if (audio._url) URL.revokeObjectURL(audio._url);
    audio = null;
  }
  $("#stop-speaking").hidden = true;
  if (!busy) $("#activity").textContent = "";
  if (assistantState === "speaking")
    setAssistantState(localModelReady ? "idle" : "offline");
}
async function record() {
  if (recorder?.state === "recording") {
    recorder.stop();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia)
    throw Error(
      "Microphone capture requires localhost and a supported browser.",
    );
  const v = await api("/voice/status");
  if (!v.stt_installed || !v.stt_model_present)
    throw Error(
      "Configure local speech recognition in Settings first. See README voice setup.",
    );
  recordStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mime = ["audio/webm", "audio/mp4", "audio/ogg"].find((x) =>
    MediaRecorder.isTypeSupported(x),
  );
  recorder = new MediaRecorder(recordStream, mime ? { mimeType: mime } : {});
  let chunks = [],
    cancelled = false,
    handled = false;
  const releaseRecording = () => {
    recordStream?.getTracks().forEach((track) => track.stop());
    recordStream = null;
    recorder = null;
    $("#mic").classList.remove("recording");
    $("#mic").innerHTML = '<span aria-hidden="true">◖</span><span>Talk</span>';
    $("#cancel-recording").hidden = true;
  };
  recorder.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data);
  };
  $("#mic").classList.add("recording");
  $("#mic").innerHTML = '<span aria-hidden="true">■</span><span>Stop</span>';
  $("#activity").textContent = "Recording locally · maximum 60 seconds";
  setAssistantState("recording");
  $("#cancel-recording").hidden = false;
  $("#cancel-recording").onclick = () => {
    cancelled = true;
    recorder.stop();
  };
  const timer = setTimeout(() => {
    if (recorder?.state === "recording") recorder.stop();
  }, 60000);
  recorder.onerror = () => {
    if (handled) return;
    handled = true;
    clearTimeout(timer);
    releaseRecording();
    $("#activity").textContent = "";
    setAssistantState(localModelReady ? "idle" : "offline");
    toast("Recording failed. Check microphone access and try again.");
  };
  recorder.onstop = async () => {
    if (handled) return;
    handled = true;
    clearTimeout(timer);
    const mimeType = recorder.mimeType;
    releaseRecording();
    if (cancelled) {
      $("#activity").textContent = "";
      setAssistantState(localModelReady ? "idle" : "offline");
      return;
    }
    try {
      $("#activity").textContent = "Transcribing on your laptop…";
      setAssistantState("transcribing");
      const form = new FormData();
      const type = mimeType,
        ext = type.includes("mp4")
          ? "mp4"
          : type.includes("ogg")
            ? "ogg"
            : "webm";
      form.append("file", new Blob(chunks, { type }), "recording." + ext);
      const result = await api("/voice/transcribe", "POST", form);
      $("#prompt").value = result.text;
      if (result.text.trim()) {
        voiceTurn = true;
        await send();
      } else toast("No speech detected");
    } catch (e) {
      toast(e.message);
      setAssistantState(localModelReady ? "idle" : "offline");
    } finally {
      if (!busy) {
        $("#activity").textContent = "";
        if (assistantState === "transcribing")
          setAssistantState(localModelReady ? "idle" : "offline");
      }
    }
  };
  try {
    recorder.start();
  } catch (e) {
    clearTimeout(timer);
    releaseRecording();
    $("#activity").textContent = "";
    setAssistantState(localModelReady ? "idle" : "offline");
    throw e;
  }
}
$("#new-chat").onclick = action(newChat);
$("#composer").onsubmit = action((e) => {
  e.preventDefault();
  return send();
});
$("#prompt").onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    action(send)();
  }
};
$("#stop").onclick = action(async () => {
  voiceTurn = false;
  stopSpeaking();
  await api("/conversations/" + cid + "/stop", "POST");
  aborter?.abort();
});
$("#chat-search").oninput = () => {
  clearTimeout(history.timer);
  history.timer = setTimeout(action(history), 200);
};
$("#rename-chat").onclick = () => {
  if (!cid) return;
  editor(
    "Rename conversation",
    field("title", "Title", current?.title || ""),
    async (f) => {
      await api("/conversations/" + cid, "PATCH", {
        title: f.get("title"),
        pinned: !!current?.pinned,
      });
      await openChat(cid);
    },
  );
};
$("#pin-chat").onclick = action(async () => {
  if (!cid) return;
  await api("/conversations/" + cid, "PATCH", {
    title: current.title,
    pinned: !current.pinned,
  });
  await openChat(cid);
});
$("#clear-chat").onclick = action(async () => {
  if (cid && confirm("Clear all messages in this conversation?")) {
    await api("/conversations/" + cid + "/messages", "DELETE");
    await openChat(cid);
  }
});
$("#delete-chat").onclick = action(async () => {
  if (cid && confirm("Delete this conversation?")) {
    await api("/conversations/" + cid, "DELETE");
    await newChat();
  }
});
$$("[data-page]").forEach((b) =>
  b.addEventListener(
    "click",
    action(() => navigate(b.dataset.page)),
  ),
);
$$("[data-prompt]").forEach(
  (b) =>
    (b.onclick = () => {
      $("#mode").value = b.dataset.mode;
      $("#prompt").value = b.dataset.prompt;
      $("#prompt").focus();
    }),
);
$("#settings-shortcut").onclick = action(() => navigate("settings"));
$("#menu").onclick = () => {
  const open = $("#sidebar").classList.toggle("open");
  $("#menu").setAttribute("aria-expanded", String(open));
  $("#drawer-scrim").hidden = !open;
};
$("#day-toggle").onclick = () => {
  const open = $("#daily-rail").classList.toggle("open");
  $("#day-toggle").setAttribute("aria-expanded", String(open));
  $("#drawer-scrim").hidden = !open;
};
$("#day-close").onclick = () => {
  $("#daily-rail").classList.remove("open");
  $("#day-toggle").setAttribute("aria-expanded", "false");
  $("#drawer-scrim").hidden = true;
};
$("#drawer-scrim").onclick = () => {
  $("#sidebar").classList.remove("open");
  $("#daily-rail").classList.remove("open");
  $("#menu").setAttribute("aria-expanded", "false");
  $("#day-toggle").setAttribute("aria-expanded", "false");
  $("#drawer-scrim").hidden = true;
};
$("#rail-collapse").onclick = () => {
  const collapsed = $(".app-shell").classList.toggle("rail-collapsed");
  $("#rail-collapse").setAttribute("aria-expanded", String(!collapsed));
  $("#rail-collapse").title = collapsed
    ? "Expand daily overview"
    : "Collapse daily overview";
};
window.addEventListener("resize", () => {
  if (window.innerWidth > 920) {
    $("#sidebar").classList.remove("open");
    $("#daily-rail").classList.remove("open");
    $("#drawer-scrim").hidden = true;
    $("#menu").setAttribute("aria-expanded", "false");
    $("#day-toggle").setAttribute("aria-expanded", "false");
  }
});
$("#focus-toggle").onclick = () => {
  const enabled = document.body.classList.toggle("focus-mode");
  $("#focus-toggle").setAttribute("aria-pressed", String(enabled));
};
$("#motion-toggle").onclick = () =>
  setMotionOff(!document.body.classList.contains("motion-off"));
$("#attach-button").onclick = () => $("#file-input").click();
$("#file-input").onchange = action(async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (file) await upload(file);
});
$("#mic").onclick = action(record);
$("#stop-speaking").onclick = stopSpeaking;
$("#close-editor").onclick = $("#cancel-editor").onclick = () =>
  $("#editor").close();
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "k") {
    e.preventDefault();
    action(newChat)();
  }
});
async function init() {
  $(".toolbar-actions").hidden = true;
  const savedMotion = localStorage.getItem("laila-motion-off");
  setMotionOff(
    savedMotion === "on" ||
      (savedMotion === null && window.matchMedia("(prefers-reduced-motion: reduce)").matches),
  );
  if (localStorage.getItem("laila-focus-mode") === "on") {
    document.body.classList.add("focus-mode");
    $("#focus-toggle").setAttribute("aria-pressed", "true");
  }
  $("#focus-toggle").addEventListener("click", () =>
    localStorage.setItem("laila-focus-mode", document.body.classList.contains("focus-mode") ? "on" : "off"),
  );
  syncClock();
  setInterval(syncClock, 30000);
  const portraitVideo = $("#laila-video");
  let resumePortraitVideo = false;
  portraitVideo.onerror = () =>
    toast("The local portrait video could not be played. Check the MP4 codec or use its poster image.");
  document.addEventListener("visibilitychange", () => {
    document.body.classList.toggle("page-hidden", document.hidden);
    if (document.hidden) {
      resumePortraitVideo = !portraitVideo.paused;
      portraitVideo.pause();
    } else if (resumePortraitVideo) {
      resumePortraitVideo = false;
      portraitVideo.play().catch(() => {});
    }
  });
  const s = await api("/session");
  $("#app-version").textContent = "v" + s.version;
  token = s.token;
  settings = await api("/settings");
  await history();
  await refreshModels();
  await refreshDailyRail();
}
init().catch((e) => {
  toast(e.message);
  $("#model-badge").textContent = "Backend unavailable";
  $("#model-badge").dataset.state = "offline";
  setAssistantState("offline", "Start the local server to reconnect");
  $("#alert").hidden = false;
  $("#alert").textContent =
    "Unable to reach Laila’s backend. Run scripts/run_laila.ps1 and refresh this page.";
});

// Personal workspace: explicit records, no hidden activity tracking.
function personalField(label, name, value = "", type = "text", extra = "") {
  return `<label class="field">${E(label)}<input name="${E(name)}" type="${type}" value="${E(value)}" ${extra}></label>`;
}
function personalText(label, name, value) {
  return `<label class="field">${E(label)}<textarea name="${E(name)}" rows="3" maxlength="800">${E(value)}</textarea></label>`;
}
async function profilePage() {
  const p = await api('/personal/profile');
  $('#workspace-page').innerHTML = pageHead('Make Laila yours.', 'Only details you save here are added to your profile. You can change or clear them anytime.') +
    `<form id="profile-form" class="settings-form"><div class="card"><div class="form-grid">
    ${personalField('What should I call you?', 'name', p.name, 'text', 'maxlength="80"')}
    ${personalField('Timezone', 'timezone', p.timezone, 'text', 'required')}
    </div>${personalText('Goals — what are you working toward?', 'goals', p.goals)}
    ${personalText('Subjects and current projects', 'subjects', p.subjects)}
    ${personalText('Routine — college, study and rest times', 'routine', p.routine)}
    ${personalText('How should Laila help you?', 'preferences', p.preferences)}
    <label><input type="checkbox" name="use_in_chat" ${p.use_in_chat ? 'checked' : ''}> Use this profile and planning context in chat (also requires Memory enabled)</label></div>
    <div class="actions"><button class="primary" type="submit">Save profile</button><button class="subtle" type="button" id="clear-profile">Clear profile</button></div></form>`;
  $('#profile-form').onsubmit = action(async e => {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.target));
    values.use_in_chat = e.target.elements.use_in_chat.checked;
    await api('/personal/profile', 'PUT', values); toast('Profile saved');
  });
  $('#clear-profile').onclick = action(async () => {
    if (confirm('Clear your profile and disable its use in chat? Existing chat messages remain.')) {
      await api('/personal/profile', 'DELETE'); await profilePage();
    }
  });
}
function localInput(iso) {
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0,16);
}
async function startPersonalChat(text, mode='chat') {
  if (busy) { toast('Stop the current response first.'); return; }
  await newChat(); $('#mode').value=mode; $('#prompt').value=text; $('#prompt').focus();
}
async function todayPage(selectedDay) {
  const [data, p] = await Promise.all([api('/personal/dashboard' + (selectedDay ? '?day='+encodeURIComponent(selectedDay) : '')), api('/personal/profile')]);
  const workspace=$('#workspace-page');
  workspace.innerHTML=pageHead(`A little progress, ${E(p.name || 'each day')}.`, 'Plan intentionally. Record what you actually complete. Leave room to rest.') +
    `<div class="personal-summary"><div class="card"><span class="eyebrow">SELECTED DAY</span><h2>${E(data.date)}</h2><label class="field">View date<input id="plan-day" type="date" value="${E(data.date)}"></label><p class="muted">${E(data.timezone)}</p></div><div class="card"><span class="eyebrow">LAST 7 DAYS · ENDING SELECTED DAY</span><h2>${data.week_minutes} minutes</h2><p>${data.week_sessions} logged study sessions</p><p class="muted">Based only on your study logs.</p></div><div class="card"><span class="eyebrow">YOUR NEXT STEP</span><h2>${data.plan.filter(x=>!x.completed).length} planned blocks</h2><div class="actions"><button class="subtle" id="morning-check">Morning check-in</button><button class="subtle" id="evening-check">Evening review</button></div></div></div>
    <div class="card"><div class="card-row personal-reminder-row"><div><h2>Gentle reminders</h2><p class="muted">In-app reminders for today's schedule. This tab must stay open and your laptop awake. Closed-tab and phone notifications are not supported.</p></div><label><input type="checkbox" id="reminders-enabled" ${localStorage.getItem('laila-reminders')==='on'?'checked':''}> Enable in this browser</label></div><div id="reminder-status" role="status"></div></div>
    <div class="personal-columns"><div><div class="card"><h2>Plan a block</h2><form id="plan-form" class="settings-form">
    ${personalField('Title','title','','text','required maxlength="200"')}
    ${personalField('Start — browser local time','starts_at',localInput(new Date()),'datetime-local','required')}
    <div class="form-grid">${personalField('Minutes','minutes','30','number','required min="5" max="720"')}<label class="field">Category<select name="category"><option value="study">Study</option><option value="project">Project</option><option value="personal">Personal</option><option value="content">Content creation</option></select></label></div>
    <button class="primary" type="submit">Add block</button></form></div><div id="plan-items"></div></div>
    <div><div class="card"><h2>Log your learning</h2><form id="study-form" class="settings-form">
    ${personalField('Subject','subject','','text','required maxlength="100"')}${personalField('Topic','topic','','text','required maxlength="200"')}
    <div class="form-grid">${personalField('Minutes studied','minutes','25','number','required min="1" max="720"')}${personalField('Confidence · 1 low, 5 high','confidence','3','number','required min="1" max="5"')}${personalField('Studied on','studied_on',data.date,'date','required')}${personalField('Review on (optional)','review_on','','date')}</div>
    ${personalText('What did you learn or struggle with?','notes','')}<button class="primary" type="submit">Save study log</button></form></div><div id="study-items"></div></div></div>
    <div class="card"><h2>Top task priorities</h2><div id="personal-tasks"></div><button class="subtle" id="all-tasks">Manage all tasks</button></div>`;
  $('#plan-day').onchange=action(e=>todayPage(e.target.value));
  $('#reminders-enabled').onchange=e=>{localStorage.setItem('laila-reminders',e.target.checked?'on':'off');toast(e.target.checked?'In-app reminders enabled':'Reminders disabled');};
  $('#morning-check').onclick=()=>startPersonalChat('Help me plan today using my saved profile, schedule and tasks. Suggest three priorities and leave time for rest. Do not claim to save a plan without approval.');
  $('#evening-check').onclick=()=>startPersonalChat('Review my recorded progress today. Ask what went well and what I want to adjust tomorrow. Do not assume unfinished tasks were completed.');
  $('#all-tasks').onclick=action(()=>navigate('tasks'));
  $('#plan-form').onsubmit=action(async e=>{
    e.preventDefault();const v=Object.fromEntries(new FormData(e.target));
    v.starts_at=new Date(v.starts_at).toISOString();v.minutes=Number(v.minutes);
    const clash=data.plan.find(x=>!x.completed && new Date(v.starts_at)<new Date(new Date(x.starts_at).getTime()+x.minutes*60000) && new Date(x.starts_at)<new Date(new Date(v.starts_at).getTime()+v.minutes*60000));
    if(clash && !confirm('This overlaps “'+clash.title+'”. Add it anyway?'))return;
    await api('/personal/plan','POST',v);await todayPage(data.date);toast('Schedule block saved');
  });
  $('#study-form').onsubmit=action(async e=>{
    e.preventDefault();const v=Object.fromEntries(new FormData(e.target));v.minutes=Number(v.minutes);v.confidence=Number(v.confidence);v.review_on=v.review_on||null;
    await api('/personal/study','POST',v);await todayPage(data.date);toast('Study log saved');
  });
  if(!data.plan.length) $('#plan-items').innerHTML='<p class="empty-small">No blocks on this date. Start with one manageable session.</p>';
  for(const item of data.plan){
    const card=document.createElement('div');card.className='card';
    card.innerHTML=`<span class="eyebrow">${E(item.category)} · ${item.minutes} MIN</span><h3>${E(item.title)}</h3><p>${E(new Date(item.starts_at).toLocaleString([], {timeZone:data.timezone}))} · ${E(data.timezone)}</p><div class="actions"></div>`;
    msgButton(card.querySelector('.actions'),item.completed?'Reopen':'Mark complete',async()=>{await api('/personal/plan/'+item.id,'PUT',{...item,completed:!item.completed});await todayPage(data.date);});
    msgButton(card.querySelector('.actions'),'Remove',async()=>{if(confirm('Remove this schedule block?')){await api('/personal/plan/'+item.id,'DELETE');await todayPage(data.date);}});
    $('#plan-items').append(card);
  }
  for(const item of data.study_logs.slice(0,20)){
    const card=document.createElement('div');card.className='card';
    card.innerHTML=`<span class="eyebrow">${E(item.subject)} · ${E(item.studied_on)}</span><h3>${E(item.topic)}</h3><p>${item.minutes} minutes · Confidence ${item.confidence}/5</p><p>${E(item.notes)}</p><p class="muted">${item.review_on?'Review: '+E(item.review_on):'No revision date set'}</p><div class="actions"></div>`;
    msgButton(card.querySelector('.actions'),'Quiz me',()=>startPersonalChat('Quiz me on '+item.topic+' in '+item.subject+'. Ask one question at a time and wait for my answer.','study'));
    if(item.review_on) msgButton(card.querySelector('.actions'),'Clear review date',async()=>{await api('/personal/study/'+item.id,'PUT',{...item,review_on:null});await todayPage(data.date);});
    msgButton(card.querySelector('.actions'),'Remove',async()=>{if(confirm('Delete this study record?')){await api('/personal/study/'+item.id,'DELETE');await todayPage(data.date);}});
    $('#study-items').append(card);
  }
  $('#personal-tasks').innerHTML=data.tasks.slice(0,3).map(t=>`<p><b>${E(t.title)}</b> · ${E(t.priority)}${t.due_date?' · '+E(t.due_date):''}</p>`).join('')||'<p class="muted">No open tasks. Add tasks from the Tasks page.</p>';
  if(data.reviews.length) $('#study-items').insertAdjacentHTML('afterbegin',`<p class="muted">${data.reviews.length} revision dates are due on or before ${E(data.date)}. Clear a review date after revising, or log a new session.</p>`);
  await refreshDailyRail();
}
async function desktopPage(){
  const data=await api('/desktop/targets');
  $('#workspace-page').innerHTML=pageHead('Your desktop, with your permission.', 'Add installed apps or local folders. Laila asks before each launch. It cannot type into apps, delete files, send messages, or control your phone.')+
    `<div class="card"><p>${data.supported?'Windows desktop launching is available.':'Launches are only available when Laila is running on Windows.'}</p><form id="desktop-form" class="settings-form">${personalField('Name, e.g. VS Code','name','','text','required maxlength="80"')}<label class="field">Type<select name="kind"><option value="app">Application (.exe)</option><option value="folder">Folder</option></select></label>${personalField('Full local path — no command arguments','path','','text','required maxlength="1000"')}<button class="primary" type="submit" ${data.supported?'':'disabled'}>Add approved target</button></form><p class="muted">Choose applications you trust. You approve the exact path before a launch. No administrator access is requested.</p></div><div id="desktop-targets"></div>`;
  $('#desktop-form').onsubmit=action(async e=>{e.preventDefault();await api('/desktop/targets','POST',Object.fromEntries(new FormData(e.target)));await desktopPage();});
  for(const t of data.targets){
    const card=document.createElement('div');card.className='card';card.innerHTML=`<h3>${E(t.name)}</h3><p class="target-path">${E(t.path)}</p><div class="actions"></div>`;
    msgButton(card.querySelector('.actions'),'Request launch',()=>requestDesktopLaunch(t));
    msgButton(card.querySelector('.actions'),'Remove',async()=>{await api('/desktop/targets/'+t.id,'DELETE');await desktopPage();});
    $('#desktop-targets').append(card);
  }
  await refreshDailyRail();
}
async function requestDesktopLaunch(target) {
  if (busy) throw Error("Stop the current response first.");
  if (!cid) {
    const conversation = await api("/conversations", "POST");
    cid = conversation.id;
    current = null;
  }
  await api("/desktop/propose", "POST", {
    conversation_id: cid,
    target_id: target.id,
  });
  await openChat(cid);
}
let checkingReminders=false;
async function checkPersonalReminders(){
  if(!token || checkingReminders || localStorage.getItem('laila-reminders')!=='on')return;
  checkingReminders=true;
  try{
    const data=await api('/personal/dashboard');const now=Date.now();
    for(const item of data.plan){
      const start=new Date(item.starts_at).getTime();const key='laila-reminder-'+item.id+'-'+item.starts_at;
      if(!item.completed && now>=start && now<start+item.minutes*60000 && !localStorage.getItem(key)){
        localStorage.setItem(key,'shown');
        let banner=$('#personal-reminder');
        if(!banner){banner=document.createElement('div');banner.id='personal-reminder';banner.className='personal-reminder';banner.setAttribute('role','status');document.body.append(banner);}
        banner.replaceChildren();const label=document.createElement('span');label.textContent='Time for '+item.title+'. Ready when you are.';banner.append(label);msgButton(banner,'Dismiss',()=>banner.remove());
      }
    }
  }catch(e){/* A reconnect will retry; no fabricated reminder delivery. */}
  finally{checkingReminders=false;}
}
setInterval(checkPersonalReminders,30000);
