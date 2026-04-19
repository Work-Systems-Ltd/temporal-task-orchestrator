/**
 * Handles inline task form submission from the workflow detail page.
 * Posts to /task/{workflowId}/submit and handles JSON responses:
 * - {ok: true} → reload page
 * - {ok: false, gone: true} → reload page (task completed by someone else)
 * - {ok: false, errors: {...}} → show validation errors inline
 */

declare const Alpine: any;

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
        window.location.reload();
        return;
      }

      if (data.errors) {
        Object.keys(data.errors).forEach((fieldName) => {
          const msgs = data.errors![fieldName];
          const input = form.querySelector('[name="' + fieldName + '"]');
          if (!input) return;

          const container = input.closest(".space-y-1\\.5");
          if (!container) return;

          // Add error styling to the input
          const inputEl = container.querySelector(".input-field");
          if (inputEl) inputEl.classList.add("input-field-error");

          // Add error messages
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

// Expose globally for Alpine @submit.prevent calls
(window as any).submitInlineTask = submitInlineTask;
