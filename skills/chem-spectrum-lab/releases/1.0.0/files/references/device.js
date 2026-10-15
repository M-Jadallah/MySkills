// shared/device.js — كشف الجهاز وتحديد مستوى الأنيميشن
// يُحمَّل أولاً في كل صفحة ومختبر.
(function () {
  "use strict";
  function detectTier() {
    const fine = window.matchMedia && window.matchMedia("(pointer:fine)").matches;
    const wide = window.innerWidth >= 1024;
    const noTouch = (navigator.maxTouchPoints || 0) === 0;
    if (fine && wide && noTouch) return "epic";   // سطح المكتب: الأنيميشن الخرافي
    return "lean";                                 // جوال/لمس: خفيف
  }
  window.LAB_TIER = detectTier();
  window.addEventListener("resize", function () {
    const t = detectTier();
    if (t !== window.LAB_TIER) location.reload(); // إعادة ضبط المستوى عند تبديل الجهاز
  });
})();
