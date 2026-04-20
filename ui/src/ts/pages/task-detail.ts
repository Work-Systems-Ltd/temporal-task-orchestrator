/**
 * Alpine.js components for the task detail page:
 * - commentForm: add comments to a task
 * - statusActions: change task status
 */

declare global {
  interface Window {
    commentForm: typeof commentForm;
    statusActions: typeof statusActions;
  }
}

function commentForm() {
  return {
    content: "",
    isInternal: false,
    submitting: false,
    error: "",

    async submit() {
      const taskId = document
        .querySelector<HTMLElement>("[data-task-id]")
        ?.dataset.taskId;
      if (!taskId) return;

      this.submitting = true;
      this.error = "";
      try {
        const resp = await fetch(`/tasks/${taskId}/comments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            content: this.content,
            is_internal: this.isInternal,
          }),
        });
        const data = await resp.json();
        if (data.ok) {
          this.content = "";
          this.isInternal = false;
          window.location.reload();
        } else {
          this.error = data.error || "Failed to add comment";
        }
      } catch {
        this.error = "Network error";
      }
      this.submitting = false;
    },
  };
}

function statusActions() {
  return {
    loading: false,
    error: "",

    async changeStatus(status: string) {
      const taskId = document
        .querySelector<HTMLElement>("[data-task-id]")
        ?.dataset.taskId;
      if (!taskId) return;

      this.loading = true;
      this.error = "";
      try {
        const resp = await fetch(`/tasks/${taskId}/status`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        });
        const data = await resp.json();
        if (data.ok) {
          window.location.reload();
        } else {
          this.error = data.error || "Failed to update status";
        }
      } catch {
        this.error = "Network error";
      }
      this.loading = false;
    },
  };
}

window.commentForm = commentForm;
window.statusActions = statusActions;
