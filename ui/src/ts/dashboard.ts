function easeOutExpo(t: number): number {
  return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

// Counter animation
const counters = document.querySelectorAll<HTMLElement>("[data-countup]");

counters.forEach((el, i) => {
  const target = parseInt(el.dataset.countup!, 10);
  if (!target || target <= 0) {
    el.textContent = "0";
    return;
  }

  const duration = target > 100 ? 900 : target > 10 ? 700 : 500;
  let start: number;

  function tick(now: number) {
    if (!start) start = now;
    const progress = Math.min((now - start) / duration, 1);
    el.textContent = Math.round(easeOutExpo(progress) * target).toLocaleString();
    if (progress < 1) requestAnimationFrame(tick);
  }

  setTimeout(() => requestAnimationFrame(tick), i * 80);
});

// Progress bar animation — bars grow from 0 width on load
const bars = document.querySelectorAll<HTMLElement>("[data-bar-width]");

bars.forEach((bar, i) => {
  const target = bar.dataset.barWidth!;
  bar.style.width = "0%";

  setTimeout(() => {
    bar.style.width = target;
  }, 300 + i * 100);
});
