const loginForm = document.getElementById('loginForm');
if (loginForm) {
  loginForm.addEventListener('submit', () => {
    const button = loginForm.querySelector('button[type="submit"]');
    if (button) {
      button.disabled = true;
      button.textContent = button.dataset.loadingText || 'Entrando...';
    }
  });
}
