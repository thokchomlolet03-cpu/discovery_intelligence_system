const mediaPageState = {
  manifest: null,
};

const mediaPageElements = {
  title: document.getElementById("media-page-title"),
  summary: document.getElementById("media-page-summary"),
  spotifyGrid: document.getElementById("spotify-grid"),
  youtubeGrid: document.getElementById("youtube-grid"),
};

function mediaEscapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function mediaEscapeAttribute(value) {
  return mediaEscapeHtml(value).replaceAll('"', "&quot;");
}

function mediaTitleize(text) {
  return String(text || "")
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

function renderMediaEntry(item) {
  const article = document.createElement("article");
  article.className = `media-entry media-${item.type || "external"}`;

  const pill = item.theme ? `<span class="media-pill">${mediaEscapeHtml(mediaTitleize(item.theme))}</span>` : "";

  let body = "";
  if (item.type === "spotify") {
    body = `
      <div class="media-embed spotify-shell">
        <iframe
          src="${mediaEscapeAttribute(item.embed_url || "")}"
          width="100%"
          height="352"
          frameborder="0"
          allowfullscreen=""
          allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
          loading="lazy"
          title="${mediaEscapeAttribute(item.title || "Spotify embed")}"
        ></iframe>
      </div>
    `;
  } else if (item.type === "youtube_playlist") {
    body = `
      <div class="media-embed video-shell">
        <iframe
          src="${mediaEscapeAttribute(item.embed_url || "")}"
          title="${mediaEscapeAttribute(item.title || "YouTube playlist")}"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          referrerpolicy="strict-origin-when-cross-origin"
          allowfullscreen
          loading="lazy"
        ></iframe>
      </div>
    `;
  }

  const links = item.link_url
    ? `<div class="media-links"><a class="ghost-button" href="${mediaEscapeAttribute(item.link_url)}" target="_blank" rel="noreferrer">Open on ${mediaEscapeHtml(item.platform || "source")}</a></div>`
    : "";

  article.innerHTML = `
    <div class="media-copy">
      ${pill}
      <h4>${mediaEscapeHtml(item.title || "Untitled media item")}</h4>
      <p>${mediaEscapeHtml(item.summary || "")}</p>
    </div>
    ${body}
    ${links}
  `;
  return article;
}

async function initializeMediaPage() {
  const response = await fetch("./assets/docs-manifest.json");
  if (!response.ok) {
    throw new Error("Unable to load media manifest.");
  }

  mediaPageState.manifest = await response.json();
  const media = mediaPageState.manifest.media || {};
  const items = media.items || [];
  const spotifyItems = items.filter((item) => item.platform === "spotify");
  const youtubeItems = items.filter((item) => item.platform === "youtube" && item.type === "youtube_playlist");

  if (media.title) mediaPageElements.title.textContent = media.title;
  if (media.summary) mediaPageElements.summary.textContent = media.summary;

  mediaPageElements.spotifyGrid.innerHTML = "";
  spotifyItems.forEach((item) => mediaPageElements.spotifyGrid.appendChild(renderMediaEntry(item)));

  mediaPageElements.youtubeGrid.innerHTML = "";
  youtubeItems.forEach((item) => mediaPageElements.youtubeGrid.appendChild(renderMediaEntry(item)));
}

initializeMediaPage().catch((error) => {
  const message = `<p class="site-subtitle">${mediaEscapeHtml(error?.message || "Media page could not load.")}</p>`;
  mediaPageElements.spotifyGrid.innerHTML = message;
  mediaPageElements.youtubeGrid.innerHTML = message;
});
