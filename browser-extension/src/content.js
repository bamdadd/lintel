/* Lintel Browser Extension — Content Script (Element Selector) */

let selecting = false;
let hoveredElement = null;

// Listen for selection requests from popup
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "START_SELECTION") {
    startSelection();
  }
});

function startSelection() {
  selecting = true;
  document.body.style.cursor = "crosshair";
  document.addEventListener("mouseover", onMouseOver, true);
  document.addEventListener("mouseout", onMouseOut, true);
  document.addEventListener("click", onClick, true);
  document.addEventListener("keydown", onKeyDown, true);
}

function stopSelection() {
  selecting = false;
  document.body.style.cursor = "";
  document.removeEventListener("mouseover", onMouseOver, true);
  document.removeEventListener("mouseout", onMouseOut, true);
  document.removeEventListener("click", onClick, true);
  document.removeEventListener("keydown", onKeyDown, true);
  removeHighlight();
}

function onMouseOver(e) {
  if (!selecting) return;
  e.stopPropagation();
  removeHighlight();
  hoveredElement = e.target;
  hoveredElement.classList.add("lintel-highlight");
}

function onMouseOut(e) {
  if (!selecting) return;
  e.stopPropagation();
  removeHighlight();
}

function onClick(e) {
  if (!selecting) return;
  e.preventDefault();
  e.stopPropagation();

  const el = e.target;
  removeHighlight();
  stopSelection();

  const payload = {
    tagName: el.tagName.toLowerCase(),
    selector: buildSelector(el),
    componentPath: getReactComponentPath(el),
    pageUrl: window.location.href,
    outerHTML: el.outerHTML.slice(0, 2000),
    rect: el.getBoundingClientRect().toJSON(),
  };

  chrome.runtime.sendMessage({ type: "ELEMENT_SELECTED", payload });
}

function onKeyDown(e) {
  if (e.key === "Escape") {
    stopSelection();
  }
}

function removeHighlight() {
  if (hoveredElement) {
    hoveredElement.classList.remove("lintel-highlight");
    hoveredElement = null;
  }
}

/**
 * Build a CSS selector path for the element.
 */
function buildSelector(el) {
  const parts = [];
  let current = el;
  while (current && current !== document.body) {
    let part = current.tagName.toLowerCase();
    if (current.id) {
      part += `#${current.id}`;
      parts.unshift(part);
      break;
    }
    if (current.className && typeof current.className === "string") {
      const classes = current.className.trim().split(/\s+/).filter(
        (c) => !c.startsWith("lintel-")
      );
      if (classes.length > 0) {
        part += `.${classes.slice(0, 2).join(".")}`;
      }
    }
    // Add nth-child for disambiguation
    const parent = current.parentElement;
    if (parent) {
      const siblings = Array.from(parent.children).filter(
        (s) => s.tagName === current.tagName
      );
      if (siblings.length > 1) {
        const idx = siblings.indexOf(current) + 1;
        part += `:nth-child(${idx})`;
      }
    }
    parts.unshift(part);
    current = current.parentElement;
  }
  return parts.join(" > ");
}

/**
 * Attempt to find the React component name by traversing fiber nodes.
 * Returns the component file path if available via _debugSource, or
 * the component display name chain.
 */
function getReactComponentPath(el) {
  // Try React fiber key (React 16+)
  const fiberKey = Object.keys(el).find(
    (k) => k.startsWith("__reactFiber$") || k.startsWith("__reactInternalInstance$")
  );
  if (!fiberKey) return "";

  let fiber = el[fiberKey];
  const names = [];

  while (fiber) {
    if (fiber._debugSource) {
      return fiber._debugSource.fileName || "";
    }
    if (fiber.type && typeof fiber.type === "function") {
      const name = fiber.type.displayName || fiber.type.name;
      if (name && !names.includes(name)) {
        names.push(name);
      }
    }
    fiber = fiber.return;
  }

  return names.join(" > ");
}
