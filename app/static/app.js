const SESSION_KEY = "gustave.sessionId";

const form = document.querySelector("#chatForm");
const input = document.querySelector("#messageInput");
const messages = document.querySelector("#messages");
const emptyState = document.querySelector("#emptyState");
const sendButton = document.querySelector("#sendButton");
const resetButton = document.querySelector("#resetButton");
const sessionLabel = document.querySelector("#sessionLabel");

let sessionId = localStorage.getItem(SESSION_KEY);

function shortSession(value) {
  if (!value) {
    return "Nouvelle session";
  }
  return `Session ${value.slice(0, 8)}`;
}

function updateSessionLabel() {
  sessionLabel.textContent = shortSession(sessionId);
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

function addMessage(role, text, options = {}) {
  emptyState.classList.add("hidden");

  const article = document.createElement("article");
  article.className = `message ${role}${options.pending ? " pending" : ""}${
    options.error ? " error" : ""
  }`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "U" : "G";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  if (role === "user") {
    article.append(bubble, avatar);
  } else {
    article.append(avatar, bubble);
  }

  messages.append(article);
  scrollToBottom();
  return { article, bubble };
}

function setBusy(isBusy) {
  sendButton.disabled = isBusy;
  input.disabled = isBusy;
}

function autosizeInput() {
  input.style.height = "auto";
  input.style.height = `${input.scrollHeight}px`;
}

async function sendMessage(message) {
  addMessage("user", message);
  const pending = addMessage("assistant", "Gustave reflechit...", { pending: true });
  setBusy(true);

  try {
    const response = await fetch("/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        session_id: sessionId,
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `Erreur HTTP ${response.status}`);
    }

    const payload = await response.json();
    sessionId = payload.session_id;
    localStorage.setItem(SESSION_KEY, sessionId);
    updateSessionLabel();

    pending.article.classList.remove("pending");
    pending.bubble.textContent = payload.response || "";
  } catch (error) {
    pending.article.classList.remove("pending");
    pending.article.classList.add("error");
    pending.bubble.textContent = `Erreur: ${error.message}`;
  } finally {
    setBusy(false);
    input.focus();
    scrollToBottom();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = input.value.trim();
  if (!message) {
    return;
  }

  input.value = "";
  autosizeInput();
  await sendMessage(message);
});

input.addEventListener("input", autosizeInput);

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

resetButton.addEventListener("click", () => {
  sessionId = null;
  localStorage.removeItem(SESSION_KEY);
  updateSessionLabel();
  messages.querySelectorAll(".message").forEach((message) => message.remove());
  emptyState.classList.remove("hidden");
  input.focus();
});

updateSessionLabel();
autosizeInput();
