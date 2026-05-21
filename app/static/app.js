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

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character];
  });
}

function applyInlineMarkdown(value) {
  const codeSpans = [];
  let text = value.replace(/`([^`]+)`/g, (_, code) => {
    const token = `@@CODE_${codeSpans.length}@@`;
    codeSpans.push(`<code>${escapeHtml(code)}</code>`);
    return token;
  });

  text = escapeHtml(text)
    .replace(
      /\[([^\]]+)]\((https?:\/\/[^\s)]+|mailto:[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    )
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");

  codeSpans.forEach((html, index) => {
    text = text.replace(`@@CODE_${index}@@`, html);
  });

  return text;
}

function isMarkdownBlockStart(line) {
  const trimmed = line.trim();
  return (
    trimmed.startsWith("```") ||
    /^#{1,6}\s+/.test(trimmed) ||
    /^[-*]\s+/.test(trimmed) ||
    /^\d+\.\s+/.test(trimmed) ||
    /^>\s?/.test(trimmed) ||
    /^-{3,}$/.test(trimmed)
  );
}

function renderMarkdown(markdown) {
  const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const language = trimmed.slice(3).trim().replace(/[^\w-]/g, "");
      const code = [];
      index += 1;

      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }

      if (index < lines.length) {
        index += 1;
      }

      const languageClass = language ? ` class="language-${language}"` : "";
      html.push(`<pre><code${languageClass}>${escapeHtml(code.join("\n"))}</code></pre>`);
      continue;
    }

    const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const level = heading[1].length;
      html.push(`<h${level}>${applyInlineMarkdown(heading[2])}</h${level}>`);
      index += 1;
      continue;
    }

    if (/^-{3,}$/.test(trimmed)) {
      html.push("<hr>");
      index += 1;
      continue;
    }

    if (/^>\s?/.test(trimmed)) {
      const quote = [];
      while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
        quote.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      html.push(`<blockquote>${applyInlineMarkdown(quote.join(" "))}</blockquote>`);
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*]\s+/, ""));
        index += 1;
      }
      html.push(`<ul>${items.map((item) => `<li>${applyInlineMarkdown(item)}</li>`).join("")}</ul>`);
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ""));
        index += 1;
      }
      html.push(`<ol>${items.map((item) => `<li>${applyInlineMarkdown(item)}</li>`).join("")}</ol>`);
      continue;
    }

    const paragraph = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !isMarkdownBlockStart(lines[index])
    ) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    html.push(`<p>${applyInlineMarkdown(paragraph.join(" "))}</p>`);
  }

  return html.join("");
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
  if (options.markdown) {
    bubble.classList.add("markdown-body");
    bubble.innerHTML = renderMarkdown(text);
  } else {
    bubble.textContent = text;
  }

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
    pending.bubble.classList.add("markdown-body");
    pending.bubble.innerHTML = renderMarkdown(payload.response || "");
  } catch (error) {
    pending.article.classList.remove("pending");
    pending.article.classList.add("error");
    pending.bubble.classList.remove("markdown-body");
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
