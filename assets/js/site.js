/* KOSTAS Lab — shared behaviour */
(function () {
  var btn = document.querySelector('.menu-btn');
  var nav = document.getElementById('nav');
  if (btn && nav) {
    btn.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.addEventListener('click', function (e) {
      if (e.target.tagName === 'A') { nav.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
    });
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve) {
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch (e) {}
      document.body.removeChild(ta); resolve();
    });
  }

  document.addEventListener('click', function (e) {
    var b = e.target.closest('.copy-btn');
    if (!b) return;
    var text = b.getAttribute('data-copy');
    if (!text) { var code = b.parentNode.querySelector('code'); text = code ? code.textContent : ''; }
    copyText(text).then(function () {
      var original = b.textContent;
      b.textContent = b.getAttribute('data-copy-label') || '✓';
      b.classList.add('done');
      setTimeout(function () { b.textContent = original; b.classList.remove('done'); }, 1600);
    });
  });
})();
