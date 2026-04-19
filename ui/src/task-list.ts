import { createSocket, type SocketHandle } from "./api/ws";

interface ViewParams {
  type: "view";
  seq: number;
  tab: string;
  page: number;
  per_page: number | null;
  wf_type: string | null;
  search: string | null;
}

interface UpdateMessage {
  type: "update";
  seq: number;
  hash: string;
  tab_bar: string;
  tab_content: string;
}

// ── Expand/collapse state for parent/child rows ──
const expandedParents = new Set<string>();

function toggleExpand(parentId: string): void {
  if (expandedParents.has(parentId)) {
    expandedParents.delete(parentId);
  } else {
    expandedParents.add(parentId);
  }
  applyExpandState();
}

function applyExpandState(): void {
  document.querySelectorAll<HTMLElement>("[data-child-of]").forEach((row) => {
    const parentId = row.getAttribute("data-child-of")!;
    row.classList.toggle("hidden", !expandedParents.has(parentId));
  });
  document.querySelectorAll<HTMLElement>("[data-parent-id]").forEach((row) => {
    const parentId = row.getAttribute("data-parent-id")!;
    const toggle = row.querySelector(".expand-toggle");
    if (toggle) {
      toggle.classList.toggle(
        "expand-toggle-open",
        expandedParents.has(parentId),
      );
    }
  });
}

// ── Column picker state (persisted in localStorage) ──
const COL_STORAGE_KEY = "wf-visible-cols";
const ALL_COLUMNS = [
  "id",
  "type",
  "started",
  "stopped",
  "duration",
  "status",
  "queue",
  "run_id",
  "events",
  "parent",
];
const DEFAULT_COLUMNS = ["id", "type", "started", "duration", "status"];

function getVisibleColumns(): string[] {
  try {
    const raw = localStorage.getItem(COL_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as string[];
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch {
    /* ignore */
  }
  return [...DEFAULT_COLUMNS];
}

function setVisibleColumns(cols: string[]): void {
  localStorage.setItem(COL_STORAGE_KEY, JSON.stringify(cols));
  applyColumnState();
}

function toggleColumn(col: string): void {
  const cols = getVisibleColumns();
  const idx = cols.indexOf(col);
  if (idx >= 0 && cols.length > 1) {
    cols.splice(idx, 1);
  } else if (idx < 0) {
    const defaultIdx = ALL_COLUMNS.indexOf(col);
    let insertAt = cols.length;
    for (let i = 0; i < cols.length; i++) {
      if (ALL_COLUMNS.indexOf(cols[i]) > defaultIdx) {
        insertAt = i;
        break;
      }
    }
    cols.splice(insertAt, 0, col);
  }
  setVisibleColumns(cols);
}

function applyColumnState(): void {
  const preload = document.getElementById("col-preload");
  if (preload) preload.remove();

  const visible = new Set(getVisibleColumns());
  document.querySelectorAll<HTMLElement>("[data-col]").forEach((el) => {
    const col = el.getAttribute("data-col")!;
    el.style.display = visible.has(col) ? "" : "none";
  });
  document
    .querySelectorAll<HTMLInputElement>("[data-col-toggle]")
    .forEach((cb) => {
      cb.checked = visible.has(cb.getAttribute("data-col-toggle")!);
    });
}

(window as Record<string, unknown>).toggleColumn = toggleColumn;
(window as Record<string, unknown>).applyColumnState = applyColumnState;
(window as Record<string, unknown>).toggleExpand = toggleExpand;

// Delegated click handler for [data-toggle-col] labels
document.addEventListener("click", (e) => {
  const label = (e.target as HTMLElement).closest(
    "[data-toggle-col]",
  ) as HTMLElement | null;
  if (!label) return;
  e.preventDefault();
  toggleColumn(label.dataset.toggleCol!);
});

function getViewParams(seq: number): ViewParams {
  const params = new URLSearchParams(window.location.search);
  return {
    type: "view",
    seq,
    tab: params.get("tab") || "pending",
    page: Math.max(1, parseInt(params.get("page") || "1", 10)),
    per_page: params.has("per_page")
      ? Math.max(10, Math.min(100, parseInt(params.get("per_page")!, 10)))
      : null,
    wf_type: params.get("type") || null,
    search: params.get("q") || null,
  };
}

function taskList() {
  let socket: SocketHandle | null = null;
  let seq = 0;
  let lastAppliedHash = "";
  let loadingTimeout: number | null = null;

  return {
    loading: false,
    connected: false,

    connect(): void {
      if (socket) return;

      socket = createSocket("/ws/tasks", {
        onMessage: (data: any) => {
          if (data.type === "update") {
            this.applyUpdate(data as UpdateMessage);
          }
        },
        onConnect: () => {
          this.connected = true;
          this.sendView();
          this._listenVisibility();
        },
        onDisconnect: () => {
          this.connected = false;
        },
      });
    },

    disconnect(): void {
      if (this._visibilityHandler) {
        document.removeEventListener(
          "visibilitychange",
          this._visibilityHandler,
        );
        this._visibilityHandler = null;
      }
      socket?.close();
      socket = null;
    },

    sendView(): void {
      seq++;
      socket?.send(getViewParams(seq));
    },

    applyUpdate(msg: UpdateMessage): void {
      if (msg.seq < seq) return;

      if (!lastAppliedHash) {
        const root = document.querySelector("[data-initial-hash]");
        lastAppliedHash = root?.getAttribute("data-initial-hash") || "";
      }

      if (msg.hash && msg.hash === lastAppliedHash) {
        this.loading = false;
        return;
      }

      lastAppliedHash = msg.hash || "";

      const tabBar = document.querySelector("[data-tab-bar]");
      if (tabBar && msg.tab_bar) {
        tabBar.innerHTML = msg.tab_bar;
      }

      const tabContent = document.querySelector(
        "[data-tab-content]",
      ) as HTMLElement | null;
      if (tabContent && msg.tab_content) {
        tabContent.innerHTML = msg.tab_content;
        tabContent.style.minHeight = "";
      }

      applyExpandState();
      applyColumnState();
      this.loading = false;
      if (loadingTimeout) {
        clearTimeout(loadingTimeout);
        loadingTimeout = null;
      }
    },

    _visibilityHandler: null as (() => void) | null,

    _listenVisibility(): void {
      if (this._visibilityHandler) return;
      this._visibilityHandler = () => {
        if (!document.hidden) {
          socket?.send({ type: "visible" });
        }
      };
      document.addEventListener("visibilitychange", this._visibilityHandler);
    },

    refresh(): void {
      this.loading = true;
      this.sendView();
    },

    navigateTab(e: Event): void {
      e.preventDefault();
      const link = e.currentTarget as HTMLAnchorElement;
      history.pushState(null, "", link.href);

      const clickedTab = link.getAttribute("data-tab");
      if (clickedTab) {
        document
          .querySelectorAll("[data-tab-bar] a[data-tab]")
          .forEach((el) => {
            const isActive = el.getAttribute("data-tab") === clickedTab;
            el.classList.toggle("tab-item-active", isActive);
            const badge = el.querySelector(".count-badge");
            if (badge) {
              badge.classList.toggle("count-badge-active", isActive);
              badge.classList.toggle("count-badge-muted", !isActive);
            }
          });
      }

      const tabContent = document.querySelector(
        "[data-tab-content]",
      ) as HTMLElement | null;
      if (tabContent) {
        // Lock the height to prevent layout jump during swap
        tabContent.style.minHeight = tabContent.offsetHeight + "px";
        tabContent.innerHTML =
          '<div class="skeleton-loader">' +
          '<div class="flex flex-col items-center">' +
          '<div class="skeleton-bars">' +
          "<span></span><span></span><span></span><span></span><span></span>" +
          "</div>" +
          '<div class="skeleton-label">Loading</div>' +
          "</div>" +
          "</div>";
      }

      lastAppliedHash = "";
      this.loading = true;
      this.sendView();

      if (loadingTimeout) clearTimeout(loadingTimeout);
      loadingTimeout = window.setTimeout(() => {
        if (this.loading) {
          window.location.href = link.href;
        }
      }, 5000);
    },
  };
}

document.addEventListener("keydown", (e: KeyboardEvent) => {
  if (e.key === "Escape") {
    if (
      document.activeElement instanceof HTMLInputElement ||
      document.activeElement instanceof HTMLTextAreaElement
    ) {
      (document.activeElement as HTMLElement).blur();
    }
    return;
  }

  if (
    e.target instanceof HTMLInputElement ||
    e.target instanceof HTMLTextAreaElement ||
    e.target instanceof HTMLSelectElement
  )
    return;

  if (e.key === "n") window.location.href = "/start";
  if (e.key === "r") window.location.reload();
  if (e.key === "/") {
    const searchInput =
      document.querySelector<HTMLInputElement>(".search-box-input");
    if (searchInput) {
      e.preventDefault();
      searchInput.focus();
    }
  }
});

window.addEventListener("popstate", () => {
  window.location.reload();
});

applyColumnState();

(window as Record<string, unknown>).taskList = taskList;
