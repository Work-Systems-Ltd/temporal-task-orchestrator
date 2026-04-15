interface ViewParams {
  type: "view";
  seq: number;
  tab: string;
  page: number;
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
  skipFirst: boolean;
  reconnectTimer: number | null;
  reconnectDelay: number;
  connect(): void;
  disconnect(): void;
  sendView(): void;
  applyUpdate(msg: UpdateMessage): void;
  refresh(): void;
  navigateTab(e: Event): void;
}

function getViewParams(seq: number): ViewParams {
  const params = new URLSearchParams(window.location.search);
  return {
    type: "view",
    seq,
    tab: params.get("tab") || "pending",
    page: Math.max(1, parseInt(params.get("page") || "1", 10)),
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
    skipFirst: true,
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
        // Sync view params with server so the push loop knows what to render
        this.sendView();
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

      // Skip the very first push — SSR already rendered the page
      if (this.skipFirst) {
        this.skipFirst = false;
        return;
      }

      if (document.hidden) return;

      const tabBar = document.querySelector("[data-tab-bar]");
      if (tabBar && msg.tab_bar) {
        tabBar.innerHTML = msg.tab_bar;
      }

      const tabContent = document.querySelector("[data-tab-content]");
      if (tabContent && msg.tab_content) {
        tabContent.innerHTML = msg.tab_content;
      }

      this.loading = false;
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
});

window.addEventListener("popstate", () => {
  window.location.reload();
});

(window as Record<string, unknown>).taskList = taskList;
