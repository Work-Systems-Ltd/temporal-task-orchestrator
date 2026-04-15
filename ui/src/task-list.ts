interface TaskListData {
  loading: boolean;
  refresh(): void;
  startPolling(): void;
}

function taskList(): TaskListData {
  return {
    loading: false,

    refresh(): void {
      this.loading = true;
      setTimeout(() => window.location.reload(), 200);
    },

    startPolling(): void {
      setInterval(() => {
        if (document.hidden) return;

        fetch(window.location.href)
          .then((r) => r.text())
          .then((html) => {
            const doc = new DOMParser().parseFromString(html, "text/html");
            const fresh = doc.querySelector("[data-task-table]");
            const target = document.querySelector("[data-task-table]");
            if (fresh && target) {
              target.innerHTML = fresh.innerHTML;
            }
            const freshStats = doc.querySelector("[data-stats]");
            const targetStats = document.querySelector("[data-stats]");
            if (freshStats && targetStats) {
              targetStats.innerHTML = freshStats.innerHTML;
            }
          })
          .catch(() => {});
      }, 5000);
    },
  };
}

document.addEventListener("keydown", (e: KeyboardEvent) => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;

  if (e.key === "n") {
    window.location.href = "/start";
  }

  if (e.key === "r") {
    window.location.reload();
  }
});

(window as Record<string, unknown>).taskList = taskList;
