/**
 * Shared WebSocket factory with reconnection and session expiry handling.
 */

export interface SocketOptions {
  onMessage: (data: unknown) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export interface SocketHandle {
  send(data: unknown): void;
  close(): void;
  isConnected(): boolean;
}

export function createSocket(path: string, opts: SocketOptions): SocketHandle {
  let ws: WebSocket | null = null;
  let reconnectDelay = 1000;
  let reconnectTimer: number | null = null;
  let closed = false;

  function connect() {
    if (closed) return;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}${path}`);

    ws.onopen = () => {
      reconnectDelay = 1000;
      opts.onConnect?.();
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        opts.onMessage(JSON.parse(event.data));
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = (ev: CloseEvent) => {
      ws = null;
      opts.onDisconnect?.();

      // Server rejected — session expired
      if (ev.code === 4401) {
        window.location.href = "/login";
        return;
      }

      if (!closed) {
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = null;
          connect();
        }, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 30000);
      }
    };

    ws.onerror = () => {
      ws?.close();
    };
  }

  connect();

  return {
    send(data: unknown) {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
      }
    },
    close() {
      closed = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      ws?.close();
    },
    isConnected() {
      return ws?.readyState === WebSocket.OPEN;
    },
  };
}
