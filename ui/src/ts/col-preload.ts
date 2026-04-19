/**
 * Column visibility preload — hides columns before first paint
 * to prevent layout shift. Used on workflow and task list pages.
 *
 * Reads saved column preferences from localStorage and injects
 * a <style> tag to hide unchecked columns immediately.
 */

import { ALL_COLUMNS, COL_STORAGE_KEY, DEFAULT_COLUMNS } from "./shared/constants";

(function preloadColumns() {
  try {
    const raw = localStorage.getItem(COL_STORAGE_KEY);
    const cols: string[] = raw ? JSON.parse(raw) : null;
    const visible = Array.isArray(cols) && cols.length ? cols : DEFAULT_COLUMNS;
    const hidden = ALL_COLUMNS.filter((c) => !visible.includes(c));
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
