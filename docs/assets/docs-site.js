const state = {
  manifest: null,
  documents: [],
  filteredDocuments: [],
  activeDocument: null,
  activeSections: [],
  focusMode: false,
  activeMapCategory: "",
};

const elements = {
  libraryGroups: document.getElementById("library-groups"),
  homeView: document.getElementById("home-view"),
  docView: document.getElementById("doc-view"),
  featuredGrid: document.getElementById("featured-grid"),
  search: document.getElementById("doc-search"),
  focusToggle: document.getElementById("focus-toggle"),
  metricDocCount: document.getElementById("metric-doc-count"),
  metricCategoryCount: document.getElementById("metric-category-count"),
  constellation: document.getElementById("doc-constellation"),
  readingProgress: document.getElementById("reading-progress"),
  articleStage: document.getElementById("article-stage"),
  sectionNav: document.getElementById("section-nav"),
  jumpListContainer: document.getElementById("jump-list-container"),
  docCategory: document.getElementById("doc-category"),
  docTitle: document.getElementById("doc-title"),
  docSummary: document.getElementById("doc-summary"),
  docPathChip: document.getElementById("doc-path-chip"),
  docSectionChip: document.getElementById("doc-section-chip"),
  docReadtimeChip: document.getElementById("doc-readtime-chip"),
  rawDocLink: document.getElementById("raw-doc-link"),
  backHome: document.getElementById("back-home"),
};

function setText(node, value) {
  if (node) {
    node.textContent = value;
  }
}

function setHtml(node, value) {
  if (node) {
    node.innerHTML = value;
  }
}

function setHref(node, value) {
  if (node) {
    node.href = value;
  }
}

function documentUrl(path) {
  const url = new URL(window.location.href);
  url.searchParams.set("doc", path);
  return `${url.pathname}${url.search}${url.hash}`;
}

function toggleHidden(node, hidden) {
  if (node) {
    node.classList.toggle("hidden", Boolean(hidden));
  }
}

function setReaderMode(enabled) {
  document.body.classList.toggle("reader-mode", Boolean(enabled));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function slugify(text) {
  return String(text || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

function applyInlineFormatting(text) {
  let value = escapeHtml(text);
  value = value.replace(/`([^`]+)`/g, "<code>$1</code>");
  value = value.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  value = value.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  value = value.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  return value;
}

function markdownToHtml(markdown) {
  const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
  const html = [];
  const sections = [];
  let paragraph = [];
  let listItems = [];
  let orderedListItems = [];
  let blockquote = [];
  let inCode = false;
  let codeLines = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p class="reveal">${applyInlineFormatting(paragraph.join(" "))}</p>`);
    paragraph = [];
  };

  const flushList = () => {
    if (!listItems.length) return;
    html.push(`<ul class="reveal">${listItems.map((item) => `<li>${applyInlineFormatting(item)}</li>`).join("")}</ul>`);
    listItems = [];
  };

  const flushOrderedList = () => {
    if (!orderedListItems.length) return;
    html.push(`<ol class="reveal">${orderedListItems.map((item) => `<li>${applyInlineFormatting(item)}</li>`).join("")}</ol>`);
    orderedListItems = [];
  };

  const flushBlockquote = () => {
    if (!blockquote.length) return;
    html.push(`<blockquote class="reveal">${blockquote.map((line) => `<p>${applyInlineFormatting(line)}</p>`).join("")}</blockquote>`);
    blockquote = [];
  };

  const flushCode = () => {
    if (!codeLines.length) return;
    html.push(`<pre class="reveal"><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    codeLines = [];
  };

  const flushAll = () => {
    flushParagraph();
    flushList();
    flushOrderedList();
    flushBlockquote();
  };

  lines.forEach((line) => {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        flushCode();
        inCode = false;
      } else {
        flushAll();
        inCode = true;
      }
      return;
    }

    if (inCode) {
      codeLines.push(line);
      return;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      flushAll();
      const level = headingMatch[1].length;
      const text = headingMatch[2].trim();
      const id = slugify(text);
      html.push(`<h${level} id="${id}" class="reveal">${applyInlineFormatting(text)}</h${level}>`);
      if (level <= 3) {
        sections.push({ level, title: text, id });
      }
      return;
    }

    if (/^\s*---\s*$/.test(line)) {
      flushAll();
      html.push('<hr class="reveal" />');
      return;
    }

    const unorderedMatch = line.match(/^\s*-\s+(.*)$/);
    if (unorderedMatch) {
      flushParagraph();
      flushOrderedList();
      flushBlockquote();
      listItems.push(unorderedMatch[1].trim());
      return;
    }

    const orderedMatch = line.match(/^\s*\d+\.\s+(.*)$/);
    if (orderedMatch) {
      flushParagraph();
      flushList();
      flushBlockquote();
      orderedListItems.push(orderedMatch[1].trim());
      return;
    }

    const blockquoteMatch = line.match(/^\s*>\s?(.*)$/);
    if (blockquoteMatch) {
      flushParagraph();
      flushList();
      flushOrderedList();
      blockquote.push(blockquoteMatch[1].trim());
      return;
    }

    if (!line.trim()) {
      flushAll();
      return;
    }

    paragraph.push(line.trim());
  });

  if (inCode) {
    flushCode();
  }
  flushAll();
  return { html: html.join("\n"), sections };
}

function groupByCategory(documents) {
  return documents.reduce((acc, doc) => {
    const key = doc.category || "Other";
    if (!acc[key]) acc[key] = [];
    acc[key].push(doc);
    return acc;
  }, {});
}

function sortedCategoryEntries(documents) {
  return Object.entries(groupByCategory(documents)).sort(([left], [right]) => left.localeCompare(right));
}

function readTimeFromMarkdown(markdown) {
  const words = String(markdown || "").trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 220));
}

function buildLibrary() {
  if (!elements.libraryGroups) return;
  elements.libraryGroups.innerHTML = "";
  const groups = groupByCategory(state.filteredDocuments);
  const cardTemplate = document.getElementById("library-card-template");
  Object.entries(groups).forEach(([category, docs]) => {
    const group = document.createElement("section");
    group.className = "library-group";
    group.innerHTML = `<div class="group-title">${escapeHtml(category)}</div>`;

    docs.forEach((doc) => {
      const button = cardTemplate?.content?.firstElementChild
        ? cardTemplate.content.firstElementChild.cloneNode(true)
        : document.createElement("a");
      if (!button.classList.contains("library-card")) {
        button.className = "library-card";
        button.href = "#";
        button.innerHTML =
          '<span class="library-card-category"></span><strong class="library-card-title"></strong><span class="library-card-summary"></span>';
      }
      setText(button.querySelector(".library-card-category"), doc.category);
      setText(button.querySelector(".library-card-title"), doc.title);
      setText(button.querySelector(".library-card-summary"), doc.summary || "");
      button.dataset.path = doc.path;
      button.href = documentUrl(doc.path);
      if (state.activeDocument && state.activeDocument.path === doc.path) {
        button.classList.add("active");
      }
      button.addEventListener("click", (event) => {
        event.preventDefault();
        safeOpenDocument(doc.path);
      });
      group.appendChild(button);
    });
    elements.libraryGroups.appendChild(group);
  });
}

function buildFeatured() {
  if (!elements.featuredGrid) return;
  elements.featuredGrid.innerHTML = "";
  state.documents.slice(0, 6).forEach((doc) => {
    const card = document.createElement("a");
    card.className = "featured-card";
    card.href = documentUrl(doc.path);
    card.innerHTML = `
      <p class="eyebrow">${escapeHtml(doc.category)}</p>
      <h4>${escapeHtml(doc.title)}</h4>
      <p>${escapeHtml(doc.summary || "")}</p>
    `;
    card.addEventListener("click", (event) => {
      event.preventDefault();
      safeOpenDocument(doc.path);
    });
    elements.featuredGrid.appendChild(card);
  });
}

function polarPosition(index, total, radiusX, radiusY, centerX, centerY) {
  const angle = (Math.PI * 2 * index) / Math.max(total, 1) - Math.PI / 2;
  return {
    x: centerX + Math.cos(angle) * radiusX,
    y: centerY + Math.sin(angle) * radiusY,
  };
}

function renderConstellation() {
  if (!elements.constellation) return;
  elements.constellation.innerHTML = "";
  const categoryEntries = sortedCategoryEntries(state.documents);
  if (!categoryEntries.length) {
    return;
  }
  if (!state.activeMapCategory || !categoryEntries.some(([category]) => category === state.activeMapCategory)) {
    state.activeMapCategory = categoryEntries[0][0];
  }
  const activeCategoryEntry = categoryEntries.find(([category]) => category === state.activeMapCategory) || categoryEntries[0];
  const activeCategory = activeCategoryEntry[0];
  const activeDocs = activeCategoryEntry[1];
  const activeCategoryIndex = categoryEntries.findIndex(([category]) => category === activeCategory);
  const width = elements.constellation.clientWidth || 600;
  const height = 380;
  const centerX = width / 2;
  const centerY = height / 2;
  const categoryRadiusX = Math.max(128, width * 0.36);
  const categoryRadiusY = 138;
  const activeCategoryPosition = polarPosition(
    activeCategoryIndex,
    categoryEntries.length,
    categoryRadiusX,
    categoryRadiusY,
    centerX,
    centerY
  );
  const fileRadiusX = Math.max(82, width * 0.16);
  const fileRadiusY = 86;

  const center = document.createElement("div");
  center.className = "constellation-center";
  center.innerHTML = `
    <span class="constellation-center-label">Layer 1</span>
    <strong>Choose a folder</strong>
    <span>Then inspect its files.</span>
  `;
  elements.constellation.appendChild(center);

  categoryEntries.forEach(([category], index) => {
    const { x, y } = polarPosition(index, categoryEntries.length, categoryRadiusX, categoryRadiusY, centerX, centerY);
    const dx = x - centerX;
    const dy = y - centerY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const angle = (Math.atan2(dy, dx) * 180) / Math.PI;

    const line = document.createElement("div");
    line.className = "constellation-line constellation-line-category";
    line.style.width = `${distance}px`;
    line.style.transform = `translate(0, 0) rotate(${angle}deg)`;
    elements.constellation.appendChild(line);

    const node = document.createElement("button");
    node.className = `constellation-node constellation-category-node${category === activeCategory ? " active" : ""}`;
    node.type = "button";
    node.style.left = `${x}px`;
    node.style.top = `${y}px`;
    node.style.transform = "translate(-50%, -50%)";
    node.innerHTML = `
      <span class="constellation-node-label">${escapeHtml(category)}</span>
      <span class="constellation-node-meta">${(groupByCategory(state.documents)[category] || []).length} doc${(groupByCategory(state.documents)[category] || []).length === 1 ? "" : "s"}</span>
    `;
    node.addEventListener("click", () => {
      state.activeMapCategory = category;
      renderConstellation();
    });
    elements.constellation.appendChild(node);
  });

  activeDocs.slice(0, 8).forEach((doc, index) => {
    const { x, y } = polarPosition(
      index,
      activeDocs.length,
      fileRadiusX,
      fileRadiusY,
      activeCategoryPosition.x,
      activeCategoryPosition.y
    );
    const dx = x - activeCategoryPosition.x;
    const dy = y - activeCategoryPosition.y;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const angle = (Math.atan2(dy, dx) * 180) / Math.PI;

    const line = document.createElement("div");
    line.className = "constellation-line constellation-line-file";
    line.style.width = `${distance}px`;
    line.style.transform = `translate(0, 0) rotate(${angle}deg)`;
    elements.constellation.appendChild(line);

    const node = document.createElement("a");
    node.className = `constellation-node constellation-file-node${state.activeDocument && state.activeDocument.path === doc.path ? " active" : ""}`;
    node.href = documentUrl(doc.path);
    node.style.left = `${x}px`;
    node.style.top = `${y}px`;
    node.style.transform = "translate(-50%, -50%)";
    node.innerHTML = `
      <span class="constellation-node-label">${escapeHtml(doc.title)}</span>
      <span class="constellation-node-meta">${escapeHtml(doc.path.split("/").pop() || doc.path)}</span>
    `;
    node.addEventListener("click", (event) => {
      event.preventDefault();
      safeOpenDocument(doc.path);
    });
    elements.constellation.appendChild(node);
  });

  const activeCategorySummary = document.createElement("div");
  activeCategorySummary.className = "constellation-category-summary";
  activeCategorySummary.innerHTML = `
    <span class="constellation-summary-label">Layer 2</span>
    <strong>${escapeHtml(activeCategory)}</strong>
    <span>${activeDocs.length} file${activeDocs.length === 1 ? "" : "s"} available in this folder</span>
  `;
  elements.constellation.appendChild(activeCategorySummary);
}

function renderSectionNav(sections) {
  if (!elements.sectionNav) return;
  elements.sectionNav.innerHTML = "";
  if (!sections.length) {
    const note = document.createElement("p");
    note.className = "helper-copy";
    note.textContent = "Headings will appear here when the current document exposes a jump list.";
    elements.sectionNav.appendChild(note);
    return;
  }
  sections.forEach((section) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = section.title;
    button.dataset.target = section.id;
    button.style.paddingLeft = `${0.9 + (section.level - 1) * 0.55}rem`;
    button.addEventListener("click", () => jumpToSection(section.id));
    elements.sectionNav.appendChild(button);
  });
}

function jumpToSection(id) {
  const target = document.getElementById(id);
  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function updateSectionHighlight() {
  if (!elements.sectionNav) return;
  const headings = state.activeSections
    .map((section) => ({ section, node: document.getElementById(section.id) }))
    .filter((entry) => entry.node);

  let activeId = "";
  headings.forEach((entry) => {
    const rect = entry.node.getBoundingClientRect();
    if (rect.top <= 140) {
      activeId = entry.section.id;
    }
  });

  elements.sectionNav.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset.target === activeId);
  });

  const activeButton = activeId
    ? elements.sectionNav.querySelector(`button[data-target="${activeId}"]`)
    : null;
  if (activeButton && elements.jumpListContainer) {
    activeButton.scrollIntoView({ block: "nearest" });
  }
}

function updateReadingProgress() {
  const doc = document.documentElement;
  const scrollable = doc.scrollHeight - window.innerHeight;
  const progress = scrollable > 0 ? (window.scrollY / scrollable) * 100 : 0;
  if (elements.readingProgress) {
    elements.readingProgress.style.width = `${Math.max(0, Math.min(100, progress))}%`;
  }
  updateSectionHighlight();
}

function observeArticleReveals() {
  if (!elements.articleStage || typeof IntersectionObserver === "undefined") return;
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
        }
      });
    },
    { threshold: 0.08 }
  );

  elements.articleStage.querySelectorAll(".reveal").forEach((node) => observer.observe(node));
}

async function openDocument(path) {
  const doc = state.documents.find((item) => item.path === path);
  if (!doc) return;
  if (!elements.homeView || !elements.docView || !elements.articleStage) {
    throw new Error("Documentation reader shell is incomplete. Required reader elements are missing.");
  }
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load markdown: ${path}`);
  }
  const markdown = await response.text();
  const rendered = markdownToHtml(markdown);

  state.activeDocument = doc;
  state.activeMapCategory = doc.category || state.activeMapCategory;
  state.activeSections = rendered.sections;
  setReaderMode(true);

  toggleHidden(elements.homeView, true);
  toggleHidden(elements.docView, false);
  setText(elements.docCategory, doc.category);
  setText(elements.docTitle, doc.title);
  setText(elements.docSummary, doc.summary || "");
  setText(elements.docPathChip, doc.path);
  setText(elements.docSectionChip, `${rendered.sections.length} sections`);
  setText(elements.docReadtimeChip, `${readTimeFromMarkdown(markdown)} min read`);
  setHref(elements.rawDocLink, doc.path);
  elements.articleStage.innerHTML = rendered.html;

  renderSectionNav(rendered.sections);
  buildLibrary();
  renderConstellation();
  observeArticleReveals();
  if (elements.jumpListContainer) {
    elements.jumpListContainer.scrollTop = 0;
  }

  window.history.replaceState({}, "", documentUrl(path));
  window.scrollTo({ top: 0, behavior: "auto" });
  updateReadingProgress();
}

function showDocumentLoadError(path, error) {
  const message = error?.message || `Unknown error while loading ${path}`;
  console.error("Discovery Intelligence docs portal failed to open document.", path, error);

  if (!elements.homeView || !elements.docView || !elements.articleStage) {
    return;
  }

  setReaderMode(true);
  toggleHidden(elements.homeView, true);
  toggleHidden(elements.docView, false);
  setText(elements.docCategory, "Document load error");
  setText(elements.docTitle, state.activeDocument?.title || path);
  setText(elements.docSummary, "The portal could not render this markdown file. You can still open the raw markdown directly.");
  setText(elements.docPathChip, path);
  setText(elements.docSectionChip, "0 sections");
  setText(elements.docReadtimeChip, "Load failed");
  setHref(elements.rawDocLink, path);
  setHtml(
    elements.articleStage,
    `
    <section class="hero-card">
      <div class="hero-copy">
        <p class="eyebrow">Document load error</p>
        <h2>We could not open this article.</h2>
        <p>${escapeHtml(message)}</p>
      </div>
    </section>
  `
  );
  renderSectionNav([]);
  if (elements.jumpListContainer) {
    elements.jumpListContainer.scrollTop = 0;
  }
}

async function safeOpenDocument(path) {
  try {
    await openDocument(path);
  } catch (error) {
    showDocumentLoadError(path, error);
  }
}

function showHome() {
  state.activeDocument = null;
  state.activeSections = [];
  setReaderMode(false);
  toggleHidden(elements.docView, true);
  toggleHidden(elements.homeView, false);
  const url = new URL(window.location.href);
  url.searchParams.delete("doc");
  window.history.replaceState({}, "", url);
  buildLibrary();
  renderConstellation();
}

function filterDocuments(query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) {
    state.filteredDocuments = [...state.documents];
  } else {
    state.filteredDocuments = state.documents.filter((doc) =>
      [doc.title, doc.category, doc.summary, doc.path].some((value) => String(value || "").toLowerCase().includes(needle))
    );
  }
  buildLibrary();
}

async function initialize() {
  const response = await fetch("./assets/docs-manifest.json");
  if (!response.ok) {
    throw new Error("Failed to load docs manifest.");
  }
  state.manifest = await response.json();
  state.documents = state.manifest.documents || [];
  state.filteredDocuments = [...state.documents];

  setText(elements.metricDocCount, String(state.documents.length));
  setText(elements.metricCategoryCount, String(new Set(state.documents.map((doc) => doc.category)).size));

  buildLibrary();
  buildFeatured();
  renderConstellation();
  setReaderMode(false);

  const requested = new URL(window.location.href).searchParams.get("doc");
  if (requested) {
    await safeOpenDocument(requested);
  }
}

if (elements.search) {
  elements.search.addEventListener("input", (event) => {
    filterDocuments(event.target.value);
  });
}

if (elements.focusToggle) {
  elements.focusToggle.addEventListener("click", () => {
    state.focusMode = !state.focusMode;
    document.body.classList.toggle("focus-mode", state.focusMode);
    setText(elements.focusToggle, state.focusMode ? "Exit focus mode" : "Focus mode");
  });
}

if (elements.backHome) {
  elements.backHome.addEventListener("click", showHome);
}
window.addEventListener("scroll", updateReadingProgress, { passive: true });
window.addEventListener("resize", () => {
  renderConstellation();
});

initialize().catch((error) => {
  setHtml(
    elements.homeView,
    `
    <section class="hero-card">
      <div class="hero-copy">
        <p class="eyebrow">Portal load error</p>
        <h2>Documentation portal could not load.</h2>
        <p>${escapeHtml(error?.message || "Unknown error")}</p>
      </div>
    </section>
  `
  );
  console.error("Discovery Intelligence docs portal failed to initialize.", error);
});
