const state = {
  manifest: null,
  documents: [],
  filteredDocuments: [],
  activeDocument: null,
  activeSections: [],
  focusMode: false,
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

function readTimeFromMarkdown(markdown) {
  const words = String(markdown || "").trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 220));
}

function buildLibrary() {
  elements.libraryGroups.innerHTML = "";
  const groups = groupByCategory(state.filteredDocuments);
  Object.entries(groups).forEach(([category, docs]) => {
    const group = document.createElement("section");
    group.className = "library-group";
    group.innerHTML = `<div class="group-title">${escapeHtml(category)}</div>`;

    docs.forEach((doc) => {
      const button = document.getElementById("library-card-template").content.firstElementChild.cloneNode(true);
      button.querySelector(".library-card-category").textContent = doc.category;
      button.querySelector(".library-card-title").textContent = doc.title;
      button.querySelector(".library-card-summary").textContent = doc.summary || "";
      button.dataset.path = doc.path;
      if (state.activeDocument && state.activeDocument.path === doc.path) {
        button.classList.add("active");
      }
      button.addEventListener("click", () => openDocument(doc.path));
      group.appendChild(button);
    });
    elements.libraryGroups.appendChild(group);
  });
}

function buildFeatured() {
  elements.featuredGrid.innerHTML = "";
  state.documents.slice(0, 6).forEach((doc) => {
    const card = document.createElement("button");
    card.className = "featured-card";
    card.type = "button";
    card.innerHTML = `
      <p class="eyebrow">${escapeHtml(doc.category)}</p>
      <h4>${escapeHtml(doc.title)}</h4>
      <p>${escapeHtml(doc.summary || "")}</p>
    `;
    card.addEventListener("click", () => openDocument(doc.path));
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
  elements.constellation.innerHTML = "";
  const docs = state.documents.slice(0, 10);
  const width = elements.constellation.clientWidth || 600;
  const height = 320;
  const centerX = width / 2;
  const centerY = height / 2;
  const radiusX = Math.max(110, width * 0.35);
  const radiusY = 115;

  const center = document.createElement("div");
  center.className = "constellation-center";
  center.textContent = "Docs map";
  elements.constellation.appendChild(center);

  docs.forEach((doc, index) => {
    const { x, y } = polarPosition(index, docs.length, radiusX, radiusY, centerX, centerY);
    const dx = x - centerX;
    const dy = y - centerY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const angle = (Math.atan2(dy, dx) * 180) / Math.PI;

    const line = document.createElement("div");
    line.className = "constellation-line";
    line.style.width = `${distance}px`;
    line.style.transform = `translate(0, 0) rotate(${angle}deg)`;
    elements.constellation.appendChild(line);

    const node = document.createElement("button");
    node.className = "constellation-node";
    node.type = "button";
    node.style.left = `${x}px`;
    node.style.top = `${y}px`;
    node.style.transform = "translate(-50%, -50%)";
    node.textContent = doc.title;
    node.addEventListener("click", () => openDocument(doc.path));
    elements.constellation.appendChild(node);
  });
}

function renderSectionNav(sections) {
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
  elements.readingProgress.style.width = `${Math.max(0, Math.min(100, progress))}%`;
  updateSectionHighlight();
}

function observeArticleReveals() {
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
  const response = await fetch(path);
  const markdown = await response.text();
  const rendered = markdownToHtml(markdown);

  state.activeDocument = doc;
  state.activeSections = rendered.sections;
  setReaderMode(true);

  elements.homeView.classList.add("hidden");
  elements.docView.classList.remove("hidden");
  elements.docCategory.textContent = doc.category;
  elements.docTitle.textContent = doc.title;
  elements.docSummary.textContent = doc.summary || "";
  elements.docPathChip.textContent = doc.path;
  elements.docSectionChip.textContent = `${rendered.sections.length} sections`;
  elements.docReadtimeChip.textContent = `${readTimeFromMarkdown(markdown)} min read`;
  elements.rawDocLink.href = doc.path;
  elements.articleStage.innerHTML = rendered.html;

  renderSectionNav(rendered.sections);
  buildLibrary();
  observeArticleReveals();
  if (elements.jumpListContainer) {
    elements.jumpListContainer.scrollTop = 0;
  }

  const url = new URL(window.location.href);
  url.searchParams.set("doc", path);
  window.history.replaceState({}, "", url);
  window.scrollTo({ top: 0, behavior: "auto" });
  updateReadingProgress();
}

function showHome() {
  state.activeDocument = null;
  state.activeSections = [];
  setReaderMode(false);
  elements.docView.classList.add("hidden");
  elements.homeView.classList.remove("hidden");
  const url = new URL(window.location.href);
  url.searchParams.delete("doc");
  window.history.replaceState({}, "", url);
  buildLibrary();
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
  state.manifest = await response.json();
  state.documents = state.manifest.documents || [];
  state.filteredDocuments = [...state.documents];

  elements.metricDocCount.textContent = String(state.documents.length);
  elements.metricCategoryCount.textContent = String(new Set(state.documents.map((doc) => doc.category)).size);

  buildLibrary();
  buildFeatured();
  renderConstellation();
  setReaderMode(false);

  const requested = new URL(window.location.href).searchParams.get("doc");
  if (requested) {
    await openDocument(requested);
  }
}

elements.search.addEventListener("input", (event) => {
  filterDocuments(event.target.value);
});

elements.focusToggle.addEventListener("click", () => {
  state.focusMode = !state.focusMode;
  document.body.classList.toggle("focus-mode", state.focusMode);
  elements.focusToggle.textContent = state.focusMode ? "Exit focus mode" : "Focus mode";
});

elements.backHome.addEventListener("click", showHome);
window.addEventListener("scroll", updateReadingProgress, { passive: true });
window.addEventListener("resize", () => {
  renderConstellation();
});

initialize().catch((error) => {
  elements.homeView.innerHTML = `
    <section class="hero-card">
      <div class="hero-copy">
        <p class="eyebrow">Portal load error</p>
        <h2>Documentation portal could not load.</h2>
        <p>${escapeHtml(error?.message || "Unknown error")}</p>
      </div>
    </section>
  `;
});
