interface TaskListData {
  loading: boolean;
  refresh(): void;
  startPolling(): void;
  navigateTab(e: Event): void;
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

        const url = window.location.href;
        fetch(url)
          .then((r) => r.text())
          .then((html) => {
            const doc = new DOMParser().parseFromString(html, "text/html");
            const fresh = doc.querySelector("[data-tab-content]");
            const target = document.querySelector("[data-tab-content]");
            if (fresh && target) {
              target.innerHTML = fresh.innerHTML;
            }
          })
          .catch(() => {});
      }, 5000);
    },

    navigateTab(e: Event): void {
      e.preventDefault();
      const link = (e.currentTarget as HTMLAnchorElement);
      const url = link.href;

      history.pushState(null, "", url);

      fetch(url)
        .then((r) => r.text())
        .then((html) => {
          const doc = new DOMParser().parseFromString(html, "text/html");

          const freshContent = doc.querySelector("[data-tab-content]");
          const targetContent = document.querySelector("[data-tab-content]");
          if (freshContent && targetContent) {
            targetContent.innerHTML = freshContent.innerHTML;
          }

          const freshTabs = doc.querySelector("[data-tab-bar]");
          const targetTabs = document.querySelector("[data-tab-bar]");
          if (freshTabs && targetTabs) {
            targetTabs.innerHTML = freshTabs.innerHTML;
          }
        })
        .catch(() => {
          window.location.href = url;
        });
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
