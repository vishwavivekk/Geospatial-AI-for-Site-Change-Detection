/* ═══ NICDC Social Studio — shared helpers ═══ */

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

/* ── Inline SVG icons (stroke style, Lucide-like) ── */
const ICONS = {
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    sparkles: '<path d="m12 3 1.9 5.7a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3Z"/>',
    undo: '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-15-6.7L3 13"/>',
    redo: '<path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 15-6.7L21 13"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    comment: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    pin: '<path d="M12 17v5"/><path d="M9 10.8V5a3 3 0 1 1 6 0v5.8l2.7 2.7a1 1 0 0 1-.7 1.7H7a1 1 0 0 1-.7-1.7Z"/>',
    back: '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    edit: '<path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
    layers: '<path d="m12 2 9 4.9-9 4.9-9-4.9Z"/><path d="m3 11.9 9 4.9 9-4.9"/><path d="m3 16.9 9 4.9 9-4.9"/>',
    inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.7 4H7.3a2 2 0 0 0-1.8 1.1Z"/>',
    file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    image: '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
    rocket: '<path d="M4.5 16.5c-1.5 1.3-2 5-2 5s3.7-.5 5-2c.7-.8.7-2 0-2.8a2 2 0 0 0-3-.2Z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.9A12.9 12.9 0 0 1 22 2c0 2.7-.9 7.4-6 11a22 22 0 0 1-4 2Z"/><path d="M9 12H4s.5-3.9 2-5c1.7-1.2 5 0 5 0"/><path d="M12 15v5s3.9-.5 5-2c1.2-1.7 0-5 0-5"/>',
    alert: '<path d="m21.7 18-8-14a2 2 0 0 0-3.5 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
};

function icon(name, size) {
    const path = ICONS[name] || '';
    const s = size || 16;
    return '<svg class="ic" style="width:' + s + 'px;height:' + s + 'px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + path + '</svg>';
}

/* ── Toasts ── */
function toast(msg, type) {
    type = type || 'info';
    let root = document.getElementById('toast-root');
    if (!root) {
        root = document.createElement('div');
        root.id = 'toast-root';
        document.body.appendChild(root);
    }
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.innerHTML = icon(type === 'success' ? 'check' : type === 'error' ? 'alert' : 'sparkles', 17) + '<span>' + escHtml(msg) + '</span>';
    root.appendChild(el);
    setTimeout(function () {
        el.style.transition = 'opacity 0.3s, transform 0.3s';
        el.style.opacity = '0';
        el.style.transform = 'translateY(6px)';
        setTimeout(function () { el.remove(); }, 320);
    }, 3800);
}

/* ── Status / formatting helpers ── */
function statusBadge(status) {
    const labels = {
        pending: 'Waiting for review',
        feedback: 'Changes requested',
        approved: 'Approved',
        published: 'Published',
        rejected: 'Rejected',
    };
    return '<span class="badge st-' + status + '"><span class="dot"></span>' + (labels[status] || status) + '</span>';
}

function catBadge(category) {
    return '<span class="badge cat-' + escHtml(category) + '">' + escHtml(category) + '</span>';
}

function fmtTime(iso) {
    if (!iso) return '';
    try {
        const d = new Date(iso);
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ', ' +
               d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    } catch (e) { return iso; }
}

function initials(name) {
    return String(name || '?').split(/\s+/).map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

function publishPills(results) {
    if (!results) return '';
    const names = { instagram: 'Instagram', x: 'X (Twitter)', linkedin: 'LinkedIn' };
    return '<div class="pub-results">' + Object.keys(results).map(function (k) {
        const r = results[k];
        if (r.status === 'published') {
            return '<span class="pub-pill">' + icon('check', 13) + names[k] + ' <span class="pid">' + escHtml(r.post_id || '') + '</span></span>';
        }
        return '<span class="pub-pill failed">' + icon('x', 13) + names[k] + ' failed</span>';
    }).join('') + '</div>';
}

function emptyState(iconName, title, sub) {
    return '<div class="empty">' + icon(iconName, 40) +
        '<div class="t">' + title + '</div>' +
        '<div>' + (sub || '') + '</div></div>';
}

function skeletonCards(n) {
    let html = '';
    for (let i = 0; i < (n || 2); i++) {
        html += '<div class="sk-card">' +
            '<div class="sk" style="width:45%;height:18px;margin-bottom:12px;"></div>' +
            '<div class="sk" style="width:28%;height:12px;margin-bottom:16px;"></div>' +
            '<div class="sk" style="width:100%;height:12px;margin-bottom:8px;"></div>' +
            '<div class="sk" style="width:80%;height:12px;"></div>' +
        '</div>';
    }
    return html;
}

/* ── Read-only Konva mini preview ── */
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
    size = size || 224;
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
    miniLayer.batchDraw();
    requestAnimationFrame(function () { miniLayer.batchDraw(); });
}
