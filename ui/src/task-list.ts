interface ViewParams {
  type: "view";
  tab: string;
  page: number;
  wf_type: string | null;
  search: string | null;
}

interface UpdateMessage {
  type: "update";
  tab_bar: string;
  tab_content: string;
}

interface TaskListData {
  loading: boolean;
  connected: boolean;
  ws: WebSocket | null;
  reconnectTimer: number | null;
  reconnectDelay: number;
  connect(): void;
  disconnect(): void;
  sendView(): void;
  applyUpdate(msg: UpdateMessage): void;
  refresh(): void;
  navigateTab(e: Event): void;
}

function getViewParams(): ViewParams {
  const params = new URLSearchParams(window.location.search);
  return {
    type: "view",
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
        // Reconnect with exponential backoff, max 30s
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
        this.ws.send(JSON.stringify(getViewParams()));
      }
    },

    applyUpdate(msg: UpdateMessage): void {
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
