/**
 * Column visibility preload — hides columns before first paint
 * to prevent layout shift. Used on workflow and task list pages.
 *
 * Reads saved column preferences from localStorage and injects
 * a <style> tag to hide unchecked columns immediately.
 */

const ALL_COLS = ["id", "type", "started", "stopped", "duration", "status", "queue", "run_id", "events", "parent"];
const DEFAULT_COLS = ["id", "type", "started", "duration", "status"];

(function preloadColumns() {
  try {
    const raw = localStorage.getItem("wf-visible-cols");
    const cols: string[] = raw ? JSON.parse(raw) : null;
    const visible = Array.isArray(cols) && cols.length ? cols : DEFAULT_COLS;
    const hidden = ALL_COLS.filter((c) => !visible.includes(c));
    if (!hidden.length) return;

    const rules = hidden.map((c) => `[data-col="${c}"]{display:none!important}`);
    const style = document.createElement("style");
    style.id = "col-preload";
    style.textContent = rules.join("");
    document.head.appendChild(style);

    document.addEventListener("DOMContentLoaded", () => {
      hidden.forEach((c) => {
        const cb = document.querySelector(`[data-col-toggle="${c}"]`) as HTMLInputElement | null;
        if (cb) cb.checked = false;
      });
    });
  } catch {
    // Ignore localStorage errors
  }
})();
