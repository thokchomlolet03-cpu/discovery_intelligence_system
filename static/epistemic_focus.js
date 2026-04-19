(function () {
  const selectionState = new Map();

  function rootKey(root) {
    return String(root?.dataset?.epistemicSelectionKey || "");
  }

  function applySelection(root, selectedValue, persist) {
    if (!(root instanceof HTMLElement)) {
      return;
    }
    const selector = root.querySelector("[data-epistemic-focus-select]");
    const panels = root.querySelectorAll("[data-epistemic-focus-panel]");
    const normalizedValue = String(selectedValue || "");
    if (selector instanceof HTMLSelectElement && normalizedValue) {
      selector.value = normalizedValue;
    }
    panels.forEach((panel) => {
      if (!(panel instanceof HTMLElement)) {
        return;
      }
      panel.hidden = String(panel.dataset.epistemicFocusPanel || "") !== normalizedValue;
    });
    if (persist) {
      const key = rootKey(root);
      if (key && normalizedValue) {
        selectionState.set(key, normalizedValue);
        root.dataset.epistemicPersistenceUsed = "true";
      }
    }
  }

  function enhance(root) {
    const scope = root instanceof HTMLElement || root instanceof Document ? root : document;
    const blocks = scope.querySelectorAll("[data-epistemic-focus-root]");
    blocks.forEach((block) => {
      if (!(block instanceof HTMLElement)) {
        return;
      }
      const selector = block.querySelector("[data-epistemic-focus-select]");
      if (!(selector instanceof HTMLSelectElement)) {
        return;
      }
      if (!block.dataset.epistemicSelectorAvailable) {
        block.dataset.epistemicSelectorAvailable = "true";
      }
      if (!block.dataset.epistemicPersistenceUsed) {
        block.dataset.epistemicPersistenceUsed = "false";
      }
      if (!selector.dataset.epistemicFocusBound) {
        selector.addEventListener("change", () => {
          applySelection(block, selector.value, true);
        });
        selector.dataset.epistemicFocusBound = "true";
      }
      const key = rootKey(block);
      const preferred = key && selectionState.has(key) ? selectionState.get(key) : selector.value;
      applySelection(block, preferred, false);
    });
  }

  window.discoveryEpistemicFocus = {
    enhance,
    applySelection,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function onReady() {
      document.removeEventListener("DOMContentLoaded", onReady);
      enhance(document);
    });
  } else {
    enhance(document);
  }
})();
