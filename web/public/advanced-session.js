let token = '';
export async function workspaceFetch(path, options = {}) {
    const url = new URL(path, location.href);
    if (url.origin !== location.origin || !url.pathname.startsWith('/api/')) {
        throw new Error('Invalid workspace API address');
    }
    const headers = new Headers(options.headers);
    if (token) headers.set('Authorization', 'Bearer ' + token);
    return window.fetch(url, {...options, headers, redirect: 'error'});
}
export async function enterWorkspace(start) {
    const root = document.getElementById('app');
    try {
        const response = await workspaceFetch('/api/health');
        if (!response.ok) throw new Error('Health check failed');
        const health = await response.json();
        if (health.v27_auth_mode === 'local_only') return start();
        if (health.v27_auth_mode !== 'required') throw new Error('Unknown authentication mode');
    } catch {
        root.textContent = 'Could not check the workspace connection. Refresh to retry.';
        return;
    }
    root.innerHTML = '<main class="panel"><h1>Sign in to the detailed workspace</h1><form id="detail-login"><label>Email<input name="email" type="email" autocomplete="username" required></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><button type="submit">Sign in</button><p role="status" aria-live="polite"></p></form></main>';
    const form = root.querySelector('form');
    const status = form.querySelector('[role=status]');
    const button = form.querySelector('button');
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (button.disabled) return;
        button.disabled = true;
        status.textContent = 'Signing in…';
        try {
            const response = await workspaceFetch('/api/v27/auth/login', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify(Object.fromEntries(new FormData(form)))
            });
            if (!response.ok) throw new Error('Sign-in failed (HTTP ' + response.status + ').');
            const result = await response.json();
            if (!result.access_token) throw new Error('No session returned.');
            token = result.access_token;
            form.elements.password.value = '';
            const me = await workspaceFetch('/api/v27/me');
            if (!me.ok) throw new Error('Workspace access failed (HTTP ' + me.status + ').');
            status.textContent = 'Signed in. Loading projects and saved runs…';
            await start();
        } catch (err) {
            token = '';
            status.textContent = err.message;
            button.disabled = false;
        }
    });
}
