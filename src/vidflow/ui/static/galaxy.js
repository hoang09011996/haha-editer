"use strict";
// Nền thiên hà: sao nhấp nháy, trôi theo parallax chuột, sao băng; tia sáng khi click.
(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cv = document.getElementById("stars"), ctx = cv.getContext("2d");
  const COLORS = ["#ffffff", "#cfe9ff", "#22d3ee", "#c4b5fd", "#f9a8d4", "#fde68a"];
  let W, H, stars = [], meteors = [], mx = 0, my = 0, dpr = Math.min(devicePixelRatio || 1, 2);
  function resize() {
    W = innerWidth; H = innerHeight; cv.width = W * dpr; cv.height = H * dpr; cv.style.width = W + "px"; cv.style.height = H + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    stars = Array.from({ length: Math.round(W * H / 2600) }, () => ({
      x: Math.random() * W, y: Math.random() * H, z: Math.random() * 0.9 + 0.1, r: Math.random() * 1.3 + 0.2,
      c: COLORS[Math.random() * COLORS.length | 0], t: Math.random() * Math.PI * 2, s: Math.random() * 0.02 + 0.005,
    }));
  }
  function meteor() {
    meteors.push({ x: Math.random() * W * 0.8 + W * 0.2, y: Math.random() * H * 0.3, vx: -(6 + Math.random() * 5), vy: 3 + Math.random() * 3, life: 1 });
  }
  function frame() {
    ctx.clearRect(0, 0, W, H);
    for (const s of stars) {
      s.t += s.s; s.y += s.z * 0.06; if (s.y > H) s.y = 0;
      const a = 0.45 + Math.sin(s.t) * 0.45, px = s.x + mx * s.z * 18, py = s.y + my * s.z * 18;
      ctx.globalAlpha = a; ctx.fillStyle = s.c; ctx.beginPath(); ctx.arc(px, py, s.r * (0.6 + s.z), 0, 7); ctx.fill();
      if (s.r > 1.2) { ctx.globalAlpha = a * 0.25; ctx.beginPath(); ctx.arc(px, py, s.r * 4, 0, 7); ctx.fill(); }
    }
    ctx.globalAlpha = 1;
    for (const m of meteors) {
      m.x += m.vx; m.y += m.vy; m.life -= 0.012;
      const g = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * 14, m.y - m.vy * 14);
      g.addColorStop(0, `rgba(255,255,255,${m.life})`); g.addColorStop(1, "rgba(34,211,238,0)");
      ctx.strokeStyle = g; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(m.x, m.y); ctx.lineTo(m.x - m.vx * 14, m.y - m.vy * 14); ctx.stroke();
    }
    meteors = meteors.filter(m => m.life > 0 && m.x > -200 && m.y < H + 200);
    if (Math.random() < 0.006) meteor();
    requestAnimationFrame(frame);
  }
  addEventListener("resize", resize);
  addEventListener("mousemove", e => { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; });
  resize();
  if (reduce) { frame = () => {}; for (const s of stars) { ctx.fillStyle = s.c; ctx.globalAlpha = 0.7; ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, 7); ctx.fill(); } return; }
  requestAnimationFrame(frame);
  addEventListener("click", e => {
    for (let i = 0; i < 10; i++) {
      const d = document.createElement("span"), a = Math.random() * Math.PI * 2, r = 20 + Math.random() * 40;
      d.className = "cursor-spark"; d.style.left = e.clientX + "px"; d.style.top = e.clientY + "px";
      d.style.setProperty("--dx", Math.cos(a) * r + "px"); d.style.setProperty("--dy", Math.sin(a) * r + "px");
      document.body.append(d); setTimeout(() => d.remove(), 800);
    }
  });
})();
