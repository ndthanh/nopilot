// Apply before CSS paints, so a remembered dark theme does not flash white.
(() => {
  const root = document.documentElement;
  const key = 'nopilot.theme';
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let saved;
  try { saved = localStorage.getItem(key) ?? localStorage.getItem('kopilot.theme'); } catch {}
  let explicit = saved === 'dark' || saved === 'light';
  function apply(theme) {
    root.dataset.theme = theme;
    const button = document.getElementById('themeToggle');
    if (!button) return;
    const dark = theme === 'dark';
    button.textContent = dark ? '☀' : '☾';
    button.setAttribute('aria-pressed', String(dark));
    button.setAttribute('aria-label', dark ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối');
    button.title = dark ? 'Giao diện sáng' : 'Giao diện tối';
  }
  apply(explicit ? saved : system.matches ? 'dark' : 'light');
  document.addEventListener('DOMContentLoaded', () => {
    apply(root.dataset.theme);
    document.getElementById('themeToggle').addEventListener('click', () => {
      const theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      explicit = true;
      try { localStorage.setItem(key, theme); } catch {}
      apply(theme);
    });
  });
  system.addEventListener('change', event => {
    if (!explicit) apply(event.matches ? 'dark' : 'light');
  });
})();
