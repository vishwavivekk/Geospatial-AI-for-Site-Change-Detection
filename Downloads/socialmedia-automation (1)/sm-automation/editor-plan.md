# Konva.js Post Editor — Implementation Plan

## Goal

Replace the existing HTML slideshow feature with a Konva.js canvas-based post editor. The LLM generates a structured JSON layout describing a 1080x1080 social media post, which Konva renders on canvas. Users can then drag, resize, edit text, add/delete elements, and export as PNG.

## Architecture

```
Story Card → "Create Post" button → /create?topic=...
                                         │
                                         ▼
                            Fetch story data from API
                                         │
                                User clicks "Generate"
                                         │
                                         ▼
                            POST /api/generate-layout
                              { topic, text, images, category }
                                         │
                                         ▼
                            Gemini → brand.json + story text
                                         │
                                         ▼
                            Returns layout JSON (custom schema)
                                         │
                                         ▼
                            Konva create(state) → renders canvas
                                         │
                            ┌────────────┴────────────┐
                            ▼                         ▼
                      User edits               User exports PNG
                   (drag / transform /     stage.toDataURL({pixelRatio:2})
                    edit text / add /
                    delete / reorder)
```

## Research Summary

| Area | Key Finding |
|------|-------------|
| **Shape types** | Rect, Circle, Ellipse, Line, Path (SVG), Star, Ring, RegularPolygon, Text, Image, Group |
| **Image loading** | `Konva.Image.fromURL(url, callback)` or `new Image()` + `onload` |
| **Transformer** | `new Konva.Transformer()` → `.nodes([shape])`. Uses `scaleX/scaleY`. Must apply scale to dims post-transform. |
| **Text editing** | Hide Konva.Text, overlay `<textarea>` at absolute coords, sync on Enter/click-outside |
| **Drag** | Set `draggable: true` on any shape |
| **Export** | `stage.toDataURL({ pixelRatio: 2 })` → 2160x2160 PNG |
| **Serialization** | Per Konva docs: use **custom JSON schema** + `create(state)` pattern, NOT `toJSON()`/`Node.create()` |
| **Undo/redo** | History stack of `JSON.stringify(state)` snapshots |
| **Resize via Transformer** | After transform: `width *= scaleX; scaleX = 1; height *= scaleY; scaleY = 1` |

## Custom JSON Schema (LLM Output)

```json
{
  "canvas": { "width": 1080, "height": 1080, "background": "#F3F7FA" },
  "elements": [
    {
      "id": "bg-1",
      "type": "rect",
      "locked": false,
      "attrs": {
        "x": 0, "y": 0, "width": 1080, "height": 400,
        "fill": "#092240", "cornerRadius": [0, 0, 24, 24]
      }
    },
    {
      "id": "headline-1",
      "type": "text",
      "attrs": {
        "x": 540, "y": 60, "text": "NICDC Launches New Initiative",
        "fontSize": 52, "fontFamily": "Georgia, serif",
        "fontStyle": "bold", "fill": "#ffffff",
        "align": "center", "width": 900, "wrap": "word"
      }
    },
    {
      "id": "body-1",
      "type": "text",
      "attrs": {
        "x": 80, "y": 480, "text": "Story body...",
        "fontSize": 26, "fontFamily": "Inter, sans-serif",
        "fill": "#0f1419", "width": 920, "wrap": "word"
      }
    },
    {
      "id": "img-1",
      "type": "image",
      "attrs": {
        "x": 80, "y": 700, "width": 200, "height": 200,
        "src": "/images/abc123.jpg", "cornerRadius": 16
      }
    },
    {
      "id": "deco-1",
      "type": "circle",
      "attrs": {
        "x": 1000, "y": 100, "radius": 60,
        "fill": "#1565C0", "opacity": 0.15
      }
    },
    {
      "id": "path-1",
      "type": "path",
      "attrs": {
        "data": "M10,10 L100,10 L100,100 Z",
        "fill": "#E65100", "opacity": 0.1
      }
    },
    {
      "id": "line-1",
      "type": "line",
      "attrs": {
        "points": [80, 440, 1000, 440],
        "stroke": "#e1e8ed", "strokeWidth": 2
      }
    }
  ]
}
```

### Supported Types → Konva Mapping

| Schema `type` | Konva class | Key `attrs` properties |
|---------------|-------------|----------------------|
| `rect` | `Konva.Rect` | x, y, width, height, fill, stroke, strokeWidth, cornerRadius, opacity, shadowBlur, shadowColor |
| `text` | `Konva.Text` | x, y, text, fontSize, fontFamily, fontStyle, fontVariant, fill, align, width, wrap, padding, lineHeight |
| `image` | `Konva.Image` | x, y, width, height, src, cornerRadius, opacity (a loaded `<img>` element is set as `image` attr) |
| `circle` | `Konva.Circle` | x, y, radius, fill, stroke, strokeWidth, opacity |
| `ellipse` | `Konva.Ellipse` | x, y, radiusX, radiusY, fill, stroke, opacity |
| `line` | `Konva.Line` | points[], stroke, strokeWidth, closed, fill, tension |
| `path` | `Konva.Path` | data (SVG path string), fill, stroke, scaleX, scaleY |
| `star` | `Konva.Star` | x, y, numPoints, innerRadius, outerRadius, fill, stroke |
| `ring` | `Konva.Ring` | x, y, innerRadius, outerRadius, fill, stroke |
| `polygon` | `Konva.Line` (closed:true) | points[], fill, stroke, closed: true |
| `group` | `Konva.Group` | x, y, children (same element schema recursively), draggable |

## Brand JSON Files

Three files at `data/brands/`:

### `data/brands/news.json`
```json
{
  "name": "News",
  "palette": {
    "primary": "#092240",
    "accent": "#1565C0",
    "highlight": "#E65100",
    "success": "#2E7D32",
    "background": "#F3F7FA"
  },
  "fonts": { "heading": "Georgia, serif", "body": "Inter, sans-serif" },
  "logo": "/images/nicdc-logo.png",
  "tone": "authoritative, institutional, news-driven"
}
```

### `data/brands/hiring.json`
Hiring-appropriate palette (teals, greens, warm accents), "opportunity, growth" tone.

### `data/brands/events.json`
Events-appropriate palette (gold, amber, navy), "celebratory, milestone" tone.

## `/create` Page Layout

```
┌──────────────────────────────────────────────────────────┐
│  [Generate] [Export PNG] [Undo] [Redo]  [Add Element ▼] │
├───────────────────────────┬──────────────────────────────┤
│                           │  Properties                  │
│    1080×1080 Canvas       │  ┌────────────────────────┐  │
│    (scaled to fit)        │  │ Type: Rect              │  │
│                           │  │ X: 0    Y: 0           │  │
│                           │  │ W: 1080  H: 400        │  │
│                           │  │ Fill: [#092240]         │  │
│                           │  │ Corner: [0,0,24,24]    │  │
│                           │  │ Opacity: 1.0           │  │
│                           │  └────────────────────────┘  │
│                           │                              │
│                           │  Layers                      │
│                           │  ┌────────────────────────┐  │
│                           │  │  ☰ bg-1        Rect    │  │
│                           │  │  ☰ headline-1  Text    │  │
│                           │  │  ☰ body-1      Text    │  │
│                           │  │  ☰ img-1       Image   │  │
│                           │  └────────────────────────┘  │
├───────────────────────────┴──────────────────────────────┤
│  Status: Ready / Generating... / Select an element       │
└──────────────────────────────────────────────────────────┘
```

## Core JS Architecture

### State Management (Konva best practice)
```javascript
let state = {
  canvas: { width: 1080, height: 1080, background: '#F3F7FA' },
  elements: []
};

const history = [JSON.stringify(state)];
let historyStep = 0;
let selectedNodeId = null;
```

### Functions

| Function | Purpose |
|----------|---------|
| `createStage(container)` | Init Konva.Stage, Layer, Transformer. Scale 1080→display. |
| `create(state)` | Clear layer, rebuild all nodes from `state.elements`. |
| `createNode(el)` | Switch on `el.type` → return `new Konva.Rect/Text/Image/Circle/...` |
| `createImageNode(el)` | `Konva.Image.fromURL(el.attrs.src, ...)` |
| `selectNode(node)` | Attach Transformer, update properties panel, set `selectedNodeId` |
| `updateNode(node, attrs)` | `node.setAttrs(attrs)`, update `state`, push history |
| `saveHistory()` | `history = history.slice(0, historyStep+1)`; push new state |
| `undo()` / `redo()` | Traverse history stack, `create(state)` |
| `editTextNode(node)` | Hide node, overlay `<textarea>`, sync back on Enter/blur |
| `deleteSelected()` | Remove from state elements, `create(state)` |
| `addElement(type)` | Push default element to state, `create(state)` |
| `exportPNG()` | `stage.toDataURL({ pixelRatio: 2 })` → trigger download |
| `generateLayout()` | Fetch `POST /api/generate-layout` → set state → `create(state)` |

### Properties Panel

Dynamically generated based on selected element `type`:

| Property | Affects types | Input |
|----------|---------------|-------|
| X, Y | All | number inputs |
| Width, Height | Rect, Image | number inputs |
| Fill | Rect, Circle, Ellipse, Polygon, Path | color picker |
| Stroke | Rect, Circle, Ellipse, Line, Polygon | color picker |
| Stroke Width | Rect, Circle, Ellipse, Line | range/number |
| Corner Radius | Rect | number or comma-separated |
| Opacity | All | range 0-1 |
| Text | Text | textarea |
| Font Size | Text | number |
| Font Family | Text | dropdown (Inter, Georgia, Arial, etc.) |
| Font Style | Text | dropdown (normal, bold, italic) |
| Color | Text | color picker |
| Align | Text | dropdown (left, center, right) |
| Radius | Circle | number |
| Radius X/Y | Ellipse | number |
| Points | Line, Polygon | textarea (comma-separated) |
| Src | Image | text (read-only) |
| Rotation | All | range 0-360 |
| Locked | All | toggle checkbox |

## Files to Create

| # | File | Purpose |
|---|------|---------|
| 1 | `data/brands/news.json` | Brand guidelines for News category |
| 2 | `data/brands/hiring.json` | Brand guidelines for Hiring category |
| 3 | `data/brands/events.json` | Brand guidelines for Events category |
| 4 | `app/layout_generator.py` | Gemini prompt builder + JSON parser for layout generation |
| 5 | Konva editor HTML/JS in `app/main.py` | The `/create` page (~600 lines inline in a Python string) |

## Changes to `app/main.py`

### Add
- `from app.layout_generator import generate_layout`
- `LayoutRequest` pydantic model: `topic, text, images: list[str], category`
- `GET /create?topic=...` → serves the Konva editor page
- `POST /api/generate-layout` → calls `generate_layout()`, returns JSON
- Story card button: "Create Post" → links to `/create?topic=...`

### Update
- `openSlidesFromStory(topic)` → redirect to `/create?topic=...` (or replace entirely)
- Story card HTML: `btn-slides` → `btn-create-post`

### Remove
- `from app.renderer import render_post`
- `from app.slide_generator import generate_slide`
- `RenderRequest` model
- `POST /render` endpoint
- `GET /slides/generate/{n}` endpoint
- `GET /slides/generate` endpoint
- `GET /slides` endpoint
- `_slides_page()` function (all slide HTML/CSS/JS — ~140 lines)
- `openSlides(btn)` JS function
- `openSlidesFromStory(topic)` JS function (or repurpose)

## Files to Delete

| File | Reason |
|------|--------|
| `app/renderer.py` | HTML rendering replaced by Konva canvas |
| `app/templates/base_design.html` | Used only by renderer |
| `app/slide_generator.py` | Replaced by layout_generator |
| `app/templates/slide_design_prompt.txt` | Used only by slide_generator |

## Implementation Order

| Step | Description | Estimated effort |
|------|-------------|-----------------|
| 1 | Create `data/brands/news.json`, `hiring.json`, `events.json` | 15 min |
| 2 | Create `app/layout_generator.py` with prompt and Gemini integration | 45 min |
| 3 | Add `LayoutRequest` model + `POST /api/generate-layout` to `main.py` | 15 min |
| 4 | Build the `/create` page — Konva editor (canvas, toolbar, properties panel, layers) | 2-3 hrs |
| 5 | Update story card buttons, remove old slides routes and functions from `main.py` | 30 min |
| 6 | Delete old slide files (`renderer.py`, `slide_generator.py`, templates) | 5 min |
| 7 | Full test pass: generate layout, edit elements, export PNG | 30 min |

## Key Konva Syntax Reference

```javascript
// Stage
const stage = new Konva.Stage({
    container: 'canvas-container',
    width: 1080,
    height: 1080
});

// Scaling to fit viewport
const scale = Math.min(container.clientWidth / 1080, container.clientHeight / 1080);
stage.scale({ x: scale, y: scale });

// Layer
const layer = new Konva.Layer();
stage.add(layer);

// Shapes
new Konva.Rect({ x: 0, y: 0, width: 1080, height: 400, fill: '#092240', cornerRadius: [0,0,24,24] });
new Konva.Text({ x: 100, y: 100, text: 'Hello', fontSize: 32, fontFamily: 'Inter', fill: '#000', width: 900, wrap: 'word' });
new Konva.Circle({ x: 500, y: 500, radius: 50, fill: '#E65100' });
new Konva.Line({ points: [100, 100, 200, 100, 200, 200], stroke: '#000', strokeWidth: 2, closed: true, fill: '#eee' });
new Konva.Path({ data: 'M10,10 L100,10 L100,100 Z', fill: '#1565C0' });
new Konva.Ellipse({ x: 200, y: 200, radiusX: 100, radiusY: 50, fill: '#2E7D32' });
new Konva.Star({ x: 300, y: 300, numPoints: 5, innerRadius: 30, outerRadius: 60, fill: '#ff0' });
new Konva.Ring({ x: 400, y: 400, innerRadius: 40, outerRadius: 80, fill: '#f0f' });
new Konva.RegularPolygon({ x: 500, y: 500, sides: 6, radius: 50, fill: '#00f' });

// Image loading
Konva.Image.fromURL('/images/file.jpg', function(node) {
    node.setAttrs({ x: 50, y: 50, width: 200, height: 200, cornerRadius: 16 });
    layer.add(node);
});

// Transformer
const tr = new Konva.Transformer();
layer.add(tr);
tr.nodes([shape]); // attach to shape

// After resize via Transformer — apply scale to dims
shape.on('transformend', () => {
    const w = shape.width() * shape.scaleX();
    const h = shape.height() * shape.scaleY();
    shape.setAttrs({ width: w, height: h, scaleX: 1, scaleY: 1 });
    // Also update state here
});

// Text editing — double click
textNode.on('dblclick dbltap', () => {
    textNode.hide();
    tr.hide();
    const textPosition = textNode.absolutePosition();
    const stageBox = stage.container().getBoundingClientRect();
    const textarea = document.createElement('textarea');
    textarea.value = textNode.text();
    // Position, style, font matching
    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { textNode.text(textarea.value); removeTextarea(); }
        if (e.key === 'Escape') { removeTextarea(); }
    });
    // Click outside to save
});

// Export
const url = stage.toDataURL({ pixelRatio: 2 });
const link = document.createElement('a');
link.download = 'post.png';
link.href = url;
link.click();

// Select by name/id
layer.findOne('#headline-1');
layer.find('.text'); // by name (class)

// Remove all children
layer.destroyChildren();
```
