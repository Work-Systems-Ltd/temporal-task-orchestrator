/**
 * Inline task submission + WebSocket-driven live updates for the workflow detail page.
 */

import { fetchHtml } from "./api/client";
import { submitTask } from "./api/tasks";
import { createSocket, type SocketHandle } from "./api/ws";

declare const Alpine: any;

let _socket: SocketHandle | null = null;
let _refreshing = false;

/**
 * Fetch the current page and update only the sections that changed.
 */
function refreshContent(): void {
  if (_refreshing) return;
  _refreshing = true;

  fetchHtml(window.location.href)
    .then((html) => {
      const doc = new DOMParser().parseFromString(html, "text/html");

      doc.querySelectorAll("[data-ws-section]").forEach((newSection) => {
        const id = newSection.getAttribute("data-ws-section");
        if (!id) return;

        const current = document.querySelector(
          '[data-ws-section="' + id + '"]',
        );
        if (!current) return;

        if (current.contains(document.activeElement)) return;
        if (current.innerHTML === newSection.innerHTML) return;

        Alpine.destroyTree(current);
        current.innerHTML = newSection.innerHTML;
        Alpine.initTree(current);
      });

      if (typeof (window as any).mountJsonViewers === "function") {
        (window as any).mountJsonViewers();
      }
    })
    .catch(() => {})
    .finally(() => {
      _refreshing = false;
    });
}

/**
 * Connect to the workflow detail WebSocket.
 */
function connectWorkflowWs(workflowId: string): void {
  _socket = createSocket(`/ws/workflow/${workflowId}`, {
    onMessage(data: any) {
      if (data.type === "refresh") {
        refreshContent();
      }
    },
  });

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && _socket?.isConnected()) {
      refreshContent();
    }
  });
}

/**
 * Handle inline task form submission.
 */
function submitInlineTask(event: Event, workflowId: string): void {
  const form = event.target as HTMLFormElement;
  const scope = Alpine.$data(form.closest("[x-data]")!);
  scope.submitting = true;

  // Clear previous inline errors
  form.querySelectorAll(".inline-error").forEach((el) => el.remove());
  form
    .querySelectorAll(".input-field-error")
    .forEach((el) => el.classList.remove("input-field-error"));

  const formData = new FormData(form);
  const data: Record<string, string> = {};
  formData.forEach((v, k) => {
    data[k] = v as string;
  });

  submitTask(workflowId, data)
    .then((result) => {
      scope.submitting = false;

      if (result.ok || result.gone) {
        _socket?.send({ type: "submitted" });
        setTimeout(refreshContent, 600);
        return;
      }

      if (result.errors) {
        Object.keys(result.errors).forEach((fieldName) => {
          const msgs = result.errors![fieldName];
          const input = form.querySelector('[name="' + fieldName + '"]');
          if (!input) return;

          const container = input.closest(".space-y-1\\.5");
          if (!container) return;

          const inputEl = container.querySelector(".input-field");
          if (inputEl) inputEl.classList.add("input-field-error");

          msgs.forEach((msg) => {
            const p = document.createElement("p");
            p.className =
              "flex items-center gap-1 text-xs text-red-400 animate-fade-in inline-error";
            p.innerHTML =
              '<svg class="h-3 w-3 shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">' +
              '<path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-8-5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 5Zm0 10a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" clip-rule="evenodd" /></svg> ' +
              msg;
            container.appendChild(p);
          });
        });
      }
    })
    .catch(() => {
      scope.submitting = false;
    });
}

(window as any).submitInlineTask = submitInlineTask;
(window as any).connectWorkflowWs = connectWorkflowWs;

document.addEventListener("DOMContentLoaded", () => {
  const el = document.querySelector("[data-workflow-ws]") as HTMLElement | null;
  if (el?.dataset.workflowWs) {
    connectWorkflowWs(el.dataset.workflowWs);
  }
});
