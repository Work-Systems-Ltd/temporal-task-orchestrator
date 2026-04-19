// Apply theme immediately (before paint) to prevent flash of wrong theme.
// This file must be loaded synchronously in <head> — do NOT use defer/async.
(function () {
  const theme = localStorage.getItem("theme");
  if (theme === "dark" || (!theme && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
    document.documentElement.classList.add("dark");
  }
})();

// Register the Alpine theme store once Alpine is ready
document.addEventListener("alpine:init", () => {
  (window as any).Alpine.store("theme", {
    dark: document.documentElement.classList.contains("dark"),
    toggle() {
      this.dark = !this.dark;
      document.documentElement.classList.toggle("dark", this.dark);
      localStorage.setItem("theme", this.dark ? "dark" : "light");
    },
  });
});
