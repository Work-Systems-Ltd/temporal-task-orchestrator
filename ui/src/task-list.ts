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
            const fresh = doc.querySelector("main");
            if (fresh) {
              document.querySelector("main")!.innerHTML = fresh.innerHTML;
            }
          })
          .catch(() => {});
      }, 5000);
    },
  };
}

(window as Record<string, unknown>).taskList = taskList;
