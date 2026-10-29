function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatInlineRichText(value) {
  const plain = (text) => escapeHtml(text).replace(/\*\*([^*\n](?:[\s\S]*?[^*\n])?)\*\*/g, "<strong>$1</strong>");
  const pattern = /`([^`\n]+)`|\[([^\]\n]{1,200})\]\((https:\/\/[^\s)]+|\/rag\/evidence\/[1-9]\d*\?[^\s)]+)\)/g;
  let result = "", cursor = 0;
  for (const match of String(value).matchAll(pattern)) {
    result += plain(value.slice(cursor, match.index));
    if (match[1] !== undefined) {
      result += `<code>${escapeHtml(match[1])}</code>`;
    } else {
      let safe = false;
      try {
        const url = new URL(match[3], "http://local.invalid");
        safe = !url.username && !url.password && !/[\\\u0000-\u0020]/.test(match[3])
          && (url.protocol === "https:" || (url.origin === "http://local.invalid" && /^\/rag\/evidence\/[1-9]\d*\?/.test(match[3])));
      } catch { /* Malformed source URLs remain inert text. */ }
      result += safe ? `<a href="${escapeHtml(match[3])}" target="_blank" rel="noopener noreferrer">${escapeHtml(match[2])}</a>` : plain(match[0]);
    }
    cursor = match.index + match[0].length;
  }
  return result + plain(value.slice(cursor));
}

function formatCodeLanguageLabel(value) {
  const normalized = String(value || "").trim().replace(/[^a-zA-Z0-9#+._-]/g, "");
  return normalized || "code";
}

export function formatRichMessage(value, options = {}) {
  const source = String(value || "").replace(/\r\n?/g, "\n");
  if (!source.trim()) return "";

  const registerCodeBlock = typeof options.registerCodeBlock === "function" ? options.registerCodeBlock : () => -1;
  const output = [];
  const paragraph = [];
  const codeLines = [];
  let listType = null;
  let inCodeBlock = false;
  let codeBlockLanguage = "";
  let codeBlockFenceLength = 3;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    output.push(`<p class="message-md-paragraph">${paragraph.map((line) => formatInlineRichText(line)).join("<br />")}</p>`);
    paragraph.length = 0;
  };

  const closeList = () => {
    if (!listType) return;
    output.push(listType === "ol" ? "</ol>" : "</ul>");
    listType = null;
  };

  const openOrderedList = (startNumber) => {
    const safeStart = Number.isFinite(startNumber) ? Math.max(1, Math.trunc(startNumber)) : 1;
    const startAttribute = safeStart > 1 ? ` start="${safeStart}"` : "";
    output.push(`<ol class="message-md-list message-md-list--ordered"${startAttribute}>`);
    listType = "ol";
  };

  const flushCodeBlock = () => {
    const rawCode = codeLines.join("\n").replace(/\n+$/, "");
    const codeIndex = registerCodeBlock(rawCode);
    const languageLabel = formatCodeLanguageLabel(codeBlockLanguage);
    output.push(`
      <div class="message-md-codeblock">
        <div class="message-md-codeblock__toolbar">
          <span class="message-md-codeblock__lang">${escapeHtml(languageLabel)}</span>
          <button class="message-md-codeblock__copy" type="button" data-code-copy-index="${codeIndex}">Копировать код</button>
        </div>
        <pre class="message-md-codeblock__pre"><code>${escapeHtml(rawCode)}</code></pre>
      </div>
    `);
    codeLines.length = 0;
    codeBlockLanguage = "";
  };

  for (const rawLine of source.split("\n")) {
    const trimmed = rawLine.trim();

    if (inCodeBlock) {
      if (/^`{3,}\s*$/.test(trimmed) && trimmed.trim().length >= codeBlockFenceLength) {
        flushCodeBlock();
        inCodeBlock = false;
      } else {
        codeLines.push(rawLine);
      }
      continue;
    }

    if (trimmed.startsWith("```")) {
      flushParagraph();
      closeList();
      inCodeBlock = true;
      codeLines.length = 0;
      codeBlockFenceLength = trimmed.match(/^`+/)[0].length;
      codeBlockLanguage = trimmed.slice(codeBlockFenceLength).trim();
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      closeList();
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      closeList();
      const level = Math.min(4, headingMatch[1].length);
      output.push(
        `<div class="message-md-heading message-md-heading--${level}">${formatInlineRichText(headingMatch[2])}</div>`,
      );
      continue;
    }

    const orderedMatch = trimmed.match(/^(\d+)\.\s+(.+)$/);
    if (orderedMatch) {
      flushParagraph();
      if (listType !== "ol") {
        closeList();
        openOrderedList(Number(orderedMatch[1]));
      }
      output.push(`<li>${formatInlineRichText(orderedMatch[2])}</li>`);
      continue;
    }

    const unorderedMatch = trimmed.match(/^[-*•]\s+(.+)$/);
    if (unorderedMatch) {
      flushParagraph();
      if (listType !== "ul") {
        closeList();
        output.push('<ul class="message-md-list message-md-list--unordered">');
        listType = "ul";
      }
      output.push(`<li>${formatInlineRichText(unorderedMatch[1])}</li>`);
      continue;
    }

    if (listType) {
      closeList();
    }
    paragraph.push(trimmed);
  }

  if (inCodeBlock) {
    flushCodeBlock();
  }
  flushParagraph();
  closeList();
  return output.join("");
}
