// 静的スナップショット向け中立化ハンドラ。CSP script-src 'unsafe-inline' を
// 不要にするため、すべての無効化動作を data-* 属性経由で扱う。
//
// 2 種のクリック動作:
//   - data-fragment-url: fetch して中身をモーダルに inject (編集画面など)
//   - data-neutralize:   モーダルでメッセージ表示 (削除・保存系)
// form submit (data-neutralize) は閲覧専用メッセージを出す。
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

    var note = document.createElement("p");
    note.className = "neutralize-modal__note";
    note.textContent = "※ 閲覧専用デモのため、保存・追加・削除は無効です";

    var body = document.createElement("div");
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
    panel.appendChild(note);
    panel.appendChild(body);
    panel.appendChild(actions);
    overlay.appendChild(panel);

    overlay.addEventListener("click", function (ev) {
      if (ev.target === overlay) hide();
    });

    document.body.appendChild(overlay);
    return { overlay: overlay, panel: panel, title: title, note: note, body: body, closeBtn: closeBtn };
  }

  function ensureDialog() {
    if (!dialog) dialog = buildDialog();
    return dialog;
  }

  function showMessage(msg) {
    var d = ensureDialog();
    d.title.textContent = "閲覧専用デモ";
    d.note.hidden = true;
    d.body.innerHTML = "";
    var p = document.createElement("p");
    p.textContent = msg;
    p.className = "neutralize-modal__message";
    d.body.appendChild(p);
    open();
  }

  function showFragment(url, title) {
    var d = ensureDialog();
    d.title.textContent = title || "詳細";
    d.note.hidden = false;
    d.body.innerHTML = '<p class="neutralize-modal__message">読み込み中...</p>';
    open();

    fetch(url, { credentials: "same-origin", cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.text();
      })
      .then(function (html) {
        // 既にサーバ側で _scrub_security 済み (CSRF/nonce/inline-script 除去、
        // form は data-neutralize 化済) なので innerHTML で安全に inject。
        d.body.innerHTML = html;
      })
      .catch(function (err) {
        d.body.innerHTML = "";
        var p = document.createElement("p");
        p.className = "neutralize-modal__message neutralize-modal__error";
        p.textContent = "詳細の読み込みに失敗しました: " + err.message;
        d.body.appendChild(p);
      });
  }

  function open() {
    var d = ensureDialog();
    lastFocus = document.activeElement;
    d.overlay.hidden = false;
    document.body.classList.add("neutralize-modal-open");
    setTimeout(function () { d.closeBtn.focus(); }, 0);
  }

  function hide() {
    if (!dialog || dialog.overlay.hidden) return;
    dialog.overlay.hidden = true;
    dialog.body.innerHTML = "";
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
      showMessage(messageFor(form));
      return false;
    }
  }, true);

  document.addEventListener("click", function (ev) {
    var el = ev.target;
    while (el && el !== document) {
      if (el.hasAttribute && el.tagName !== "FORM") {
        if (el.hasAttribute("data-fragment-url")) {
          ev.preventDefault();
          ev.stopPropagation();
          showFragment(el.getAttribute("data-fragment-url"), el.getAttribute("data-fragment-title"));
          return false;
        }
        if (el.hasAttribute("data-neutralize")) {
          ev.preventDefault();
          ev.stopPropagation();
          showMessage(messageFor(el));
          return false;
        }
      }
      el = el.parentNode;
    }
  }, true);
})();