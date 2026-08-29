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

/* ── Application shell (sidebar + topbar) ── */
function mountShell() {
    const b = document.body;
    const role = b.dataset.role || 'editor';
    const active = b.dataset.active || '';
    const userName = b.dataset.user || '';
    const roleLabel = role === 'approver' ? 'Admin' : 'Editor';
    const subtitle = role === 'approver' ? 'Approver · Admin' : 'Content Editor';
    const links = role === 'approver'
        ? [['/review', '▦', 'Approval workspace'], ['/review?tab=team', '♙', 'Team management']]
        : [['/', '▦', 'Content workspace'], ['/html-editor', '&lt;/&gt;', 'HTML designer'], ['/?tab=stories', '✦', 'Canvas / AI designer']];

    const screen = document.getElementById('screen');
    const app = document.createElement('section');
    app.id = 'app';
    app.innerHTML =
        '<aside class="sidebar" id="sidebar">' +
            '<div class="side-logo"><div class="logo"><img src="/assets/nicdc-wide.png" alt="NICDC logo"><div class="logo-copy"><b>Social Studio</b><span>Approval &amp; publishing</span></div></div></div>' +
            '<div class="workspace-name">' + roleLabel.toUpperCase() + ' WORKSPACE</div>' +
            '<nav class="nav">' + links.map(function (l) {
                const isActive = l[0] === active;
                return '<a href="' + l[0] + '" class="' + (isActive ? 'active' : '') + '"><span>' + l[1] + '</span>' + l[2] +
                    '<span class="nav-arrow">' + (isActive ? '›' : '') + '</span></a>';
            }).join('') + '</nav>' +
            '<div class="profile"><div class="user"><i class="avatar">' + escHtml(initials(userName)) + '</i><span><b>' + escHtml(userName) + '</b><small>' + subtitle + '</small></span><span></span></div>' +
            '<button class="signout" onclick="logout()">↪ Sign out</button></div>' +
        '</aside>' +
        '<div class="main">' +
            '<header class="topbar">' +
                '<button class="menu" onclick="document.getElementById(\'sidebar\').classList.toggle(\'open\')">☰</button>' +
                '<div class="crumb"><span>NICDC Social Studio</span><b>›</b><b>' + roleLabel + '</b></div>' +
                '<div class="top-actions"><button class="bell" title="Notifications">♢</button><i class="avatar top-avatar">' + escHtml(initials(userName)) + '</i></div>' +
            '</header>' +
        '</div>';
    b.insertBefore(app, screen);
    app.querySelector('.main').appendChild(screen);
}

/* ── Legacy compat shims ── */
function icon() { return ''; }
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
    return '<article class="stat"><span class="stat-icon">' + icon + '</span><div><strong>' + value + '</strong><label>' + label + '</label></div><small>' + (note || '') + '</small></article>';
}

function emptyState(icon, title, sub, actionHtml) {
    return '<div class="empty"><i class="empty-icon">' + icon + '</i><h3>' + title + '</h3><p>' + (sub || '') + '</p>' + (actionHtml || '') + '</div>';
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
            rows += '<div class="result"><span>' + escHtml(label) + '</span><span class="ok">✓ Published</span>' +
                (url ? '<a href="' + escHtml(url) + '" target="_blank" rel="noopener">↗</a>' : '<span></span>') + '</div>';
        });
        if (!rows && results.post_id) {
            rows = '<div class="result"><span>Posted</span><span class="ok">✓ ' + escHtml(results.post_id) + '</span><span></span></div>';
        }
    } else {
        Object.keys(results).forEach(function (k) {
            const r = results[k];
            if (!r || typeof r !== 'object' || !r.status) return;
            const label = PLATFORM_NAMES[k] || k;
            rows += '<div class="result"><span>' + escHtml(label) + '</span>' +
                (r.status === 'published'
                    ? '<span class="ok">✓ Published · ' + escHtml(r.post_id || '') + '</span>'
                    : '<span class="fail">× Failed</span>') + '<span></span></div>';
        });
    }
    if (!rows) return '';
    const mock = (results.mode !== 'real' || results.note)
        ? '<div class="mock">⚡ Mock mode — no real posts were published.</div>' : '';
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
        '<div class="dialog-head"><span class="dialog-symbol">' + symbol + '</span><div><h2>' + title + '</h2><p>' + sub + '</p></div>' +
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
