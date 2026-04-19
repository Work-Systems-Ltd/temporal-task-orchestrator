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

interface TaskListData {
  loading: boolean;
  connected: boolean;
  ws: WebSocket | null;
  seq: number;
  reconnectTimer: number | null;
  reconnectDelay: number;
  connect(): void;
  disconnect(): void;
  sendView(): void;
  applyUpdate(msg: UpdateMessage): void;
  refresh(): void;
  navigateTab(e: Event): void;
  _visibilityHandler: (() => void) | null;
  _listenVisibility(): void;
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
      toggle.classList.toggle("expand-toggle-open", expandedParents.has(parentId));
    }
  });
}

// ── Column picker state (persisted in localStorage) ──
const COL_STORAGE_KEY = "wf-visible-cols";
const ALL_COLUMNS = ["id", "type", "started", "stopped", "duration", "status", "queue", "run_id", "events", "parent"];
const DEFAULT_COLUMNS = ["id", "type", "started", "duration", "status"];

function getVisibleColumns(): string[] {
  try {
    const raw = localStorage.getItem(COL_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as string[];
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch { /* ignore */ }
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
    // Insert in default order
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
  // Remove the preload style if present (SSR anti-flash)
  const preload = document.getElementById("col-preload");
  if (preload) preload.remove();

  const visible = new Set(getVisibleColumns());
  document.querySelectorAll<HTMLElement>("[data-col]").forEach((el) => {
    const col = el.getAttribute("data-col")!;
    el.style.display = visible.has(col) ? "" : "none";
  });
  // Update checkbox states in the picker dropdown
  document.querySelectorAll<HTMLInputElement>("[data-col-toggle]").forEach((cb) => {
    cb.checked = visible.has(cb.getAttribute("data-col-toggle")!);
  });
}

(window as Record<string, unknown>).toggleColumn = toggleColumn;
(window as Record<string, unknown>).applyColumnState = applyColumnState;
(window as Record<string, unknown>).toggleExpand = toggleExpand;

function getViewParams(seq: number): ViewParams {
  const params = new URLSearchParams(window.location.search);
  return {
    type: "view",
    seq,
    tab: params.get("tab") || "pending",
    page: Math.max(1, parseInt(params.get("page") || "1", 10)),
    per_page: params.has("per_page") ? Math.max(10, Math.min(100, parseInt(params.get("per_page")!, 10))) : null,
    wf_type: params.get("type") || null,
    search: params.get("q") || null,
  };
}

function taskList(): TaskListData {
  return {
    loading: false,
    connected: false,
    ws: null,
    seq: 0,
    reconnectTimer: null,
    reconnectDelay: 1000,

    connect(): void {
      if (this.ws) return;

      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${proto}//${location.host}/ws/tasks`;
      const ws = new WebSocket(url);

      ws.onopen = () => {
        this.connected = true;
        this.reconnectDelay = 1000;
        this.sendView();
        this._listenVisibility();
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const msg: UpdateMessage = JSON.parse(event.data);
          if (msg.type === "update") {
            this.applyUpdate(msg);
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = (ev: CloseEvent) => {
        this.connected = false;
        this.ws = null;
        // Server rejected with 4401 — session expired, redirect to login
        if (ev.code === 4401) {
          window.location.href = "/login";
          return;
        }
        if (!this.reconnectTimer) {
          this.reconnectTimer = window.setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
          }, this.reconnectDelay);
          this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      this.ws = ws;
    },

    disconnect(): void {
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      if (this._visibilityHandler) {
        document.removeEventListener("visibilitychange", this._visibilityHandler);
        this._visibilityHandler = null;
      }
      if (this.ws) {
        this.ws.close();
        this.ws = null;
      }
    },

    sendView(): void {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.seq++;
        this.ws.send(JSON.stringify(getViewParams(this.seq)));
      }
    },

    _lastAppliedHash: "",

    applyUpdate(msg: UpdateMessage): void {
      // Drop stale updates from before the latest navigation
      if (msg.seq < this.seq) return;

      // Compare hash: if the data hasn't changed since SSR or last update, skip DOM replacement.
      // This prevents the flash when the first WS push has identical data to SSR.
      if (!this._lastAppliedHash) {
        // Read the SSR hash from the DOM on first update
        const root = document.querySelector("[data-initial-hash]");
        this._lastAppliedHash = root?.getAttribute("data-initial-hash") || "";
      }

      if (msg.hash && msg.hash === this._lastAppliedHash) {
        this.loading = false;
        return;
      }

      this._lastAppliedHash = msg.hash || "";

      const tabBar = document.querySelector("[data-tab-bar]");
      if (tabBar && msg.tab_bar) {
        tabBar.innerHTML = msg.tab_bar;
      }

      const tabContent = document.querySelector("[data-tab-content]");
      if (tabContent && msg.tab_content) {
        tabContent.innerHTML = msg.tab_content;
      }

      applyExpandState();
      applyColumnState();
      this.loading = false;
    },

    _visibilityHandler: null as (() => void) | null,

    _listenVisibility(): void {
      if (this._visibilityHandler) return;
      this._visibilityHandler = () => {
        if (!document.hidden && this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ type: "visible" }));
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

      // Optimistic: immediately highlight the clicked tab
      const clickedTab = link.getAttribute("data-tab");
      if (clickedTab) {
        document.querySelectorAll("[data-tab-bar] a[data-tab]").forEach((el) => {
          const isActive = el.getAttribute("data-tab") === clickedTab;
          el.classList.toggle("tab-item-active", isActive);
          const badge = el.querySelector(".count-badge");
          if (badge) {
            badge.classList.toggle("count-badge-active", isActive);
            badge.classList.toggle("count-badge-muted", !isActive);
          }
        });
      }

      // Show equalizer loader while waiting for server
      const tabContent = document.querySelector("[data-tab-content]");
      if (tabContent) {
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

      this._lastAppliedHash = "";  // force next update to apply
      this.loading = true;
      this.sendView();
    },
  };
}

document.addEventListener("keydown", (e: KeyboardEvent) => {
  // Escape: blur active input or close dropdowns
  if (e.key === "Escape") {
    if (document.activeElement instanceof HTMLInputElement || document.activeElement instanceof HTMLTextAreaElement) {
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

  if (e.key === "n") {
    window.location.href = "/start";
  }

  if (e.key === "r") {
    window.location.reload();
  }

  if (e.key === "/") {
    const searchInput = document.querySelector<HTMLInputElement>(".search-box-input");
    if (searchInput) {
      e.preventDefault();
      searchInput.focus();
    }
  }
});

window.addEventListener("popstate", () => {
  window.location.reload();
});

// Apply column visibility on initial load
applyColumnState();

(window as Record<string, unknown>).taskList = taskList;
