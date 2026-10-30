/* BloodConnect — progressive enhancements only; the site works without JS. */
(function () {
  'use strict';

  // Mobile navigation toggle.
  var toggle = document.getElementById('nav-toggle');
  var links = document.getElementById('nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var open = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  // Confirmation before destructive/consequential actions.
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (form instanceof HTMLFormElement && form.hasAttribute('data-confirm')) {
      if (!window.confirm(form.getAttribute('data-confirm'))) {
        event.preventDefault();
      }
    }
  });

  // Dismissable alert messages (plus gentle auto-dismiss).
  document.querySelectorAll('.alert-close').forEach(function (button) {
    button.addEventListener('click', function () {
      var alert = button.closest('.alert');
      if (alert) { alert.remove(); }
    });
  });
  document.querySelectorAll('.messages .alert').forEach(function (alert) {
    window.setTimeout(function () { alert.remove(); }, 8000);
  });
})();
