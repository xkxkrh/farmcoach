(function () {
  if (window.G && document.getElementById('g-root')) return 'already';
  var css = `
  #g-root{position:fixed;inset:0;pointer-events:none;z-index:2147483646;font-family:"Pretendard","Malgun Gothic","Apple SD Gothic Neo",sans-serif}
  #g-cap{position:absolute;left:50%;bottom:34px;transform:translate(-50%,20px);opacity:0;transition:all .35s ease;
    max-width:1560px;background:rgba(17,24,39,.92);color:#fff;border-radius:22px;padding:22px 34px;display:flex;align-items:center;gap:20px;
    box-shadow:0 12px 40px rgba(0,0,0,.35)}
  #g-cap.on{opacity:1;transform:translate(-50%,0)}
  #g-chip{flex-shrink:0;background:#22c55e;color:#06210f;font-weight:800;font-size:24px;border-radius:999px;padding:8px 18px;white-space:nowrap}
  #g-text{font-size:31px;font-weight:700;line-height:1.4;letter-spacing:-.02em;word-break:keep-all}
  #g-text em{font-style:normal;color:#fde047}
  #g-text small{display:block;font-size:22px;font-weight:600;opacity:.7;margin-top:6px}
  .g-box{position:absolute;border:5px solid #ef4444;border-radius:12px;box-shadow:0 0 0 4000px rgba(0,0,0,.0),0 0 18px rgba(239,68,68,.55);
    opacity:0;transform:scale(1.08);transition:opacity .3s, transform .3s}
  .g-box.on{opacity:1;transform:scale(1)}
  .g-box b{position:absolute;left:-5px;top:-44px;background:#ef4444;color:#fff;font-size:22px;font-weight:800;padding:4px 12px;border-radius:8px;white-space:nowrap}
  #g-ptr{position:absolute;left:0;top:0;width:0;height:0;transition:transform .75s cubic-bezier(.45,.05,.25,1);transform:translate(960px,620px)}
  #g-ptr svg{position:absolute;left:-6px;top:-4px;width:44px;height:52px;filter:drop-shadow(0 3px 6px rgba(0,0,0,.45))}
  #g-ptr i{position:absolute;left:-30px;top:-30px;width:60px;height:60px;border-radius:50%;border:5px solid #f59e0b;opacity:0}
  #g-ptr i.go{animation:gpulse .7s ease-out}
  @keyframes gpulse{0%{opacity:1;transform:scale(.3)}100%{opacity:0;transform:scale(1.6)}}
  #g-slide{position:absolute;inset:0;background:#0f172a;opacity:0;transition:opacity .4s}
  #g-slide.on{opacity:1}
  #g-slide img{position:absolute;left:0;top:0;width:1920px}
  #g-slide .tag{position:absolute;left:28px;bottom:66px;background:#f59e0b;color:#111;font-weight:800;font-size:20px;padding:6px 14px;border-radius:999px}
  #g-card{position:absolute;inset:0;background:linear-gradient(135deg,#0f3d2a,#1e7b4f 60%,#2f9e6a);color:#fff;opacity:0;transition:opacity .5s;
    display:flex;flex-direction:column;justify-content:center;padding:0 160px}
  #g-card.on{opacity:1}
  #g-card h1{font-size:84px;margin:0 0 18px;letter-spacing:-.03em}
  #g-card h2{font-size:38px;margin:0 0 40px;font-weight:600;opacity:.9}
  #g-card ol,#g-card ul{font-size:34px;line-height:1.75;margin:0;padding-left:44px}
  #g-card .g-foot{margin:46px 0 0;padding:0;font-size:30px;color:#fff;opacity:.92;line-height:1.6;text-align:left;max-width:none;width:auto}
  #g-card .logo{display:flex;align-items:center;gap:16px;font-size:30px;font-weight:800;margin-bottom:40px}
  #g-card .logo span{width:58px;height:58px;border-radius:16px;background:#fff;color:#1e7b4f;display:grid;place-items:center;font-size:30px}
  `;
  var st = document.createElement('style'); st.id = 'g-style'; st.textContent = css; document.head.appendChild(st);
  var root = document.createElement('div'); root.id = 'g-root';
  root.innerHTML = '<div id="g-slide"></div><div id="g-boxes"></div><div id="g-card"></div>' +
    '<div id="g-cap"><span id="g-chip"></span><span id="g-text"></span></div>' +
    '<div id="g-ptr"><i></i><svg viewBox="0 0 24 28"><path d="M2 2 L2 22 L7.5 17 L11 25.5 L14.5 24 L11 15.8 L18.5 15.8 Z" fill="#fff" stroke="#111" stroke-width="1.6" stroke-linejoin="round"/></svg></div>';
  document.body.appendChild(root);
  var $ = function (id) { return document.getElementById(id); };
  var ptr = { x: 960, y: 620 };

  function visible(e) { var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && e.offsetParent !== null; }
  window.G = {
    find: function (text, nth) {
      var all = [].slice.call(document.querySelectorAll('body *')).filter(function (e) {
        return !root.contains(e) && visible(e) && e.textContent.trim().replace(/\s+/g, ' ') === text;
      });
      // 가장 안쪽(자식이 적은) 요소
      all = all.filter(function (e) { return ![].some.call(e.children, function (c) { return all.indexOf(c) > -1; }); });
      var e = all[nth || 0] || null;
      // 글자만 감싸는 작은 요소면, 그 글자를 담은 버튼/링크/라벨 전체를 가리킴
      if (e) { var b = e.closest('button,a,label,li,[role=button]'); if (b && !root.contains(b) && b.getBoundingClientRect().width < 900) e = b; }
      return e;
    },
    q: function (sel, nth) { return [].slice.call(document.querySelectorAll(sel)).filter(visible)[nth || 0] || null; },
    rect: function (el, pad) {
      if (!el) return null; var r = el.getBoundingClientRect(); pad = pad == null ? 6 : pad;
      return { x: r.left - pad, y: r.top - pad, w: r.width + pad * 2, h: r.height + pad * 2 };
    },
    cap: function (chip, html) {
      $('g-chip').textContent = chip; $('g-chip').style.display = chip ? '' : 'none';
      $('g-text').innerHTML = html; $('g-cap').classList.add('on');
    },
    capOff: function () { $('g-cap').classList.remove('on'); },
    box: function (r, label) {
      if (!r) return false;
      var b = document.createElement('div'); b.className = 'g-box';
      b.style.left = r.x + 'px'; b.style.top = r.y + 'px'; b.style.width = r.w + 'px'; b.style.height = r.h + 'px';
      if (label) { var t = document.createElement('b'); t.textContent = label; b.appendChild(t); }
      $('g-boxes').appendChild(b); requestAnimationFrame(function () { b.classList.add('on'); });
      return true;
    },
    clear: function () { $('g-boxes').innerHTML = ''; },
    move: function (x, y) { ptr = { x: x, y: y }; $('g-ptr').style.transform = 'translate(' + x + 'px,' + y + 'px)'; },
    moveTo: function (el, dx, dy) {
      if (!el) return false; var r = el.getBoundingClientRect();
      G.move(r.left + r.width / 2 + (dx || 0), r.top + r.height / 2 + (dy || 0)); return true;
    },
    pulse: function () { var i = $('g-ptr').querySelector('i'); i.classList.remove('go'); void i.offsetWidth; i.classList.add('go'); },
    ptrShow: function (on) { $('g-ptr').style.display = on ? '' : 'none'; },
    slide: function (src, scale, tag) {
      $('g-slide').innerHTML = '<img src="' + src + '" style="width:' + (1920) + 'px">' + (tag ? '<span class="tag">' + tag + '</span>' : '');
      $('g-slide').classList.add('on');
    },
    slideOff: function () { $('g-slide').classList.remove('on'); },
    card: function (html) { $('g-card').innerHTML = html; $('g-card').classList.add('on'); },
    cardOff: function () { $('g-card').classList.remove('on'); }
  };
  return 'ok';
})();
