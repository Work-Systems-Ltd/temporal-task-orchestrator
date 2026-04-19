/**
 * Inline task submission + WebSocket-driven live updates for the workflow detail page.
 *
 * The WebSocket at /ws/workflow/{id} sends {"type": "refresh"} when the workflow
 * state changes. The client fetches the page and does targeted section replacement
 * using data-ws-section markers — only sections whose content actually changed get
 * swapped, preserving Alpine state and avoiding visual jumpiness.
 */

declare const Alpine: any;

let _ws: WebSocket | null = null;
let _refreshing = false;

/**
 * Fetch the current page and update only the sections that changed.
 * Sections are identified by data-ws-section attributes.
 * Sections containing the active element (e.g. a form being filled) are skipped.
 */
function refreshContent(): void {
  if (_refreshing) return;
  _refreshing = true;

  fetch(window.location.href, { headers: { Accept: "text/html" } })
    .then((r) => r.text())
    .then((html) => {
      const doc = new DOMParser().parseFromString(html, "text/html");

      doc.querySelectorAll("[data-ws-section]").forEach((newSection) => {
        const id = newSection.getAttribute("data-ws-section");
        if (!id) return;

        const current = document.querySelector(
          '[data-ws-section="' + id + '"]'
        );
        if (!current) return;

        // Skip sections where the user is actively interacting
        if (current.contains(document.activeElement)) return;

        // Skip if content hasn't changed
        if (current.innerHTML === newSection.innerHTML) return;

        // Swap the section content
        Alpine.destroyTree(current);
        current.innerHTML = newSection.innerHTML;
        Alpine.initTree(current);
      });

      // Re-initialize JSON viewers on any new data-json-viewer elements
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
 * Called from the template with the workflow ID.
 */
function connectWorkflowWs(workflowId: string): void {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const url = proto + "//" + location.host + "/ws/workflow/" + workflowId;

  function connect(): void {
    _ws = new WebSocket(url);

    _ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "refresh") {
          refreshContent();
        }
      } catch {}
    };

    _ws.onclose = () => {
      // Reconnect after a delay
      setTimeout(connect, 3000);
    };

    _ws.onerror = () => {
      _ws?.close();
    };
  }

  connect();

  // Refresh when the tab becomes visible again
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && _ws?.readyState === WebSocket.OPEN) {
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

  fetch("/task/" + workflowId + "/submit", {
    method: "POST",
    body: new URLSearchParams(formData as any),
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  })
    .then((r) => r.json())
    .then((data: { ok: boolean; gone?: boolean; errors?: Record<string, string[]> }) => {
      scope.submitting = false;

      if (data.ok || data.gone) {
        // Tell the WS server a task was submitted so it checks sooner
        if (_ws?.readyState === WebSocket.OPEN) {
          _ws.send(JSON.stringify({ type: "submitted" }));
        }
        // Also do an immediate refresh as a fallback
        setTimeout(refreshContent, 600);
        return;
      }

      if (data.errors) {
        Object.keys(data.errors).forEach((fieldName) => {
          const msgs = data.errors![fieldName];
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

// Auto-initialize from data attribute on any element
document.addEventListener("DOMContentLoaded", () => {
  const el = document.querySelector("[data-workflow-ws]") as HTMLElement | null;
  if (el?.dataset.workflowWs) {
    connectWorkflowWs(el.dataset.workflowWs);
  }
});
