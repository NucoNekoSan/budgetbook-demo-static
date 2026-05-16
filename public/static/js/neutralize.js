// 静的スナップショット向け中立化ハンドラ。CSP script-src 'unsafe-inline' を
// 不要にするため、すべての無効化動作を data-neutralize 属性経由で扱う。
(function () {
  "use strict";

  function messageFor(el) {
    return el.getAttribute("data-neutralize") || "閲覧専用デモです (静的スナップショット)";
  }

  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (form && form.hasAttribute && form.hasAttribute("data-neutralize")) {
      ev.preventDefault();
      ev.stopPropagation();
      window.alert(messageFor(form));
      return false;
    }
  }, true);

  document.addEventListener("click", function (ev) {
    var el = ev.target;
    while (el && el !== document) {
      if (el.hasAttribute && el.hasAttribute("data-neutralize") && el.tagName !== "FORM") {
        ev.preventDefault();
        ev.stopPropagation();
        window.alert(messageFor(el));
        return false;
      }
      el = el.parentNode;
    }
  }, true);
})();