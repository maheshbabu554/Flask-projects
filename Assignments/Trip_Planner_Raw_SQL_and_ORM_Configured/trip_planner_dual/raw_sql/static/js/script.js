/* Small progressive enhancements; all important validation is also server-side. */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.needs-validation').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add('was-validated');
    });
  });

  document.querySelectorAll('[data-toggle-password]').forEach((button) => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.dataset.togglePassword);
      if (!input) return;
      const showing = input.type === 'text';
      input.type = showing ? 'password' : 'text';
      button.textContent = showing ? 'Show' : 'Hide';
      button.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
    });
  });

  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  const startDate = document.getElementById('start_date');
  const endDate = document.getElementById('end_date');
  if (startDate && endDate) {
    startDate.addEventListener('change', () => {
      endDate.min = startDate.value;
      if (endDate.value && endDate.value < startDate.value) endDate.value = startDate.value;
    });
    endDate.addEventListener('change', () => {
      startDate.max = endDate.value;
    });
  }
});
