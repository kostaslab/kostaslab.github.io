/* Publication filters: search + author/type/theme, synced with the URL (?q=&member=&type=&topic=) */
(function () {
  var form = document.querySelector('.filters');
  if (!form) return;
  var items = Array.prototype.slice.call(document.querySelectorAll('.pub'));
  var groups = Array.prototype.slice.call(document.querySelectorAll('[data-year-group]'));
  var count = form.querySelector('.count');
  var empty = document.querySelector('.empty');
  var keys = ['member', 'type', 'topic', 'origin'];

  function fold(s) {
    return (s || '').toLocaleLowerCase('tr').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/ı/g, 'i');
  }
  items.forEach(function (el) { el._text = fold(el.textContent); });

  function state() {
    var st = { q: form.q.value.trim() };
    keys.forEach(function (k) { var c = form.querySelector('input[name=' + k + ']:checked'); st[k] = c ? c.value : ''; });
    return st;
  }

  function apply(push) {
    var st = state(), shown = 0, terms = fold(st.q).split(/\s+/).filter(Boolean);
    items.forEach(function (el) {
      var ok = (!st.member || el.dataset.members.split(' ').indexOf(st.member) > -1) &&
               (!st.type || el.dataset.type === st.type) &&
               (!st.topic || el.dataset.topics.split(' ').indexOf(st.topic) > -1) &&
               (!st.origin || el.dataset.origin === st.origin) &&
               terms.every(function (t) { return el._text.indexOf(t) > -1; });
      el.hidden = !ok; if (ok) shown++;
    });
    groups.forEach(function (g) { g.hidden = !g.querySelector('.pub:not([hidden])'); });
    count.textContent = count.dataset.template.replace('{n}', shown).replace('{total}', count.dataset.total);
    empty.hidden = shown > 0;
    if (push) {
      var p = new URLSearchParams();
      Object.keys(st).forEach(function (k) { if (st[k]) p.set(k, st[k]); });
      var qs = p.toString();
      history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
    }
  }

  // initial state from URL
  var params = new URLSearchParams(location.search);
  if (params.get('q')) form.q.value = params.get('q');
  keys.forEach(function (k) {
    var v = params.get(k);
    if (v) { var r = form.querySelector('input[name=' + k + '][value="' + CSS.escape(v) + '"]'); if (r) r.checked = true; }
  });

  form.addEventListener('input', function () { apply(true); });
  form.addEventListener('change', function () { apply(true); });
  document.querySelector('[data-reset]').addEventListener('click', function () {
    form.reset(); apply(true); form.q.focus();
  });
  apply(false);
})();
