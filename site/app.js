const copyButtons = () => {
  document.querySelectorAll('[data-copy]').forEach((button) => {
    button.addEventListener('click', async () => {
      const original = button.textContent;
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        button.textContent = 'COPIED';
      } catch {
        button.textContent = 'SELECT';
      }
      window.setTimeout(() => { button.textContent = original; }, 1600);
    });
  });
};

copyButtons();
