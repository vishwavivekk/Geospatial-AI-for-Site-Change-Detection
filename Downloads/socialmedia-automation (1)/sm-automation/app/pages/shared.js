/* ═══ NICDC Social Studio — shared helpers (mockup design system) ═══ */

function escHtml(s) {
    if (typeof s !== 'string') return String(s);
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function escId(s) {
    return String(s).replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 64);
}

async function logout() {
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = '/login';
}

function initials(name) {
    return String(name || '?').split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

function fmtTime(iso) {
    if (!iso) return '';
    try {
        const d = new Date(iso);
        return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) +
            ', ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    } catch (e) { return iso; }
}


/* ── SVG icon system (lucide-style, stroke = currentColor) ── */
const ICONS = {
    'grid': '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
    'shield': '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1 1 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    'code': '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    'sparkles': '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/>',
    'users': '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    'user-plus': '<path d="M2 21a8 8 0 0 1 13.292-6"/><circle cx="10" cy="8" r="5"/><path d="M19 16v6"/><path d="M22 19h-6"/>',
    'bell': '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    'logout': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
    'menu': '<line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="18" y2="18"/>',
    'search': '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    'inbox': '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    'clock': '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    'reply': '<polyline points="9 14 4 9 9 4"/><path d="M20 20v-7a4 4 0 0 0-4-4H4"/>',
    'check': '<path d="M20 6 9 17l-5-5"/>',
    'check-circle': '<path d="M21.801 10A10 10 0 1 1 17 3.335"/><path d="m9 11 3 3L22 4"/>',
    'alert': '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
    'zap': '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    'arrow-right': '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    'arrow-left': '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    'comment': '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    'trash': '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    'undo': '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>',
    'redo': '<path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3L21 13"/>',
    'download': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
    'upload': '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
    'send': '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
    'plus': '<path d="M5 12h14"/><path d="M12 5v14"/>',
    'image': '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
    'eye': '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    'refresh': '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    'history': '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    'chev-down': '<path d="m6 9 6 6 6-6"/>',
    'chev-left': '<path d="m15 18-6-6 6-6"/>',
    'chev-right': '<path d="m9 18 6-6-6-6"/>',
    'external': '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    'crosshair': '<circle cx="12" cy="12" r="10"/><line x1="22" x2="18" y1="12" y2="12"/><line x1="6" x2="2" y1="12" y2="12"/><line x1="12" x2="12" y1="6" y2="2"/><line x1="12" x2="12" y1="22" y2="18"/>',
    'pin': '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    'pencil': '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
    'dot': '<circle cx="12" cy="12" r="5" fill="currentColor" stroke="none"/>',
    'square': '<rect width="18" height="18" x="3" y="3" rx="2"/>',
    'circle': '<circle cx="12" cy="12" r="10"/>',
    'ellipse': '<ellipse cx="12" cy="12" rx="10" ry="7"/>',
    'line': '<line x1="5" x2="19" y1="19" y2="5"/>',
    'star': '<path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/>',
    'ring': '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4"/>',
    'pentagon': '<path d="M10.83 2.38a2 2 0 0 1 2.34 0l8 5.74a2 2 0 0 1 .73 2.25l-3.04 9.26a2 2 0 0 1-1.9 1.37H7.04a2 2 0 0 1-1.9-1.37L2.1 10.37a2 2 0 0 1 .73-2.25z"/>',
    'shapes': '<path d="M8.3 10a.7.7 0 0 1-.626-1.079L11.4 3a.7.7 0 0 1 1.198-.043L16.3 8.9a.7.7 0 0 1-.572 1.1Z"/><rect x="3" y="14" width="7" height="7" rx="1"/><circle cx="17.5" cy="17.5" r="3.5"/>',
    'layout': '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/>',
    'list': '<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M8 6h13"/>',
    'lock': '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    'linkedin': '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/>',
    'x-brand': '<path fill="currentColor" stroke="none" d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zM17.083 19.77h1.833L7.084 4.126H5.117z"/>',
    'instagram': '<rect width="20" height="20" x="2" y="2" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" x2="17.51" y1="6.5" y2="6.5"/>',
};
function svg(name, size) {
    const body = ICONS[name];
    if (!body) return '';
    const s = size || 16;
    return '<svg class="ic" width="' + s + '" height="' + s + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + body + '</svg>';
}
function applyIcons(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('[data-icon]').forEach(function (el) {
        el.classList.add('ic-wrap');
        el.innerHTML = svg(el.getAttribute('data-icon'), parseInt(el.getAttribute('data-icon-size'), 10) || 16);
        el.removeAttribute('data-icon');
    });
}
(function () {
    const run = function () { applyIcons(document); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
    new MutationObserver(function () { applyIcons(document); }).observe(document.documentElement, { childList: true, subtree: true });
})();

/* ── Application shell (sidebar + topbar) ── */
function mountShell() {
    const b = document.body;
    const role = b.dataset.role || 'editor';
    const active = b.dataset.active || '';
    const userName = b.dataset.user || '';
    const roleLabel = role === 'approver' ? 'Admin' : 'Editor';
    const subtitle = role === 'approver' ? 'Approver · Admin' : 'Content Editor';
    const links = role === 'approver'
        ? [['/review', 'shield', 'Approval workspace'], ['/review?tab=team', 'users', 'Team management']]
        : [['/', 'grid', 'Content workspace'], ['/html-editor', 'code', 'HTML designer'], ['/?tab=stories', 'sparkles', 'Canvas / AI designer']];

    const screen = document.getElementById('screen');
    const app = document.createElement('section');
    app.id = 'app';
    app.innerHTML =
        '<aside class="sidebar" id="sidebar">' +
            '<button class="side-toggle" id="sideToggle" title="Collapse sidebar">‹</button>' +
            '<div class="side-logo"><div class="logo"><img src="/assets/nicdc-wide.png" alt="NICDC logo"><div class="logo-copy"><b>Social Studio</b><span>Approval &amp; publishing</span></div></div></div>' +
            '<div class="workspace-name">' + roleLabel.toUpperCase() + ' WORKSPACE</div>' +
            '<nav class="nav">' + links.map(function (l) {
                const isActive = l[0] === active;
                const plain = l[2].replace(/&[a-z]+;|<[^>]*>/g, '');
                return '<a href="' + l[0] + '" class="' + (isActive ? 'active' : '') + '" title="' + plain + '"><span class="ic-wrap">' + svg(l[1], 16) + '</span><em class="nav-text" style="font-style:normal;">' + l[2] + '</em>' +
                    '<span class="nav-arrow">' + (isActive ? '›' : '') + '</span></a>';
            }).join('') + '</nav>' +
            '<div class="profile"><div class="user"><i class="avatar">' + escHtml(initials(userName)) + '</i><span><b>' + escHtml(userName) + '</b><small>' + subtitle + '</small></span><span></span></div>' +
            '<button class="signout" onclick="logout()" title="Sign out">' + svg('logout', 14) + ' <em class="nav-text" style="font-style:normal;">Sign out</em></button></div>' +
        '</aside>' +
        '<div class="main">' +
            '<header class="topbar">' +
                '<button class="menu" onclick="document.getElementById(\'sidebar\').classList.toggle(\'open\')">' + svg('menu', 17) + '</button>' +
                '<div class="crumb"><span>NICDC Social Studio</span><b>›</b><b>' + roleLabel + '</b></div>' +
                '<div class="top-actions"><button class="bell" title="Notifications">' + svg('bell', 15) + '</button><i class="avatar top-avatar">' + escHtml(initials(userName)) + '</i></div>' +
            '</header>' +
        '</div>';
    b.insertBefore(app, screen);
    app.querySelector('.main').appendChild(screen);

    // Collapsible sidebar: icons only when collapsed, hover to peek, arrow to pin
    const toggle = document.getElementById('sideToggle');
    const sidebarEl = document.getElementById('sidebar');
    toggle.innerHTML = svg('chev-left', 12);
    let holdPeek = false; // right after collapsing the pointer is still on the panel — show the rail, don't peek until the pointer leaves once
    function setCollapsed(collapsed, save) {
        b.classList.toggle('side-collapsed', collapsed);
        sidebarEl.classList.toggle('rail', collapsed);
        sidebarEl.classList.remove('peek');
        toggle.innerHTML = svg(collapsed ? 'chev-right' : 'chev-left', 12);
        toggle.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
        if (save) try { localStorage.setItem('side.collapsed', collapsed ? '1' : ''); } catch (e) {}
        setTimeout(function () { window.dispatchEvent(new Event('resize')); }, 200);
    }
    toggle.addEventListener('click', function () {
        const collapse = !b.classList.contains('side-collapsed');
        holdPeek = collapse;
        setCollapsed(collapse, true);
    });
    sidebarEl.addEventListener('mouseenter', function () {
        if (b.classList.contains('side-collapsed') && !holdPeek) {
            sidebarEl.classList.add('peek');
            sidebarEl.classList.remove('rail');
        }
    });
    sidebarEl.addEventListener('mouseleave', function () {
        holdPeek = false;
        if (b.classList.contains('side-collapsed')) {
            sidebarEl.classList.remove('peek');
            sidebarEl.classList.add('rail');
        }
    });
    try { if (localStorage.getItem('side.collapsed') === '1') setCollapsed(true, false); } catch (e) {}
}

/* ── Legacy compat shims ── */
function icon(name, size) { return svg(name, size); }
function catBadge(category) {
    return '<span class="role editor" style="font-size:8px;">' + escHtml(category) + '</span>';
}
function publishPills(results) { return publishResults(results); }
function skeletonCards(n) { return skeletonGrid(n); }

/* ── Component helpers ── */
const STATUS_META = {
    draft:     ['draft', 'Draft'],
    pending:   ['review', 'Waiting for review'],
    feedback:  ['changes', 'Changes requested'],
    approved:  ['approved', 'Approved'],
    published: ['published', 'Published'],
    rejected:  ['rejected', 'Rejected'],
};

function statusBadge(status, adminView) {
    const m = STATUS_META[status] || ['draft', status];
    let label = m[1];
    if (adminView && status === 'pending') label = 'Needs review';
    return '<span class="badge ' + m[0] + '">' + label + '</span>';
}

const PLATFORM_META = { linkedin: ['in', 'in'], x: ['', 'X'], instagram: ['ig', 'ig'] };
function platformChips(arr) {
    return '<div class="platforms">' + (arr || []).map(function (p) {
        const m = PLATFORM_META[p] || ['', p];
        return '<span class="platform ' + m[0] + '">' + m[1] + '</span>';
    }).join('') + '</div>';
}

function pageHead(eyebrow, title, copy, actions) {
    return '<div class="page-head"><div><span class="eyebrow">' + eyebrow + '</span><h1>' + title + '</h1><p>' + copy + '</p></div>' +
        '<div class="page-actions">' + (actions || '') + '</div></div>';
}

function statCard(icon, value, label, note) {
    return '<article class="stat"><span class="stat-icon">' + (ICONS[icon] ? svg(icon, 20) : icon) + '</span><div><strong>' + value + '</strong><label>' + label + '</label></div><small>' + (note || '') + '</small></article>';
}

function emptyState(icon, title, sub, actionHtml) {
    return '<div class="empty"><i class="empty-icon">' + (ICONS[icon] ? svg(icon, 22) : icon) + '</i><h3>' + title + '</h3><p>' + (sub || '') + '</p>' + (actionHtml || '') + '</div>';
}

function skeletonGrid(n) {
    let html = '<div class="skeletons">';
    for (let i = 0; i < (n || 3); i++) {
        html += '<div><div class="skeleton img"></div><div class="skeleton line"></div><div class="skeleton line short"></div></div>';
    }
    return html + '</div>';
}

/* ── Toast (mockup style) ── */
function toast(msg, type) {
    let t = document.getElementById('toast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'toast';
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.className = 'toast' + (type === 'error' ? ' error' : '');
    clearTimeout(t._timer);
    t._timer = setTimeout(function () { t.className = 'hidden'; }, 3200);
}

/* ── Publish results (mockup .results rows) ── */
const PLATFORM_NAMES = { linkedin: 'LinkedIn', x: 'X', instagram: 'Instagram' };

function publishResults(results) {
    if (!results) return '';
    let rows = '';
    if (results.mode === 'real') {
        const urls = results.post_urls || {};
        (results.platforms || []).forEach(function (p) {
            const platform = p.platform || 'unknown';
            const label = PLATFORM_NAMES[platform] || platform;
            const url = urls[platform];
            rows += '<div class="result"><span>' + escHtml(label) + '</span><span class="ok">' + svg('check', 11) + ' Published</span>' +
                (url ? '<a href="' + escHtml(url) + '" target="_blank" rel="noopener">' + svg('external', 11) + '</a>' : '<span></span>') + '</div>';
        });
        if (!rows && results.post_id) {
            rows = '<div class="result"><span>Posted</span><span class="ok">' + svg('check', 11) + ' ' + escHtml(results.post_id) + '</span><span></span></div>';
        }
    } else {
        Object.keys(results).forEach(function (k) {
            const r = results[k];
            if (!r || typeof r !== 'object' || !r.status) return;
            const label = PLATFORM_NAMES[k] || k;
            rows += '<div class="result"><span>' + escHtml(label) + '</span>' +
                (r.status === 'published'
                    ? '<span class="ok">' + svg('check', 11) + ' Published · ' + escHtml(r.post_id || '') + '</span>'
                    : '<span class="fail">× Failed</span>') + '<span></span></div>';
        });
    }
    if (!rows) return '';
    const mock = (results.mode !== 'real' || results.note)
        ? '<div class="mock">' + svg('zap', 11) + ' Mock mode — no real posts were published.</div>' : '';
    return '<div class="results">' + rows + mock + '</div>';
}

/* ── Dialog helper (mockup .dialog) ── */
function openDialog(symbol, title, sub, bodyHtml, footHtml) {
    let root = document.getElementById('modal');
    if (!root) {
        root = document.createElement('div');
        root.id = 'modal';
        document.body.appendChild(root);
    }
    root.innerHTML =
        '<div class="dialog-overlay" onclick="if(event.target===this)closeDialog()"><div class="dialog">' +
        '<div class="dialog-head"><span class="dialog-symbol">' + (ICONS[symbol] ? svg(symbol, 18) : symbol) + '</span><div><h2>' + title + '</h2><p>' + sub + '</p></div>' +
        '<button class="dialog-close" onclick="closeDialog()">×</button></div>' +
        '<div class="dialog-body">' + bodyHtml + '</div>' +
        (footHtml ? '<div class="dialog-foot">' + footHtml + '</div>' : '') +
        '</div></div>';
}
function closeDialog() {
    const root = document.getElementById('modal');
    if (root) root.innerHTML = '';
}

/* ── Resizable panels ── */
function clampNum(v, min, max) { return Math.max(min, Math.min(max, v)); }

function makeGutter() {
    const g = document.createElement('div');
    g.className = 'gutter';
    return g;
}

/* Drag primitive: cb({type:'start'|'move'|'end', dx}) */
function dragHorizontal(handle, cb) {
    handle.addEventListener('pointerdown', function (e) {
        e.preventDefault();
        try { handle.setPointerCapture(e.pointerId); } catch (err) {}
        handle.classList.add('drag');
        document.body.style.cursor = 'col-resize';
        const sx = e.clientX;
        cb({ type: 'start', dx: 0 });
        function mv(ev) { cb({ type: 'move', dx: ev.clientX - sx }); }
        function up(ev) {
            handle.classList.remove('drag');
            document.body.style.cursor = '';
            handle.removeEventListener('pointermove', mv);
            handle.removeEventListener('pointerup', up);
            cb({ type: 'end', dx: ev.clientX - sx });
        }
        handle.addEventListener('pointermove', mv);
        handle.addEventListener('pointerup', up);
    });
}

/* Column resizer bound to a stored width. dir=1: dragging right grows;
   dir=-1: dragging right shrinks (right-hand panels). */
function columnResizer(gutter, opts) {
    let value = +(localStorage.getItem(opts.key) || opts.value);
    value = clampNum(value, opts.min, opts.max);
    let start = value;
    opts.apply(value);
    dragHorizontal(gutter, function (e) {
        if (e.type === 'start') { start = value; return; }
        value = clampNum(start + e.dx * (opts.dir || 1), opts.min, opts.max);
        opts.apply(value);
        if (e.type === 'end') try { localStorage.setItem(opts.key, String(Math.round(value))); } catch (err) {}
    });
    return { get: function () { return value; } };
}

/* ── Read-only Konva mini preview (templates / story designs) ── */
function createReadOnlyNode(el) {
    const a = el.attrs || {};
    const config = {};
    for (const k in a) { if (a[k] !== undefined && a[k] !== null) config[k] = a[k]; }
    config.draggable = false;
    config.listening = false;
    switch (el.type) {
        case 'rect': return new Konva.Rect(config);
        case 'text': return new Konva.Text(config);
        case 'circle': return new Konva.Circle(config);
        case 'ellipse': return new Konva.Ellipse(config);
        case 'line': return new Konva.Line(config);
        case 'path': return new Konva.Path(config);
        case 'star': return new Konva.Star(config);
        case 'ring': return new Konva.Ring(config);
        case 'polygon': return new Konva.Line(Object.assign({}, config, { closed: true }));
        case 'image': {
            if (!a.src) return null;
            const img = new Image();
            if (a.src.indexOf('/') !== 0) img.crossOrigin = 'anonymous';
            img.src = a.src;
            const node = new Konva.Image(Object.assign({}, config, { image: img }));
            img.onerror = function () { node.destroy(); };
            return node;
        }
        default: return null;
    }
}

function renderMiniPreview(containerId, designState, size) {
    const container = document.getElementById(containerId);
    if (!container || !designState) return;
    size = size || 200;
    const cw = designState.canvas ? designState.canvas.width || 1080 : 1080;
    const ch = designState.canvas ? designState.canvas.height || 1080 : 1080;
    const scale = Math.min(size / cw, size / ch);
    const miniStage = new Konva.Stage({ container: containerId, width: cw * scale, height: ch * scale });
    const miniLayer = new Konva.Layer();
    miniStage.add(miniLayer);
    miniLayer.add(new Konva.Rect({
        x: 0, y: 0, width: cw * scale, height: ch * scale,
        fill: (designState.canvas && designState.canvas.background) || '#F3F7FA',
        listening: false,
    }));
    const group = new Konva.Group({ scaleX: scale, scaleY: scale, listening: false });
    miniLayer.add(group);
    (designState.elements || []).forEach(function (el) {
        const node = createReadOnlyNode(el);
        if (node) {
            group.add(node);
            if (el.type === 'image') {
                const imgEl = node.image();
                if (imgEl && !imgEl.complete) imgEl.onload = function () { miniLayer.batchDraw(); };
            }
        }
    });
    miniLayer.draw();
    requestAnimationFrame(function () { miniLayer.batchDraw(); });
}
