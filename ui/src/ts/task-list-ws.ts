/**
 * Lightweight WebSocket client for the DB-powered task list page.
 * Connects to /ws/task-list and reloads the page when task data changes.
 */
import { createSocket, type SocketHandle } from "./api/ws";

let socket: SocketHandle | null = null;

function connect(): void {
  if (socket) return;

  socket = createSocket("/ws/task-list", {
    onMessage: (data: any) => {
      if (data.type === "refresh") {
        window.location.reload();
      }
    },
  });
}

connect();

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    socket?.send({ type: "nudge" });
  }
});
