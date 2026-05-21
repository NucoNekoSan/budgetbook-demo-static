// 静的スナップショット向け中立化ハンドラ。CSP script-src 'unsafe-inline' を
// 不要にするため、すべての無効化動作を data-neutralize 属性経由で扱う。
// 押下時はモーダルダイアログで「閲覧専用」を説明する (window.alert より穏当)。
(function () {
  "use strict";

  var DEFAULT_MSG = "閲覧専用デモです (静的スナップショット)";
  var dialog = null;
  var lastFocus = null;

  function messageFor(el) {
    return el.getAttribute("data-neutralize") || DEFAULT_MSG;
  }

  function buildDialog() {
    var overlay = document.createElement("div");
    overlay.className = "neutralize-modal";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-labelledby", "neutralize-modal-title");
    overlay.hidden = true;

    var panel = document.createElement("div");
    panel.className = "neutralize-modal__panel";

    var title = document.createElement("h2");
    title.id = "neutralize-modal-title";
    title.className = "neutralize-modal__title";
    title.textContent = "閲覧専用デモ";

    var body = document.createElement("p");
    body.className = "neutralize-modal__body";

    var actions = document.createElement("div");
    actions.className = "neutralize-modal__actions";

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "neutralize-modal__close";
    closeBtn.textContent = "閉じる";
    closeBtn.addEventListener("click", hide);

    actions.appendChild(closeBtn);
    panel.appendChild(title);
    panel.appendChild(body);
    panel.appendChild(actions);
    overlay.appendChild(panel);

    overlay.addEventListener("click", function (ev) {
      if (ev.target === overlay) hide();
    });

    document.body.appendChild(overlay);
    return { overlay: overlay, body: body, closeBtn: closeBtn };
  }

  function show(msg) {
    if (!dialog) dialog = buildDialog();
    dialog.body.textContent = msg;
    lastFocus = document.activeElement;
    dialog.overlay.hidden = false;
    document.body.classList.add("neutralize-modal-open");
    setTimeout(function () { dialog.closeBtn.focus(); }, 0);
  }

  function hide() {
    if (!dialog || dialog.overlay.hidden) return;
    dialog.overlay.hidden = true;
    document.body.classList.remove("neutralize-modal-open");
    if (lastFocus && typeof lastFocus.focus === "function") {
      try { lastFocus.focus(); } catch (_) {}
    }
    lastFocus = null;
  }

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && dialog && !dialog.overlay.hidden) {
      ev.preventDefault();
      hide();
    }
  });

  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (form && form.hasAttribute && form.hasAttribute("data-neutralize")) {
      ev.preventDefault();
      ev.stopPropagation();
      show(messageFor(form));
      return false;
    }
  }, true);

  document.addEventListener("click", function (ev) {
    var el = ev.target;
    while (el && el !== document) {
      if (el.hasAttribute && el.hasAttribute("data-neutralize") && el.tagName !== "FORM") {
        ev.preventDefault();
        ev.stopPropagation();
        show(messageFor(el));
        return false;
      }
      el = el.parentNode;
    }
  }, true);
})();