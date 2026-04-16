// Page loader: shows a loading animation on first session visit.
// This file should be loaded with `defer` so the DOM is parsed before it runs.
(function () {
  const loader = document.getElementById("page-loader");
  if (!loader) return;

  // Only show the loader on the first visit of the session
  if (sessionStorage.getItem("loaded")) {
    loader.remove();
    return;
  }

  sessionStorage.setItem("loaded", "1");
  window.addEventListener("load", () => {
    setTimeout(() => {
      loader.classList.add("is-hidden");
      setTimeout(() => loader.remove(), 500);
    }, 800);
  });
})();
