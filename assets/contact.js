// Reuse the Energy site's contact service; its CORS allow-list includes this site.
(() => {
  const form = document.getElementById('contact-form');
  if (!form) return;
  const status = document.getElementById('contact-status');
  const button = form.querySelector('button[type="submit"]');
  const started = Date.now();
  let sending = false;
  button.disabled = false;

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (sending || !form.reportValidity()) return;
    const fields = form.elements;
    if (!fields.message.value.trim()) {
      status.textContent = 'Please enter a message.';
      fields.message.focus();
      return;
    }
    const fillMs = Date.now() - started;
    if (fillMs < 3000) {
      status.textContent = 'Please wait a moment, then send again.';
      return;
    }
    sending = true;
    button.disabled = true;
    form.setAttribute('aria-busy', 'true');
    status.textContent = 'Sending…';
    try {
      const response = await fetch('https://energy.madeclear.ca/api/contact', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          name: fields.name.value,
          email: fields.email.value,
          message: fields.message.value,
          website: fields.website.value,
          fillMs
        })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        status.textContent = data.error || 'Could not send. Please try again later.';
        return;
      }
      form.reset();
      status.textContent = 'Sent. Thank you.';
    } catch {
      status.textContent = 'Could not send. Please try again later. Your message is still here.';
    } finally {
      sending = false;
      button.disabled = false;
      form.removeAttribute('aria-busy');
    }
  });
})();
