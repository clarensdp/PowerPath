/* Sign-in dialog (Office Dialog API). Exchanges credentials with PowerPath on the same origin
   and hands only the session token back to the task pane. Nothing is stored here. */
(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }
  function send(msg) { Office.context.ui.messageParent(JSON.stringify(msg)); }

  Office.onReady(function () {
    $('login').onsubmit = async function (ev) {
      ev.preventDefault();
      $('status').textContent = 'Signing in…';
      $('status').className = '';
      try {
        var r = await fetch('/api/v27/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({ email: $('email').value.trim(), password: $('password').value })
        });
        var d = await r.json();
        $('password').value = '';
        if (!r.ok || !d.access_token) throw new Error(typeof d.detail === 'string' ? d.detail : 'Sign-in failed');
        var expires = d.expires_at || (d.expires_in ? new Date(Date.now() + d.expires_in * 1000).toISOString() : null);
        send({ type: 'session', token: d.access_token, expires_at: expires, email: $('email').value.trim() });
      } catch (e) {
        $('status').textContent = e.message;
        $('status').className = 'error';
      }
    };
  });
})();
