// Fish Labeling Tool — Canvas-based bounding box and polygon mask annotation

const LABELS = {};
const COLORS = {};

// Parse label data from DOM. Read the color from data-color rather than the
// swatch's inline style — the CSSOM normalizes "#e6194b" to "rgb(230, 25, 75)",
// which breaks any string math on the value.
document.querySelectorAll(".species-btn").forEach(btn => {
    const id = parseInt(btn.dataset.classId);
    LABELS[id] = btn.textContent.trim().split("\n")[0].trim();
    COLORS[id] = btn.dataset.color;
});

// --- State ---

let images = [];
let currentIndex = 0;
let annotations = [];
let selectedClassId = 0;
let selectedAnnId = null;
let isDirty = false;

// Tool mode: "polygon" | "box" | "point". Polygon is the default because
// segmentation masks are the primary annotation type for this dataset.
let toolMode = "polygon";

// Drawing state (box)
let isDrawing = false;
let drawStart = null;
let drawCurrent = null;

// Resize state (box)
let isResizing = false;
let resizeHandle = null;
let resizeAnn = null;

// Move state (box)
let isMoving = false;
let moveAnn = null;
let moveOffset = null;

// Polygon in-progress state
let polyPoints = [];        // normalized [[x, y], ...] for the polygon being drawn
let polyHoverPos = null;    // canvas-pixel position of the cursor, for rubber band

// Polygon vertex drag state
let isVertexDragging = false;
let vertexDragAnn = null;
let vertexDragIdx = -1;

// Point drag state
let isMovingPoint = false;
let movePointAnn = null;

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
const countsList = document.getElementById("counts-list");
const noCounts = document.getElementById("no-counts");
const modeHint = document.getElementById("mode-hint");
const imageCounter = document.getElementById("image-counter");
const filenameDisplay = document.getElementById("filename-display");
const statusMsg = document.getElementById("status-message");

// --- Init ---

async function init() {
    const resp = await fetch("/api/images");
    const data = await resp.json();

    // Session went away (e.g. the remembered input folder moved) — the page
    // loaded but the API can't serve it. Send the user back to Setup.
    if (data.needs_setup) {
        window.location.href = "/setup";
        return;
    }

    images = data.images;

    if (images.length === 0) {
        showStatus("No images found in input directory.", "error");
        return;
    }

    // Select first label button
    document.querySelector(".species-btn").classList.add("active");

    // Sync button state and hint text with the default tool mode
    setToolMode(toolMode);

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
        if (ann.type === "polygon") {
            drawPolygon(ann, ann.id === selectedAnnId);
        } else if (ann.type === "point") {
            drawPoint(ann, ann.id === selectedAnnId);
        } else {
            drawBox(ann, ann.id === selectedAnnId);
        }
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

    if (toolMode === "polygon" && polyPoints.length > 0) {
        drawInProgressPolygon();
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

    // Interior stays transparent so the fish underneath remains inspectable.
    // A dark under-stroke keeps the outline readable over bright water.
    ctx.strokeStyle = "rgba(0, 0, 0, 0.55)";
    ctx.lineWidth = selected ? 5 : 4;
    ctx.strokeRect(x, y, w, h);

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

function drawPolygon(ann, selected) {
    const ir = getImageRect();
    const pts = ann.points || [];
    if (pts.length < 2) return;
    const color = COLORS[ann.class_id] || "#fff";

    ctx.beginPath();
    ctx.moveTo(ir.x + pts[0][0] * ir.w, ir.y + pts[0][1] * ir.h);
    for (let i = 1; i < pts.length; i++) {
        ctx.lineTo(ir.x + pts[i][0] * ir.w, ir.y + pts[i][1] * ir.h);
    }
    ctx.closePath();

    // Interior stays transparent — see drawBox.
    ctx.strokeStyle = "rgba(0, 0, 0, 0.55)";
    ctx.lineWidth = selected ? 5 : 4;
    ctx.stroke();

    ctx.strokeStyle = color;
    ctx.lineWidth = selected ? 3 : 2;
    ctx.stroke();

    // Label at topmost vertex
    let topIdx = 0;
    for (let i = 1; i < pts.length; i++) {
        if (pts[i][1] < pts[topIdx][1]) topIdx = i;
    }
    const lx = ir.x + pts[topIdx][0] * ir.w;
    const ly = ir.y + pts[topIdx][1] * ir.h;
    const label = LABELS[ann.class_id] || `class ${ann.class_id}`;
    ctx.font = "bold 13px sans-serif";
    const textW = ctx.measureText(label).width + 8;
    ctx.fillStyle = color;
    ctx.fillRect(lx, ly - 20, textW, 20);
    ctx.fillStyle = "#fff";
    ctx.fillText(label, lx + 4, ly - 6);

    // Vertex handles when selected
    if (selected) {
        const hs = 8;
        ctx.fillStyle = "#fff";
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        for (const [nx, ny] of pts) {
            const px = ir.x + nx * ir.w;
            const py = ir.y + ny * ir.h;
            ctx.fillRect(px - hs/2, py - hs/2, hs, hs);
            ctx.strokeRect(px - hs/2, py - hs/2, hs, hs);
        }
    }
}

function drawPoint(ann, selected) {
    const ir = getImageRect();
    const px = ir.x + ann.x * ir.w;
    const py = ir.y + ann.y * ir.h;
    const color = COLORS[ann.class_id] || "#fff";
    const r = selected ? 9 : 7;
    const tick = r + 5;

    // Crosshair arms, gapped at the center so the marked fish stays visible.
    ctx.strokeStyle = "rgba(0, 0, 0, 0.55)";
    ctx.lineWidth = 3.5;
    for (let pass = 0; pass < 2; pass++) {
        ctx.beginPath();
        ctx.moveTo(px - tick, py); ctx.lineTo(px - r + 1, py);
        ctx.moveTo(px + r - 1, py); ctx.lineTo(px + tick, py);
        ctx.moveTo(px, py - tick); ctx.lineTo(px, py - r + 1);
        ctx.moveTo(px, py + r - 1); ctx.lineTo(px, py + tick);
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(px, py, r, 0, Math.PI * 2);
        ctx.stroke();

        // Second pass draws the colored marker over the dark halo.
        ctx.strokeStyle = color;
        ctx.lineWidth = selected ? 2.5 : 2;
    }

    // Small centre dot marks the exact position without covering the subject.
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(px, py, 1.5, 0, Math.PI * 2);
    ctx.fill();

    // Only the selected point gets a name chip — a dense count image would be
    // unreadable with a label on every marker.
    if (selected) {
        const label = LABELS[ann.class_id] || `class ${ann.class_id}`;
        ctx.font = "bold 13px sans-serif";
        const textW = ctx.measureText(label).width + 8;
        ctx.fillStyle = color;
        ctx.fillRect(px + tick + 2, py - 10, textW, 20);
        ctx.fillStyle = "#fff";
        ctx.fillText(label, px + tick + 6, py + 4);
    }
}

function drawInProgressPolygon() {
    const ir = getImageRect();
    const color = COLORS[selectedClassId];

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 3]);
    ctx.beginPath();
    for (let i = 0; i < polyPoints.length; i++) {
        const [nx, ny] = polyPoints[i];
        const px = ir.x + nx * ir.w;
        const py = ir.y + ny * ir.h;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    if (polyHoverPos) ctx.lineTo(polyHoverPos.x, polyHoverPos.y);
    ctx.stroke();
    ctx.setLineDash([]);

    // Point markers
    ctx.fillStyle = color;
    for (const [nx, ny] of polyPoints) {
        const px = ir.x + nx * ir.w;
        const py = ir.y + ny * ir.h;
        ctx.beginPath();
        ctx.arc(px, py, 4, 0, Math.PI * 2);
        ctx.fill();
    }
}

// --- Annotations list ---

const TYPE_SUFFIX = { polygon: " (mask)", point: " (point)" };

function renderCounts() {
    countsList.innerHTML = "";

    const tally = new Map();
    for (const ann of annotations) {
        tally.set(ann.class_id, (tally.get(ann.class_id) || 0) + 1);
    }

    noCounts.style.display = tally.size ? "none" : "block";

    for (const classId of [...tally.keys()].sort((a, b) => a - b)) {
        const li = document.createElement("li");

        const swatch = document.createElement("span");
        swatch.className = "color-swatch";
        swatch.style.background = COLORS[classId] || "#fff";
        li.appendChild(swatch);

        const name = document.createElement("span");
        name.textContent = LABELS[classId] || `class ${classId}`;
        li.appendChild(name);

        const n = document.createElement("span");
        n.className = "count-value";
        n.textContent = tally.get(classId);
        li.appendChild(n);

        countsList.appendChild(li);
    }
}

function renderAnnotationsList() {
    annotationsList.innerHTML = "";
    noAnnotations.style.display = annotations.length ? "none" : "block";
    renderCounts();

    for (const ann of annotations) {
        const li = document.createElement("li");
        if (ann.id === selectedAnnId) li.classList.add("selected");

        const swatch = document.createElement("span");
        swatch.className = "color-swatch";
        swatch.style.background = COLORS[ann.class_id] || "#fff";
        li.appendChild(swatch);

        const text = document.createElement("span");
        const name = LABELS[ann.class_id] || `class ${ann.class_id}`;
        text.textContent = name + (TYPE_SUFFIX[ann.type] || "");
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
    // Only boxes have corner handles; points and polygons have no w/h.
    if (ann.type === "polygon" || ann.type === "point") return null;

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
        if (ann.type === "polygon" || ann.type === "point") continue;
        if (nx >= ann.x && nx <= ann.x + ann.w &&
            ny >= ann.y && ny <= ann.y + ann.h) {
            return ann;
        }
    }
    return null;
}

function pointInPolygon(nx, ny, pts) {
    let inside = false;
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
        const xi = pts[i][0], yi = pts[i][1];
        const xj = pts[j][0], yj = pts[j][1];
        const intersect = ((yi > ny) !== (yj > ny)) &&
            (nx < (xj - xi) * (ny - yi) / (yj - yi + 1e-12) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}

function hitTestPolygon(px, py) {
    const n = canvasToNorm(px, py);
    for (let i = annotations.length - 1; i >= 0; i--) {
        const ann = annotations[i];
        if (ann.type !== "polygon") continue;
        if (pointInPolygon(n.x, n.y, ann.points || [])) return ann;
    }
    return null;
}

function hitTestPoint(px, py) {
    const ir = getImageRect();
    const r = 12;
    for (let i = annotations.length - 1; i >= 0; i--) {
        const ann = annotations[i];
        if (ann.type !== "point") continue;
        const cx = ir.x + ann.x * ir.w;
        const cy = ir.y + ann.y * ir.h;
        if (Math.hypot(px - cx, py - cy) < r) return ann;
    }
    return null;
}

function hitTestVertex(px, py) {
    if (!selectedAnnId) return null;
    const ann = annotations.find(a => a.id === selectedAnnId);
    if (!ann || ann.type !== "polygon") return null;

    const ir = getImageRect();
    const r = 10;
    for (let i = 0; i < ann.points.length; i++) {
        const [nx, ny] = ann.points[i];
        const cx = ir.x + nx * ir.w;
        const cy = ir.y + ny * ir.h;
        if (Math.abs(px - cx) < r && Math.abs(py - cy) < r) {
            return { ann, idx: i };
        }
    }
    return null;
}

canvas.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    // Ctrl+drag pan handler runs in its own capture-phase listener below.
    if (e.ctrlKey && zoom > 1) return;
    const pos = getMousePos(e);

    // Vertex drag for selected polygon
    const vertexHit = hitTestVertex(pos.x, pos.y);
    if (vertexHit) {
        isVertexDragging = true;
        vertexDragAnn = vertexHit.ann;
        vertexDragIdx = vertexHit.idx;
        return;
    }

    const handleHit = hitTestHandles(pos.x, pos.y);
    if (handleHit) {
        isResizing = true;
        resizeHandle = handleHit.handle;
        resizeAnn = handleHit.ann;
        return;
    }

    // Points are small, so test them before the larger shapes — otherwise a
    // point sitting inside a box or mask could never be selected.
    const pointHit = hitTestPoint(pos.x, pos.y);
    if (pointHit) {
        if (pointHit.id === selectedAnnId) {
            isMovingPoint = true;
            movePointAnn = pointHit;
            return;
        }
        selectedAnnId = pointHit.id;
        render();
        renderAnnotationsList();
        return;
    }

    // In point mode, clicking a mask or box would otherwise select it instead
    // of dropping a count marker inside it. Those shapes stay selectable from
    // the annotations list.
    if (toolMode !== "point") {
        // Click on an existing polygon selects it
        const polyHit = hitTestPolygon(pos.x, pos.y);
        if (polyHit) {
            selectedAnnId = polyHit.id;
            render();
            renderAnnotationsList();
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
    }

    // Empty area — tool-dependent behavior
    if (toolMode === "point") {
        const norm = canvasToNorm(pos.x, pos.y);
        if (norm.x < 0 || norm.x > 1 || norm.y < 0 || norm.y > 1) return;
        const id = Math.random().toString(36).substring(2, 10);
        annotations.push({
            id,
            class_id: selectedClassId,
            type: "point",
            x: norm.x,
            y: norm.y,
        });
        selectedAnnId = id;
        isDirty = true;
        render();
        renderAnnotationsList();
        return;
    }

    if (toolMode === "polygon") {
        const norm = canvasToNorm(pos.x, pos.y);
        // Only add the point if it's within the image bounds
        if (norm.x < 0 || norm.x > 1 || norm.y < 0 || norm.y > 1) return;
        polyPoints.push([norm.x, norm.y]);
        selectedAnnId = null;
        render();
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

    if (isVertexDragging && vertexDragAnn) {
        const norm = canvasToNorm(pos.x, pos.y);
        vertexDragAnn.points[vertexDragIdx] = [
            Math.max(0, Math.min(1, norm.x)),
            Math.max(0, Math.min(1, norm.y)),
        ];
        isDirty = true;
        render();
        return;
    }

    if (isMovingPoint && movePointAnn) {
        const norm = canvasToNorm(pos.x, pos.y);
        movePointAnn.x = Math.max(0, Math.min(1, norm.x));
        movePointAnn.y = Math.max(0, Math.min(1, norm.y));
        isDirty = true;
        render();
        return;
    }

    if (toolMode === "polygon" && polyPoints.length > 0) {
        polyHoverPos = { ...pos };
        render();
    }

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
    const vertexHit = hitTestVertex(pos.x, pos.y);
    if (hitTestPoint(pos.x, pos.y)) {
        canvas.style.cursor = "pointer";
    } else if (vertexHit) {
        canvas.style.cursor = "grab";
    } else if (handleHit) {
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

    if (isVertexDragging) {
        isVertexDragging = false;
        vertexDragAnn = null;
        vertexDragIdx = -1;
        return;
    }

    if (isMovingPoint) {
        isMovingPoint = false;
        movePointAnn = null;
        return;
    }
});

function finalizePolygon() {
    if (polyPoints.length < 3) {
        polyPoints = [];
        polyHoverPos = null;
        render();
        return;
    }
    const id = Math.random().toString(36).substring(2, 10);
    annotations.push({
        id,
        class_id: selectedClassId,
        type: "polygon",
        points: polyPoints.slice(),
    });
    selectedAnnId = id;
    polyPoints = [];
    polyHoverPos = null;
    isDirty = true;
    render();
    renderAnnotationsList();
}

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

// Double-click: finalize polygon if drawing one, else reset zoom
canvas.addEventListener("dblclick", () => {
    if (toolMode === "polygon" && polyPoints.length > 0) {
        // Drop the duplicate point added by the preceding single-click
        if (polyPoints.length >= 2) polyPoints.pop();
        finalizePolygon();
        return;
    }
    // In point mode a double-click is two deliberate counts, not a request to
    // reset the view — resetting zoom mid-count would be disruptive.
    if (toolMode === "point") return;
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
    const counted = Object.entries(data.point_totals || {})
        .filter(([, n]) => n > 0)
        .map(([name, n]) => `${name}: ${n}`)
        .join(", ");
    const suffix = counted ? ` — points counted (${counted})` : "";
    showStatus(`Exported ${data.count} labeled images to YOLO format${suffix}`, "success");
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

const MODE_HINTS = {
    polygon: "Click to add points around the fish; double-click or Enter to close the mask.",
    box: "Drag a box around the fish. Drag corners to resize, drag the middle to move.",
    point: "Click each fish once to count it. Drag a marker to nudge it, Del to remove.",
};

function setToolMode(mode) {
    if (!(mode in MODE_HINTS)) return;
    // Cancel any in-progress polygon when switching away
    if (toolMode === "polygon" && mode !== "polygon") {
        polyPoints = [];
        polyHoverPos = null;
    }
    toolMode = mode;
    document.querySelectorAll(".mode-btn").forEach(b => {
        b.classList.toggle("active", b.dataset.mode === mode);
    });
    if (modeHint) modeHint.textContent = MODE_HINTS[mode];
    render();
}

document.querySelectorAll(".mode-btn").forEach(btn => {
    btn.addEventListener("click", () => setToolMode(btn.dataset.mode));
});

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

    if (e.key === "b" && !e.ctrlKey && !e.metaKey) {
        setToolMode("box");
        return;
    }
    if (e.key === "p" && !e.ctrlKey && !e.metaKey) {
        setToolMode("polygon");
        return;
    }
    if (e.key === "c" && !e.ctrlKey && !e.metaKey) {
        setToolMode("point");
        return;
    }

    if (e.key === "Enter") {
        e.preventDefault();
        if (toolMode === "polygon" && polyPoints.length > 0) {
            finalizePolygon();
            return;
        }
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
        }
        if (polyPoints.length > 0) {
            polyPoints = [];
            polyHoverPos = null;
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
