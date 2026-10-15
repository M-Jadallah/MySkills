// shared/fx.js — مكتبة الأنيميشن الخرافي (Canvas 2D + CSS) لمختبر الطيف
// كل الدوال تتحقق من window.LAB_TIER وتُطبّق المستوى المناسب.
(function () {
  "use strict";
  const EPIC = window.LAB_TIER === "epic";
  const PRIMARY = "#00D4FF";
  const canvas = document.createElement("canvas");
  let ctx, particles = [], raf = null;

  function ensureCanvas(parent) {
    canvas.width = parent.clientWidth; canvas.height = parent.clientHeight;
    canvas.style.position = "absolute"; canvas.style.inset = "0";
    canvas.style.pointerEvents = "none"; canvas.style.zIndex = "0";
    parent.appendChild(canvas);
    ctx = canvas.getContext("2d");
  }

  function spawnParticles(n) {
    if (!EPIC) return;
    for (let i = 0; i < n; i++) {
      particles.push({ x: Math.random()*canvas.width, y: Math.random()*canvas.height,
        vx: (Math.random()-0.5)*0.4, vy: (Math.random()-0.5)*0.4, r: Math.random()*2+0.5 });
    }
  }

  function loop() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const p of particles) {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI*2);
      ctx.fillStyle = PRIMARY; ctx.globalAlpha = 0.5; ctx.fill();
    }
    ctx.globalAlpha = 1;
    raf = requestAnimationFrame(loop);
  }

  const LabFX = {
    // توهج جزيئي مستمر في خلفية منطقة العمل
    ambientGlow(parent) {
      if (!EPIC) return;
      ensureCanvas(parent); spawnParticles(40); loop();
    },
    // انفجار فقاعات عند التفاعل
    burstBubbles(parent, x, y) {
      if (!EPIC) { this.appear(); return; }
      ensureCanvas(parent);
      for (let i = 0; i < 24; i++) {
        const a = (Math.PI*2*i)/24;
        particles.push({ x, y, vx: Math.cos(a)*2, vy: Math.sin(a)*2, r: Math.random()*3+1 });
      }
      if (!raf) loop();
    },
    // شرارات النجاح
    success(parent) {
      if (!EPIC) { parent.style.boxShadow = "0 0 12px " + PRIMARY; return; }
      ensureCanvas(parent);
      for (let i = 0; i < 80; i++) {
        const a = Math.random()*Math.PI*2, s = Math.random()*4+1;
        particles.push({ x: parent.clientWidth/2, y: parent.clientHeight/2, vx: Math.cos(a)*s, vy: Math.sin(a)*s, r: Math.random()*3+1 });
      }
      if (!raf) loop();
    },
    // ظهور تدريجي (يُستخدم على الجوال والسطح)
    appear(el, delay) {
      if (!el) return;
      el.style.opacity = "0"; el.style.transform = "translateY(12px)";
      setTimeout(() => { el.style.transition = "opacity .4s, transform .4s"; el.style.opacity = "1"; el.style.transform = "none"; }, delay||0);
    },
    // spring staggered لأدوات سطح المكتب
    staggerIn(els) {
      els.forEach((el, i) => { if (EPIC) this.appear(el, i*60); else this.appear(el, 0); });
    },
    // انتقال شاشة كامل (بداية -> مختبر)
    screenTransition(from, to) {
      if (!EPIC) { from.classList.add("hidden"); to.classList.remove("hidden"); return; }
      from.style.transition = "opacity .5s, transform .5s";
      from.style.opacity = "0"; from.style.transform = "scale(1.04)";
      setTimeout(() => { from.classList.add("hidden"); to.classList.remove("hidden"); to.style.animation = "labGlow .7s"; }, 500);
    },
    isEpic() { return EPIC; }
  };

  // keyframes للتوهج (تُحقن مرة)
  const style = document.createElement("style");
  style.textContent = `@keyframes labGlow{0%{filter:drop-shadow(0 0 0 ${PRIMARY})}100%{filter:drop-shadow(0 0 24px ${PRIMARY})}}`;
  document.head.appendChild(style);

  window.LabFX = LabFX;
})();
