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

      ws.onclose = () => {
        this.connected = false;
        this.ws = null;
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

    applyUpdate(msg: UpdateMessage): void {
      // Drop stale updates from before the latest navigation
      if (msg.seq < this.seq) return;

      const tabBar = document.querySelector("[data-tab-bar]");
      if (tabBar && msg.tab_bar) {
        tabBar.innerHTML = msg.tab_bar;
      }

      const tabContent = document.querySelector("[data-tab-content]");
      if (tabContent && msg.tab_content) {
        tabContent.innerHTML = msg.tab_content;
      }

      applyExpandState();
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

(window as Record<string, unknown>).taskList = taskList;
