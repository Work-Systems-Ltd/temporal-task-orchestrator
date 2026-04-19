/**
 * Navigation progress bar and clickable row delegation.
 * Loaded on every page via base layout.
 */

// ── Navigation progress bar ──
(function initNavProgress() {
  const bar = document.getElementById("nav-progress");
  if (!bar) return;

  document.addEventListener("click", (e) => {
    const a = (e.target as HTMLElement).closest("a[href]") as HTMLAnchorElement | null;
    if (!a || a.target === "_blank" || e.metaKey || e.ctrlKey) return;
    const url = new URL(a.href, location.origin);
    if (url.origin !== location.origin) return;
    if (url.pathname === location.pathname && url.search === location.search) return;
    bar.classList.remove("is-done");
    bar.classList.add("is-active");
  });

  window.addEventListener("pageshow", () => {
    bar.classList.remove("is-active");
    bar.classList.add("is-done");
    setTimeout(() => bar.classList.remove("is-done"), 500);
  });
})();

// ── Clickable row delegation ──
// Rows with data-href navigate on click/Enter without inline handlers.
document.addEventListener("click", (e) => {
  const row = (e.target as HTMLElement).closest("tr[data-href]") as HTMLElement | null;
  if (!row) return;
  // Don't navigate if clicking on an interactive element inside the row
  const target = e.target as HTMLElement;
  if (target.closest("a, button, input, select, textarea, [onclick]")) return;
  window.location.href = row.dataset.href!;
});

document.addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  const row = (e.target as HTMLElement).closest("tr[data-href]") as HTMLElement | null;
  if (row) window.location.href = row.dataset.href!;
});

// ── Expand/collapse toggle ──
// Used by workflow list for parent/child rows.
function toggleExpand(parentId: string) {
  const children = document.querySelectorAll(`[data-child-of="${parentId}"]`);
  const toggle = document.querySelector(`[data-parent-id="${parentId}"] .expand-toggle`);
  children.forEach((el) => el.classList.toggle("hidden"));
  if (toggle) toggle.classList.toggle("expand-toggle-open");
}

// Expose globally for any remaining callers
(window as Record<string, unknown>).toggleExpand = toggleExpand;

// Delegated click handler for [data-expand] elements
document.addEventListener("click", (e) => {
  const el = (e.target as HTMLElement).closest("[data-expand]") as HTMLElement | null;
  if (!el) return;
  e.stopPropagation();
  toggleExpand(el.dataset.expand!);
});
