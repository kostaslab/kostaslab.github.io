/* Hero network: two communities of nodes (the two halves of the lab's logo) linked by a few bridges.
   Drawn once on load, then drifts gently while visible. Static when reduced motion is requested. */
(function () {
  var canvas = document.querySelector('.hero-graph');
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext('2d');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var nodes = [], edges = [], W = 0, H = 0, dpr = 1, raf = null, visible = true, t0 = performance.now();

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  var colors;
  function readColors() { colors = { a: css('--navy'), b: css('--green'), line: css('--line') }; }

  function rnd(seed) { return function () { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }; }

  function layout() {
    var r = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = r.width; H = r.height;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var rand = rnd(7), n = Math.round(Math.min(90, Math.max(36, W * H / 9000)));
    nodes = [];
    var centres = [{ x: W * 0.36, y: H * 0.42, g: 0 }, { x: W * 0.7, y: H * 0.58, g: 1 }];
    for (var i = 0; i < n; i++) {
      var c = centres[i % 2], ang = rand() * Math.PI * 2, rad = Math.pow(rand(), 0.6) * Math.min(W, H) * 0.42;
      nodes.push({ x0: c.x + Math.cos(ang) * rad * 1.15, y0: c.y + Math.sin(ang) * rad * 0.85, g: c.g,
                   r: 1.6 + rand() * 2.6, p: rand() * Math.PI * 2, s: 0.15 + rand() * 0.25 });
    }
    edges = [];
    var maxD = Math.min(W, H) * 0.2;
    for (var a = 0; a < n; a++) for (var b = a + 1; b < n; b++) {
      var A = nodes[a], B = nodes[b], d = Math.hypot(A.x0 - B.x0, A.y0 - B.y0);
      if (A.g === B.g ? d < maxD : d < maxD * 0.55) edges.push([a, b, d / maxD, A.g !== B.g]);
    }
  }

  function draw(now) {
    var t = (now - t0) / 1000;
    ctx.clearRect(0, 0, W, H);
    var amp = reduce ? 0 : 6;
    for (var i = 0; i < nodes.length; i++) {
      var N = nodes[i];
      N.x = N.x0 + Math.sin(t * N.s + N.p) * amp;
      N.y = N.y0 + Math.cos(t * N.s * 0.8 + N.p) * amp;
    }
    ctx.lineWidth = 1;
    for (var e = 0; e < edges.length; e++) {
      var E = edges[e], A = nodes[E[0]], B = nodes[E[1]];
      ctx.globalAlpha = (1 - E[2]) * (E[3] ? 0.55 : 0.4);
      ctx.strokeStyle = E[3] ? colors.b : (A.g ? colors.b : colors.a);
      ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke();
    }
    ctx.globalAlpha = 0.9;
    for (var j = 0; j < nodes.length; j++) {
      var M = nodes[j];
      ctx.fillStyle = M.g ? colors.b : colors.a;
      ctx.beginPath(); ctx.arc(M.x, M.y, M.r, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
    if (!reduce && visible) raf = requestAnimationFrame(draw);
  }

  function start() { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); }
  readColors(); layout(); start();
  requestAnimationFrame(function () { canvas.classList.add('ready'); });

  var rt;
  window.addEventListener('resize', function () { clearTimeout(rt); rt = setTimeout(function () { layout(); start(); }, 150); });
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { readColors(); start(); });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (en) { visible = en[0].isIntersecting; if (visible) start(); }).observe(canvas);
  }
})();
