// Fish Labeling Tool — Canvas-based bounding box annotation

const LABELS = {};
const COLORS = {};

// Parse label data from DOM
document.querySelectorAll(".species-btn").forEach(btn => {
    const id = parseInt(btn.dataset.classId);
    LABELS[id] = btn.textContent.trim().split("\n")[0].trim();
    COLORS[id] = btn.querySelector(".color-swatch").style.background;
});

// --- State ---

let images = [];
let currentIndex = 0;
let annotations = [];
let selectedClassId = 0;
let selectedAnnId = null;
let isDirty = false;

// Drawing state
let isDrawing = false;
let drawStart = null;
let drawCurrent = null;

// Resize state
let isResizing = false;
let resizeHandle = null;
let resizeAnn = null;

// Move state
let isMoving = false;
let moveAnn = null;
let moveOffset = null;

// Image and canvas
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
const img = new Image();
let imgScale = 1;

// Zoom/pan state
let zoom = 1;
let panX = 0;
let panY = 0;
let isPanning = false;
let panStart = null;

// DOM elements
const annotationsList = document.getElementById("annotations-list");
const noAnnotations = document.getElementById("no-annotations");
const imageCounter = document.getElementById("image-counter");
const filenameDisplay = document.getElementById("filename-display");
const statusMsg = document.getElementById("status-message");

// --- Init ---

async function init() {
    const resp = await fetch("/api/images");
    const data = await resp.json();
    images = data.images;

    if (images.length === 0) {
        showStatus("No images found in input directory.", "error");
        return;
    }

    // Select first label button
    document.querySelector(".species-btn").classList.add("active");

    await loadImage(0);
    updateProgress();
}

// --- Image loading ---

async function loadImage(index) {
    if (index < 0 || index >= images.length) return;

    // Auto-save if dirty
    if (isDirty) await saveAnnotations();

    currentIndex = index;
    const filename = images[currentIndex];

    imageCounter.textContent = `${currentIndex + 1} / ${images.length}`;
    filenameDisplay.textContent = filename;

    // Load annotations
    const resp = await fetch(`/api/annotations/${encodeURIComponent(filename)}`);
    const data = await resp.json();
    annotations = data.annotations || [];
    selectedAnnId = null;
    isDirty = false;

    // Load image
    img.onload = () => {
        fitCanvas();
        render();
        renderAnnotationsList();
    };
    img.src = `/api/image/${encodeURIComponent(filename)}`;
}

function fitCanvas() {
    const container = document.getElementById("canvas-container");
    const cw = container.clientWidth;
    const ch = container.clientHeight;

    const scaleX = cw / img.naturalWidth;
    const scaleY = ch / img.naturalHeight;
    imgScale = Math.min(scaleX, scaleY, 1);

    // Canvas is always full container size to support zoom/pan
    canvas.width = cw;
    canvas.height = ch;

    // Reset zoom/pan when loading new image
    zoom = 1;
    panX = 0;
    panY = 0;
}

function getImageRect() {
    // The drawn image rect within the canvas, accounting for zoom and pan
    const w = img.naturalWidth * imgScale * zoom;
    const h = img.naturalHeight * imgScale * zoom;
    const x = (canvas.width - w) / 2 + panX;
    const y = (canvas.height - h) / 2 + panY;
    return { x, y, w, h };
}

// --- Rendering ---

function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const ir = getImageRect();
    ctx.drawImage(img, ir.x, ir.y, ir.w, ir.h);

    for (const ann of annotations) {
        drawBox(ann, ann.id === selectedAnnId);
    }

    if (isDrawing && drawStart && drawCurrent) {
        const x = Math.min(drawStart.x, drawCurrent.x);
        const y = Math.min(drawStart.y, drawCurrent.y);
        const w = Math.abs(drawCurrent.x - drawStart.x);
        const h = Math.abs(drawCurrent.y - drawStart.y);
        ctx.strokeStyle = COLORS[selectedClassId];
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 3]);
        ctx.strokeRect(x, y, w, h);
        ctx.setLineDash([]);
    }

    // Zoom indicator
    if (zoom !== 1) {
        ctx.fillStyle = "rgba(0,0,0,0.6)";
        ctx.fillRect(canvas.width - 70, 8, 62, 22);
        ctx.fillStyle = "#fff";
        ctx.font = "12px sans-serif";
        ctx.fillText(`${Math.round(zoom * 100)}%`, canvas.width - 62, 23);
    }
}

function drawBox(ann, selected) {
    const ir = getImageRect();
    const x = ir.x + ann.x * ir.w;
    const y = ir.y + ann.y * ir.h;
    const w = ann.w * ir.w;
    const h = ann.h * ir.h;
    const color = COLORS[ann.class_id] || "#fff";

    ctx.fillStyle = color + "22";
    ctx.fillRect(x, y, w, h);

    ctx.strokeStyle = color;
    ctx.lineWidth = selected ? 3 : 2;
    ctx.strokeRect(x, y, w, h);

    // Label
    const label = LABELS[ann.class_id] || `class ${ann.class_id}`;
    ctx.font = "bold 13px sans-serif";
    const textW = ctx.measureText(label).width + 8;
    ctx.fillStyle = color;
    ctx.fillRect(x, y - 20, textW, 20);
    ctx.fillStyle = "#fff";
    ctx.fillText(label, x + 4, y - 6);

    // Resize handles
    if (selected) {
        const hs = 8;
        const handles = [
            [x, y], [x + w, y],
            [x, y + h], [x + w, y + h],
        ];
        ctx.fillStyle = "#fff";
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        for (const [hx, hy] of handles) {
            ctx.fillRect(hx - hs/2, hy - hs/2, hs, hs);
            ctx.strokeRect(hx - hs/2, hy - hs/2, hs, hs);
        }
    }
}

// --- Annotations list ---

function renderAnnotationsList() {
    annotationsList.innerHTML = "";
    noAnnotations.style.display = annotations.length ? "none" : "block";

    for (const ann of annotations) {
        const li = document.createElement("li");
        if (ann.id === selectedAnnId) li.classList.add("selected");

        const swatch = document.createElement("span");
        swatch.className = "color-swatch";
        swatch.style.background = COLORS[ann.class_id] || "#fff";
        li.appendChild(swatch);

        const text = document.createElement("span");
        text.textContent = LABELS[ann.class_id] || `class ${ann.class_id}`;
        li.appendChild(text);

        const del = document.createElement("button");
        del.className = "ann-delete";
        del.textContent = "\u00d7";
        del.title = "Delete annotation";
        del.addEventListener("click", (e) => {
            e.stopPropagation();
            deleteAnnotation(ann.id);
        });
        li.appendChild(del);

        li.addEventListener("click", () => {
            selectedAnnId = ann.id;
            render();
            renderAnnotationsList();
        });

        annotationsList.appendChild(li);
    }
}

// --- Mouse handling ---

function getMousePos(e) {
    const rect = canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
}

// Convert canvas pixel to normalized image coordinate [0,1]
function canvasToNorm(px, py) {
    const ir = getImageRect();
    return { x: (px - ir.x) / ir.w, y: (py - ir.y) / ir.h };
}

function hitTestHandles(px, py) {
    if (!selectedAnnId) return null;
    const ann = annotations.find(a => a.id === selectedAnnId);
    if (!ann) return null;

    const ir = getImageRect();
    const x = ir.x + ann.x * ir.w;
    const y = ir.y + ann.y * ir.h;
    const w = ann.w * ir.w;
    const h = ann.h * ir.h;
    const r = 10;

    const corners = {
        "nw": [x, y], "ne": [x + w, y],
        "sw": [x, y + h], "se": [x + w, y + h],
    };

    for (const [handle, [cx, cy]] of Object.entries(corners)) {
        if (Math.abs(px - cx) < r && Math.abs(py - cy) < r) {
            return { handle, ann };
        }
    }
    return null;
}

function hitTestBox(px, py) {
    const n = canvasToNorm(px, py);
    const nx = n.x;
    const ny = n.y;
    for (let i = annotations.length - 1; i >= 0; i--) {
        const ann = annotations[i];
        if (nx >= ann.x && nx <= ann.x + ann.w &&
            ny >= ann.y && ny <= ann.y + ann.h) {
            return ann;
        }
    }
    return null;
}

canvas.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    const pos = getMousePos(e);

    const handleHit = hitTestHandles(pos.x, pos.y);
    if (handleHit) {
        isResizing = true;
        resizeHandle = handleHit.handle;
        resizeAnn = handleHit.ann;
        return;
    }

    const boxHit = hitTestBox(pos.x, pos.y);
    if (boxHit) {
        if (boxHit.id === selectedAnnId) {
            isMoving = true;
            moveAnn = boxHit;
            const norm = canvasToNorm(pos.x, pos.y);
            moveOffset = {
                x: norm.x - boxHit.x,
                y: norm.y - boxHit.y,
            };
            return;
        }
        selectedAnnId = boxHit.id;
        render();
        renderAnnotationsList();
        return;
    }

    selectedAnnId = null;
    isDrawing = true;
    drawStart = { ...pos };
    drawCurrent = { ...pos };
    renderAnnotationsList();
});

canvas.addEventListener("mousemove", (e) => {
    const pos = getMousePos(e);

    if (isDrawing) {
        drawCurrent = { ...pos };
        render();
        return;
    }

    if (isResizing && resizeAnn) {
        const norm = canvasToNorm(pos.x, pos.y);
        const nx = norm.x;
        const ny = norm.y;
        const ann = resizeAnn;
        const right = ann.x + ann.w;
        const bottom = ann.y + ann.h;

        if (resizeHandle.includes("w")) { ann.w = right - nx; ann.x = nx; }
        if (resizeHandle.includes("e")) { ann.w = nx - ann.x; }
        if (resizeHandle.includes("n")) { ann.h = bottom - ny; ann.y = ny; }
        if (resizeHandle.includes("s")) { ann.h = ny - ann.y; }

        if (ann.w < 0) { ann.x += ann.w; ann.w = Math.abs(ann.w); }
        if (ann.h < 0) { ann.y += ann.h; ann.h = Math.abs(ann.h); }

        isDirty = true;
        render();
        return;
    }

    if (isMoving && moveAnn) {
        const norm = canvasToNorm(pos.x, pos.y);
        moveAnn.x = Math.max(0, Math.min(1 - moveAnn.w, norm.x - moveOffset.x));
        moveAnn.y = Math.max(0, Math.min(1 - moveAnn.h, norm.y - moveOffset.y));
        isDirty = true;
        render();
        return;
    }

    // Cursor updates
    const handleHit = hitTestHandles(pos.x, pos.y);
    if (handleHit) {
        const cursors = { nw: "nw-resize", ne: "ne-resize", sw: "sw-resize", se: "se-resize" };
        canvas.style.cursor = cursors[handleHit.handle];
    } else if (hitTestBox(pos.x, pos.y)?.id === selectedAnnId && selectedAnnId) {
        canvas.style.cursor = "move";
    } else {
        canvas.style.cursor = "crosshair";
    }
});

canvas.addEventListener("mouseup", (e) => {
    if (isDrawing) {
        isDrawing = false;
        const pos = getMousePos(e);

        const n1 = canvasToNorm(Math.min(drawStart.x, pos.x), Math.min(drawStart.y, pos.y));
        const n2 = canvasToNorm(Math.max(drawStart.x, pos.x), Math.max(drawStart.y, pos.y));
        const x1 = n1.x;
        const y1 = n1.y;
        const x2 = n2.x;
        const y2 = n2.y;
        const w = x2 - x1;
        const h = y2 - y1;

        if (w > 0.005 && h > 0.005) {
            const id = Math.random().toString(36).substring(2, 10);
            annotations.push({ id, class_id: selectedClassId, x: x1, y: y1, w, h });
            selectedAnnId = id;
            isDirty = true;
            renderAnnotationsList();
        }

        drawStart = null;
        drawCurrent = null;
        render();
        return;
    }

    if (isResizing) {
        isResizing = false;
        resizeHandle = null;
        resizeAnn = null;
        return;
    }

    if (isMoving) {
        isMoving = false;
        moveAnn = null;
        moveOffset = null;
        return;
    }
});

// --- Scroll zoom and pan ---

canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const pos = getMousePos(e);

    // Zoom toward mouse position
    const oldZoom = zoom;
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    zoom = Math.max(0.5, Math.min(10, zoom * delta));

    // Adjust pan so the point under the cursor stays fixed
    const ir = getImageRect();
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    panX = panX - (pos.x - cx) * (zoom / oldZoom - 1) * (oldZoom / zoom);
    panY = panY - (pos.y - cy) * (zoom / oldZoom - 1) * (oldZoom / zoom);

    render();
}, { passive: false });

// Middle-mouse or Ctrl+drag to pan
canvas.addEventListener("mousedown", (e) => {
    if (e.button === 1 || (e.button === 0 && e.ctrlKey && zoom > 1)) {
        e.preventDefault();
        isPanning = true;
        panStart = { x: e.clientX - panX, y: e.clientY - panY };
    }
}, true);

window.addEventListener("mousemove", (e) => {
    if (isPanning) {
        panX = e.clientX - panStart.x;
        panY = e.clientY - panStart.y;
        render();
    }
});

window.addEventListener("mouseup", (e) => {
    if (isPanning && (e.button === 1 || e.button === 0)) {
        isPanning = false;
        panStart = null;
    }
});

// Double-click to reset zoom
canvas.addEventListener("dblclick", () => {
    zoom = 1;
    panX = 0;
    panY = 0;
    render();
});

// --- API calls ---

async function saveAnnotations() {
    const filename = images[currentIndex];
    const resp = await fetch(`/api/annotations/${encodeURIComponent(filename)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ annotations }),
    });
    const data = await resp.json();
    isDirty = false;
    showStatus(`Saved ${data.count} annotation(s)`, "success");
}

function deleteAnnotation(id) {
    annotations = annotations.filter(a => a.id !== id);
    if (selectedAnnId === id) selectedAnnId = null;
    isDirty = true;
    render();
    renderAnnotationsList();
}

async function deleteCurrentImage() {
    const filename = images[currentIndex];
    if (!confirm(`Delete "${filename}"?\n\nThis moves the image to the deleted folder.`)) return;

    const resp = await fetch(`/api/delete-image/${encodeURIComponent(filename)}`, { method: "POST" });
    const data = await resp.json();

    if (data.error) {
        showStatus(data.error, "error");
        return;
    }

    showStatus(`Deleted: ${filename}`, "info");

    // Refresh image list and load next
    const listResp = await fetch("/api/images");
    const listData = await listResp.json();
    images = listData.images;

    if (images.length === 0) {
        showStatus("All images have been processed!", "success");
        return;
    }

    if (currentIndex >= images.length) currentIndex = images.length - 1;
    await loadImage(currentIndex);
    updateProgress();
}

async function markProgress(status) {
    const filename = images[currentIndex];
    await fetch(`/api/progress/${encodeURIComponent(filename)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
    });
    updateProgress();
}

async function updateProgress() {
    const resp = await fetch("/api/progress");
    const data = await resp.json();
    const pct = data.total > 0 ? ((data.completed / data.total) * 100).toFixed(0) : 0;
    document.getElementById("progress-fill").style.width = `${pct}%`;
    document.getElementById("progress-text").textContent =
        `${data.completed} done, ${data.skipped} skipped, ${data.deleted} deleted, ${data.remaining} remaining`;
}

async function exportYolo() {
    if (isDirty) await saveAnnotations();
    const resp = await fetch("/api/export", { method: "POST" });
    const data = await resp.json();
    showStatus(`Exported ${data.count} labeled images to YOLO format`, "success");
}

// --- Status message ---

let statusTimeout = null;
function showStatus(msg, type) {
    statusMsg.textContent = msg;
    statusMsg.className = `visible ${type}`;
    clearTimeout(statusTimeout);
    statusTimeout = setTimeout(() => { statusMsg.className = ""; }, 3000);
}

// --- Button handlers ---

document.querySelectorAll(".species-btn").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".species-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        selectedClassId = parseInt(btn.dataset.classId);

        if (selectedAnnId) {
            const ann = annotations.find(a => a.id === selectedAnnId);
            if (ann) {
                ann.class_id = selectedClassId;
                isDirty = true;
                render();
                renderAnnotationsList();
            }
        }
    });
});

document.getElementById("btn-prev").addEventListener("click", () => {
    if (currentIndex > 0) loadImage(currentIndex - 1);
});

document.getElementById("btn-next").addEventListener("click", () => {
    if (currentIndex < images.length - 1) loadImage(currentIndex + 1);
});

document.getElementById("btn-save").addEventListener("click", saveAnnotations);

document.getElementById("btn-skip").addEventListener("click", async () => {
    await markProgress("skipped");
    if (currentIndex < images.length - 1) loadImage(currentIndex + 1);
});

document.getElementById("btn-done").addEventListener("click", async () => {
    await saveAnnotations();
    await markProgress("completed");
    if (currentIndex < images.length - 1) loadImage(currentIndex + 1);
});

document.getElementById("btn-delete-image").addEventListener("click", deleteCurrentImage);

document.getElementById("btn-export").addEventListener("click", exportYolo);

// --- Keyboard shortcuts ---

document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

    // 1-9: select label
    if (e.key >= "1" && e.key <= "9") {
        const classId = parseInt(e.key) - 1;
        const btn = document.querySelector(`.species-btn[data-class-id="${classId}"]`);
        if (btn) {
            document.querySelectorAll(".species-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            selectedClassId = classId;
            if (selectedAnnId) {
                const ann = annotations.find(a => a.id === selectedAnnId);
                if (ann) {
                    ann.class_id = classId;
                    isDirty = true;
                    render();
                    renderAnnotationsList();
                }
            }
        }
        return;
    }

    if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (currentIndex > 0) loadImage(currentIndex - 1);
        return;
    }
    if (e.key === "ArrowRight") {
        e.preventDefault();
        if (currentIndex < images.length - 1) loadImage(currentIndex + 1);
        return;
    }

    if (e.key === "s" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        saveAnnotations();
        return;
    }

    if (e.key === "s" && !e.ctrlKey && !e.metaKey) {
        document.getElementById("btn-skip").click();
        return;
    }

    if (e.key === "d" && !e.ctrlKey && !e.metaKey) {
        deleteCurrentImage();
        return;
    }

    if (e.key === "Enter") {
        e.preventDefault();
        document.getElementById("btn-done").click();
        return;
    }

    if ((e.key === "Delete" || e.key === "Backspace") && selectedAnnId) {
        e.preventDefault();
        deleteAnnotation(selectedAnnId);
        return;
    }

    if (e.key === "Escape") {
        if (isDrawing) {
            isDrawing = false;
            drawStart = null;
            drawCurrent = null;
            render();
        }
        selectedAnnId = null;
        render();
        renderAnnotationsList();
        return;
    }
});

// --- Window resize ---

window.addEventListener("resize", () => {
    if (img.naturalWidth) {
        fitCanvas();
        render();
    }
});

// Auto-save on page unload
window.addEventListener("beforeunload", (e) => {
    if (isDirty) {
        saveAnnotations();
        e.preventDefault();
        e.returnValue = "";
    }
});

// --- Start ---

init();
