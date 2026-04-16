import { EditorView, lineNumbers, drawSelection, highlightActiveLine } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { json } from "@codemirror/lang-json";
import { syntaxHighlighting, HighlightStyle } from "@codemirror/language";
import { tags } from "@lezer/highlight";

// Theme that matches the app's zinc design tokens
const appTheme = EditorView.theme(
  {
    "&": {
      fontSize: "12px",
      fontFamily: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace",
    },
    ".cm-content": {
      padding: "12px 0",
      caretColor: "transparent",
    },
    ".cm-line": {
      padding: "0 16px",
    },
    "&.cm-focused .cm-cursor": {
      display: "none",
    },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground": {
      background: "var(--color-selection)",
    },
    "&.cm-focused": {
      outline: "none",
    },
    ".cm-gutters": {
      background: "transparent",
      border: "none",
      color: "var(--color-text-ghost)",
      paddingLeft: "8px",
    },
    ".cm-lineNumbers .cm-gutterElement": {
      fontSize: "10px",
      minWidth: "24px",
      padding: "0 4px 0 0",
    },
    ".cm-activeLine": {
      background: "var(--color-surface-subtle)",
    },
    ".cm-activeLineGutter": {
      background: "transparent",
      color: "var(--color-text-faint)",
    },
  },
  { dark: false }
);

const appHighlight = HighlightStyle.define([
  { tag: tags.string, color: "#059669" },
  { tag: tags.number, color: "#2563eb" },
  { tag: tags.bool, color: "#b45309" },
  { tag: tags.null, color: "var(--color-text-faint)" },
  { tag: tags.propertyName, color: "var(--color-text-primary)" },
  { tag: tags.punctuation, color: "var(--color-text-ghost)" },
]);

function createJsonViewer(element: HTMLElement, content: string): EditorView {
  // Try to pretty-print if it's valid JSON
  let formatted = content;
  try {
    formatted = JSON.stringify(JSON.parse(content), null, 2);
  } catch {
    // leave as-is
  }

  const state = EditorState.create({
    doc: formatted,
    extensions: [
      EditorView.editable.of(false),
      EditorState.readOnly.of(true),
      lineNumbers(),
      drawSelection(),
      highlightActiveLine(),
      json(),
      syntaxHighlighting(appHighlight),
      appTheme,
    ],
  });

  return new EditorView({ state, parent: element });
}

// Mount all viewers on page load
function mountViewers(): void {
  document.querySelectorAll<HTMLElement>("[data-json-viewer]").forEach((el) => {
    const raw = el.getAttribute("data-json-viewer") || "{}";
    el.removeAttribute("data-json-viewer");
    el.textContent = "";
    createJsonViewer(el, raw);
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mountViewers);
} else {
  mountViewers();
}
