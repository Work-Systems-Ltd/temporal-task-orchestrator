/**
 * WebSocket client for the DB-powered task list page.
 *
 * Uses the same section-patching pattern as the workflow detail page:
 * on "refresh", fetches the current page HTML and swaps [data-ws-section]
 * elements rather than doing a full page reload.
 *
 * Sends the server-rendered data hash on connect so the server can seed
 * its comparison value and avoid a spurious first refresh.
 */
import { fetchHtml } from "../api/client";
import { createSocket, type SocketHandle } from "../api/ws";

declare const Alpine: any;

let _socket: SocketHandle | null = null;
let _refreshing = false;

function getInitialHash(): string {
  const el = document.querySelector("[data-initial-hash]");
  return el?.getAttribute("data-initial-hash") || "";
}

function refreshContent(): void {
  if (_refreshing) return;
  _refreshing = true;

  fetchHtml(window.location.href)
    .then((html) => {
      const doc = new DOMParser().parseFromString(html, "text/html");

      // Update the data-initial-hash so subsequent checks use the new value
      const newRoot = doc.querySelector("[data-initial-hash]");
      const curRoot = document.querySelector("[data-initial-hash]");
      if (newRoot && curRoot) {
        curRoot.setAttribute(
          "data-initial-hash",
          newRoot.getAttribute("data-initial-hash") || "",
        );
      }

      doc.querySelectorAll("[data-ws-section]").forEach((newSection) => {
        const id = newSection.getAttribute("data-ws-section");
        if (!id) return;

        const current = document.querySelector(
          '[data-ws-section="' + id + '"]',
        );
        if (!current) return;

        // Don't replace if user is interacting with this section
        if (current.contains(document.activeElement)) return;
        // Don't replace if nothing changed
        if (current.innerHTML === newSection.innerHTML) return;

        if (typeof Alpine !== "undefined" && Alpine.destroyTree) {
          Alpine.destroyTree(current);
        }
        current.innerHTML = newSection.innerHTML;
        if (typeof Alpine !== "undefined" && Alpine.initTree) {
          Alpine.initTree(current);
        }
      });
    })
    .catch(() => {})
    .finally(() => {
      _refreshing = false;
    });
}

function connect(): void {
  if (_socket) return;

  _socket = createSocket("/ws/task-list", {
    onMessage: (data: any) => {
      if (data.type === "refresh") {
        refreshContent();
      }
    },
    onConnect: () => {
      // Send initial hash so server seeds its comparison value
      _socket?.send({ type: "init", hash: getInitialHash() });
    },
  });
}

connect();

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    _socket?.send({ type: "nudge" });
  }
});
