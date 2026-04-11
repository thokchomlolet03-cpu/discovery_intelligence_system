const state = {
  manifest: null,
  documents: [],
  filteredDocuments: [],
  activeDocument: null,
  activeSections: [],
  focusMode: false,
  discovery: {
    mode: "manifest",
    repoDocCount: 0,
    autoCount: 0,
  },
};

const elements = {
  libraryGroups: document.getElementById("library-groups"),
  homeView: document.getElementById("home-view"),
  docView: document.getElementById("doc-view"),
  featuredGrid: document.getElementById("featured-grid"),
  mediaGrid: document.getElementById("media-grid"),
  search: document.getElementById("doc-search"),
  focusToggle: document.getElementById("focus-toggle"),
  metricDocCount: document.getElementById("metric-doc-count"),
  metricCategoryCount: document.getElementById("metric-category-count"),
  metricSyncValue: document.getElementById("metric-sync-value"),
  metricSyncLabel: document.getElementById("metric-sync-label"),
  syncSummary: document.getElementById("sync-summary"),
  syncDocTotal: document.getElementById("sync-doc-total"),
  syncAutoCount: document.getElementById("sync-auto-count"),
  siteTitle: document.getElementById("site-title"),
  siteSubtitle: document.getElementById("site-subtitle"),
  mediaTitle: document.getElementById("media-title"),
  mediaSummary: document.getElementById("media-summary"),
  constellation: document.getElementById("doc-constellation"),
  readingProgress: document.getElementById("reading-progress"),
  articleStage: document.getElementById("article-stage"),
  sectionNav: document.getElementById("section-nav"),
  sectionOrbit: document.getElementById("section-orbit"),
  docCategory: document.getElementById("doc-category"),
  docTitle: document.getElementById("doc-title"),
  docSummary: document.getElementById("doc-summary"),
  docPathChip: document.getElementById("doc-path-chip"),
  docSectionChip: document.getElementById("doc-section-chip"),
  docReadtimeChip: document.getElementById("doc-readtime-chip"),
  rawDocLink: document.getElementById("raw-doc-link"),
  backHome: document.getElementById("back-home"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll('"', "&quot;");
}

function slugify(text) {
  return String(text || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

function titleize(text) {
  return String(text || "")
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      if (word.toUpperCase() === "AI") return "AI";
      if (word.toUpperCase() === "LLM") return "LLM";
      if (word.toUpperCase() === "DI") return "DI";
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}

function prettifyFileStem(path) {
  const stem = String(path || "")
    .split("/")
    .pop()
    .replace(/\.md$/i, "")
    .replace(/^\d+_/, "")
    .replace(/[-_]+/g, " ");
  return titleize(stem);
}

function prettifyCategory(segment) {
  const clean = String(segment || "")
    .replace(/^\d+_/, "")
    .replace(/[-_]+/g, " ")
    .trim();
  if (!clean) return "General";
  if (clean.toLowerCase() === "ai interface") return "AI Interface";
  return titleize(clean);
}

function categoryFromPath(path) {
  const parts = String(path || "").split("/");
  if (parts.length > 1) {
    return prettifyCategory(parts[0]);
  }
  const stem = parts[0] || "";
  if (stem.includes("deployment") || stem.includes("cost") || stem.includes("vm")) return "Operations";
  if (stem.includes("system_truth") || stem.includes("evolution_progress")) return "System Truth";
  return "General";
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

  if (inCode) flushCode();
  flushAll();
  return { html: html.join("\n"), sections };
}

function stripMarkdown(text) {
  return String(text || "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    .replace(/#+\s+/g, "")
    .trim();
}

function inferSummaryFromMarkdown(markdown) {
  const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
  const paragraphLines = [];
  let inCode = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      inCode = !inCode;
      continue;
    }
    if (inCode || !trimmed) {
      if (paragraphLines.length) break;
      continue;
    }
    if (/^(#|>|-|\*|\d+\.)\s+/.test(trimmed) || /^---$/.test(trimmed)) {
      if (paragraphLines.length) break;
      continue;
    }
    paragraphLines.push(trimmed);
  }

  if (!paragraphLines.length) return "Auto-indexed markdown document.";
  const sentence = stripMarkdown(paragraphLines.join(" "));
  const words = sentence.split(/\s+/).filter(Boolean);
  if (words.length <= 24) return sentence;
  return `${words.slice(0, 24).join(" ")}...`;
}

function inferTitleFromMarkdown(markdown, path) {
  const firstHeading = String(markdown || "")
    .split(/\r?\n/)
    .find((line) => /^#\s+/.test(line.trim()));
  if (firstHeading) return stripMarkdown(firstHeading.replace(/^#\s+/, ""));
  return prettifyFileStem(path);
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load ${url}`);
  }
  return response.json();
}

async function fetchText(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load ${url}`);
  }
  return response.text();
}

async function discoverMarkdownPaths(repoConfig) {
  if (!repoConfig?.owner || !repoConfig?.name || !repoConfig?.branch) {
    return { mode: "manifest", paths: [] };
  }

  const docsRoot = String(repoConfig.docs_root || "docs").replace(/^\/+|\/+$/g, "");
  const treeUrl = `https://api.github.com/repos/${repoConfig.owner}/${repoConfig.name}/git/trees/${repoConfig.branch}?recursive=1`;

  try {
    const payload = await fetchJson(treeUrl);
    const paths = (payload.tree || [])
      .filter((item) => item.type === "blob")
      .map((item) => item.path)
      .filter((path) => path.startsWith(`${docsRoot}/`) && path.endsWith(".md"))
      .map((path) => path.slice(docsRoot.length + 1))
      .sort();
    return { mode: "github-api", paths };
  } catch (error) {
    console.warn("Docs auto-discovery fallback to manifest only.", error);
    return { mode: "manifest", paths: [] };
  }
}

async function inferDocumentMetadata(path) {
  try {
    const markdown = await fetchText(path);
    return {
      title: inferTitleFromMarkdown(markdown, path),
      path,
      category: categoryFromPath(path),
      summary: inferSummaryFromMarkdown(markdown),
      auto_discovered: true,
    };
  } catch (error) {
    console.warn(`Failed to infer metadata for ${path}`, error);
    return {
      title: prettifyFileStem(path),
      path,
      category: categoryFromPath(path),
      summary: "Auto-indexed markdown document.",
      auto_discovered: true,
    };
  }
}

async function buildDocuments() {
  const manifestDocs = state.manifest.documents || [];
  const manifestByPath = new Map(manifestDocs.map((doc) => [doc.path, doc]));
  const discovery = await discoverMarkdownPaths(state.manifest.repo);
  const discoveredPaths = discovery.paths || [];
  const autoPaths = discoveredPaths.filter((path) => !manifestByPath.has(path));
  const autoDocs = await Promise.all(autoPaths.map((path) => inferDocumentMetadata(path)));

  state.discovery.mode = discovery.mode;
  state.discovery.repoDocCount = discoveredPaths.length || manifestDocs.length;
  state.discovery.autoCount = autoDocs.length;

  return [...manifestDocs, ...autoDocs];
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
      button.querySelector(".library-card-category").textContent = doc.auto_discovered ? `${doc.category} · Auto` : doc.category;
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
      <p class="eyebrow">${escapeHtml(doc.auto_discovered ? `${doc.category} · Auto` : doc.category)}</p>
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
  const centerX = width / 2;
  const centerY = 160;
  const radiusX = Math.max(110, width * 0.35);
  const radiusY = 115;

  const center = document.createElement("div");
  center.className = "constellation-center";
  center.textContent = "Docs constellation";
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

function renderSectionOrbit(sections) {
  elements.sectionOrbit.innerHTML = "";
  if (!sections.length) {
    elements.sectionOrbit.innerHTML = "<p class='site-subtitle'>Section map becomes active when a document is open.</p>";
    return;
  }

  const width = elements.sectionOrbit.clientWidth || 280;
  const centerX = width / 2;
  const centerY = 160;
  const radiusX = Math.max(82, width * 0.3);
  const radiusY = 108;
  const primarySections = sections.filter((section) => section.level <= 2).slice(0, 8);

  const center = document.createElement("div");
  center.className = "orbit-center";
  center.textContent = "Section flow";
  elements.sectionOrbit.appendChild(center);

  primarySections.forEach((section, index) => {
    const { x, y } = polarPosition(index, primarySections.length, radiusX, radiusY, centerX, centerY);
    const dx = x - centerX;
    const dy = y - centerY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    const angle = (Math.atan2(dy, dx) * 180) / Math.PI;

    const line = document.createElement("div");
    line.className = "orbit-line";
    line.style.width = `${distance}px`;
    line.style.transform = `translate(0, 0) rotate(${angle}deg)`;
    elements.sectionOrbit.appendChild(line);

    const node = document.createElement("button");
    node.className = "orbit-node";
    node.type = "button";
    node.style.left = `${x}px`;
    node.style.top = `${y}px`;
    node.style.transform = "translate(-50%, -50%)";
    node.textContent = section.title;
    node.addEventListener("click", () => jumpToSection(section.id));
    elements.sectionOrbit.appendChild(node);
  });
}

function renderSectionNav(sections) {
  elements.sectionNav.innerHTML = "";
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

function renderMedia() {
  const media = state.manifest.media || {};
  const items = media.items || [];
  elements.mediaGrid.innerHTML = "";
  if (!items.length) {
    elements.mediaGrid.innerHTML = "<p class='site-subtitle'>No media entries configured yet.</p>";
    return;
  }

  elements.mediaTitle.textContent = media.title || "Signals, code, and Discovery Intelligence media";
  elements.mediaSummary.textContent =
    media.summary ||
    "External audio and video surfaces that track Discovery Intelligence, programming, and the surrounding build process.";

  items.forEach((item) => {
    const article = document.createElement("article");
    article.className = `media-entry media-${item.type || "external"}`;

    const pill = item.theme ? `<span class="media-pill">${escapeHtml(titleize(item.theme))}</span>` : "";
    const header = `
      <div class="media-copy">
        ${pill}
        <h4>${escapeHtml(item.title || "Untitled media item")}</h4>
        <p>${escapeHtml(item.summary || "")}</p>
      </div>
    `;

    let body = "";
    if (item.type === "spotify") {
      body = `
        <div class="media-embed spotify-shell">
          <iframe
            src="${escapeAttribute(item.embed_url || "")}"
            width="100%"
            height="352"
            frameborder="0"
            allowfullscreen=""
            allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
            loading="lazy"
            title="${escapeAttribute(item.title || "Spotify embed")}"
          ></iframe>
        </div>
      `;
    } else if (item.type === "youtube_playlist") {
      body = `
        <div class="media-embed video-shell">
          <iframe
            src="${escapeAttribute(item.embed_url || "")}"
            title="${escapeAttribute(item.title || "YouTube playlist")}"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            referrerpolicy="strict-origin-when-cross-origin"
            allowfullscreen
            loading="lazy"
          ></iframe>
        </div>
      `;
    } else {
      body = `
        <div class="media-spotlight">
          <div class="media-spotlight-mark">YT</div>
          <div>
            <strong>Channel spotlight</strong>
            <p>Open the channel directly to explore Discovery Intelligence and programming videos together.</p>
          </div>
        </div>
      `;
    }

    const links = item.link_url
      ? `<div class="media-links"><a class="ghost-button" href="${escapeAttribute(item.link_url)}" target="_blank" rel="noreferrer">Open source</a></div>`
      : "";

    article.innerHTML = `${header}${body}${links}`;
    elements.mediaGrid.appendChild(article);
  });
}

function applyManifestChrome() {
  elements.siteTitle.textContent = state.manifest.site_title || "Discovery Intelligence Documentation Portal";
  elements.siteSubtitle.textContent =
    state.manifest.site_subtitle ||
    "Interactive reading surface for the product, scientific, AI-interface, publication, and operational reference documents.";
}

function updateDiscoverySummary() {
  const liveScan = state.discovery.mode === "github-api";
  elements.metricSyncValue.textContent = liveScan ? "Live scan" : "Manifest";
  elements.metricSyncLabel.textContent = liveScan ? "GitHub auto-indexing active" : "Manifest-only fallback";
  elements.syncDocTotal.textContent = String(state.discovery.repoDocCount || state.documents.length);
  elements.syncAutoCount.textContent = String(state.discovery.autoCount || 0);
  elements.syncSummary.textContent = liveScan
    ? `The portal is reading the GitHub repository tree on ${state.manifest.repo.branch} and can auto-index new docs markdown files that are added under /docs, even if you have not curated them in the manifest yet.`
    : "The portal is currently using the curated manifest only. If the live repository scan is unavailable, the browser falls back safely to the known document list.";
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
  const markdown = await fetchText(path);
  const rendered = markdownToHtml(markdown);

  state.activeDocument = doc;
  state.activeSections = rendered.sections;

  elements.homeView.classList.add("hidden");
  elements.docView.classList.remove("hidden");
  elements.docCategory.textContent = doc.auto_discovered ? `${doc.category} · Auto indexed` : doc.category;
  elements.docTitle.textContent = doc.title;
  elements.docSummary.textContent = doc.summary || "";
  elements.docPathChip.textContent = doc.path;
  elements.docSectionChip.textContent = `${rendered.sections.length} sections`;
  elements.docReadtimeChip.textContent = `${readTimeFromMarkdown(markdown)} min read`;
  elements.rawDocLink.href = doc.path;
  elements.articleStage.innerHTML = rendered.html;

  renderSectionNav(rendered.sections);
  renderSectionOrbit(rendered.sections);
  buildLibrary();
  observeArticleReveals();

  const url = new URL(window.location.href);
  url.searchParams.set("doc", path);
  window.history.replaceState({}, "", url);
  window.scrollTo({ top: 0, behavior: "auto" });
  updateReadingProgress();
}

function showHome() {
  state.activeDocument = null;
  state.activeSections = [];
  elements.docView.classList.add("hidden");
  elements.homeView.classList.remove("hidden");
  renderSectionOrbit([]);
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
  state.manifest = await fetchJson("./assets/docs-manifest.json");
  applyManifestChrome();
  state.documents = await buildDocuments();
  state.filteredDocuments = [...state.documents];

  elements.metricDocCount.textContent = String(state.documents.length);
  elements.metricCategoryCount.textContent = String(new Set(state.documents.map((doc) => doc.category)).size);
  updateDiscoverySummary();

  buildLibrary();
  buildFeatured();
  renderConstellation();
  renderSectionOrbit([]);
  renderMedia();

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
  renderSectionOrbit(state.activeSections);
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
