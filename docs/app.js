(function () {
  "use strict";
  var ICONS = { "001": "🥬", "002": "🥩", "003": "🐟", "004": "🥢", "005": "🥫" };
  var LINK_ICONS = { blue: "🏬", green: "📘", yellow: "💬", dark: "📌", red: "📣" };
  var D = null, byId = {}, picked = [];
  var $ = function (s) { return document.querySelector(s); };
  var main = $("#main");

  try { picked = JSON.parse(localStorage.getItem("fc_compare") || "[]"); } catch (e) { picked = []; }
  function savePicked() { try { localStorage.setItem("fc_compare", JSON.stringify(picked)); } catch (e) {} }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function linkify(s) {
    return esc(s).replace(/https?:\/\/[^\s<]+/g, function (u) { return '<a href="' + u + '" target="_blank" rel="noopener">' + u + "</a>"; });
  }
  function won(n) { return Number(n || 0).toLocaleString("ko-KR") + "원"; }
  function img(g) {
    return g.img ? '<img src="' + esc(g.img) + '" alt="" loading="lazy">' : '<span class="noimg">사진 없음</span>';
  }
  function isNew(g) {
    var a = new Date(g.date.replace(" ", "T")), b = new Date((D.updated || "").replace(" ", "T"));
    return (b - a) / 86400000 <= 7;
  }
  function catName(code) {
    for (var i = 0; i < D.categories.length; i++) if (D.categories[i].code === code) return D.categories[i].name;
    return "기타";
  }
  function minPrice(g) { return Math.min.apply(null, g.options.map(function (o) { return o.price; })); }
  function taxBadge(t) { return t === "면세" ? '<span class="b b-free">면세</span>' : t === "과세" ? '<span class="b b-tax">과세</span>' : t === "혼합" ? '<span class="b b-tax">과세·면세</span>' : ""; }

  // ---------- 바로가기 버튼 + 영상 ----------
  function linkButtons() {
    return (D.links || []).map(function (l) {
      var c = l.color || "blue";
      return '<a class="lbtn ' + esc(c) + '" href="' + esc(l.url) + '" target="_blank" rel="noopener"><span class="i">' + (LINK_ICONS[c] || "🔗") +
        "</span>" + esc(l.label) + '<span class="go">›</span></a>';
    }).join("") + (D.videos || []).map(function (v, i) {
      return '<button type="button" class="lbtn video" data-video="' + i + '"><span class="i">▶</span>' + esc(v.title) + '<span class="go">›</span></button>';
    }).join("");
  }
  function playVideo(i) {
    var v = D.videos[i]; if (!v) return;
    $("#playerTitle").textContent = v.title;
    var el = $("#playerVideo"); el.src = v.file; $("#player").showModal();
    var p = el.play(); if (p && p.catch) p.catch(function () {});
  }
  $("#player").addEventListener("close", function () { var el = $("#playerVideo"); el.pause(); el.removeAttribute("src"); el.load(); });

  // ---------- 왼쪽 메뉴 ----------
  function sideNav(route) {
    var h = '<a href="#/" class="' + (route === "home" ? "on" : "") + '"><span class="ico">🏠</span>홈</a><hr>';
    D.categories.forEach(function (c) {
      var n = D.groups.filter(function (g) { return g.cat === c.code; }).length;
      h += '<a href="#/c/' + c.code + '" class="' + (route === c.code ? "on" : "") + '"><span class="ico">' +
        (ICONS[c.code] || "📦") + "</span>" + esc(c.name) + '<span class="n">' + n + "</span></a>";
    });
    $("#side").innerHTML = h;
    $("#sideLinks").innerHTML = (D.links && D.links.length) || (D.videos && D.videos.length) ? '<div class="lh">📢 공지 · 바로가기</div>' + linkButtons() : "";
  }

  // ---------- 홈 ----------
  function home() {
    var md = (D.md || []).map(function (p) {
      var g = byId[p.g]; if (!g) return "";
      var opts = (p.o && p.o.length ? g.options.filter(function (o) { return p.o.indexOf(o.id) > -1; }) : g.options.slice(0, 3));
      return '<a class="md-item" href="#/c/' + g.cat + "/" + g.id + '">' + img(g) + "<div><b>" + esc(g.name) + "</b>" +
        opts.map(function (o) { return '<div class="md-opt"><span>' + esc(o.name) + "</span><span>" + won(o.price) + "</span></div>"; }).join("") +
        "</div>" + (p.text ? '<div class="md-text">' + esc(p.text) + "</div>" : "") + "</a>";
    }).join("");
    var latest = D.groups.slice(0, 8).map(function (g) {
      return '<a href="#/c/' + g.cat + "/" + g.id + '">' + img(g) + '<div><div class="t">' + esc(g.name) +
        '</div><div class="d">' + esc(catName(g.cat)) + " · " + esc(g.date.slice(0, 10)) + "</div></div>" +
        (isNew(g) ? '<span class="b b-new">NEW</span>' : "<span></span>") + "</a>";
    }).join("");
    main.innerHTML = '<div class="home"><div>' +
      '<section class="card notice"><h2 class="h">📢 공지사항</h2><div class="body">' + linkify(D.notice) + "</div>" +
      '<div class="links">' + linkButtons() + "</div></section>" +
      '<section class="card latest"><h2 class="h">🆕 최근 등록 상품</h2>' + (latest || '<p class="empty">아직 상품이 없어요.</p>') + "</section>" +
      '</div><aside class="card md"><h2 class="h">⭐ 금주의 MD추천 상품!</h2>' +
      (md || '<p class="empty">이번 주 추천 상품을 준비 중이에요.</p>') + "</aside></div>";
  }

  // ---------- 상품 카드 ----------
  function facts(g) {
    var rows = [["배송비", g.ship], ["제주", g.jeju], ["도서산간", g.island], ["원산지", g.origin]].filter(function (r) { return r[1]; });
    return '<dl class="facts">' + rows.map(function (r) {
      return "<div><dt>" + r[0] + '</dt><dd class="' + (/불가/.test(r[1]) ? "no" : "") + '">' + esc(r[1]) + "</dd></div>";
    }).join("") + "</dl>";
  }
  function card(g) {
    var on = picked.indexOf(g.id) > -1;
    var rows = g.options.map(function (o) {
      return '<tr><td class="oname" title="눌러서 옵션명 복사">' + esc(o.name) + (o.tax ? " " + taxBadge(o.tax) : "") +
        '</td><td class="pr">' + won(o.price) + "</td></tr>";
    }).join("");
    return '<article class="card pc' + (on ? " picked" : "") + '" id="g' + g.id + '">' +
      '<label class="pick"><input type="checkbox" data-pick="' + g.id + '"' + (on ? " checked" : "") + ">비교</label>" +
      '<button class="thumb" type="button" data-big="' + esc(g.big || g.img) + '" aria-label="사진 크게 보기">' + img(g) + "</button>" +
      '<div class="pb"><div class="badges">' + (isNew(g) ? '<span class="b b-new">NEW</span>' : "") + taxBadge(g.tax) + "</div>" +
      "<h3>" + esc(g.name) + "</h3>" + facts(g) +
      '<div class="price">' + won(minPrice(g)) + (g.options.length > 1 ? "~<small>옵션 " + g.options.length + "개</small>" : "") + "</div>" +
      '<div class="acts"><button type="button" class="btn" data-drop="' + g.id + '">옵션·가격 ▾</button>' +
      (g.link ? '<a class="btn pri" href="' + esc(g.link) + '" target="_blank" rel="noopener">상세페이지 ↗</a>' : '<span></span>') + "</div>" +
      '<div class="drop" id="d' + g.id + '" hidden><table class="opts"><tbody>' + rows + "</tbody></table>" +
      (g.note ? '<div class="note">' + linkify(g.note) + "</div>" : "") + "</div>" +
      "</div></article>";
  }

  function list(title, groups, focusId) {
    main.innerHTML = '<div class="listhead"><h2 class="h">' + title + ' <span class="sub">' + groups.length + "개 · 최신순</span></h2>" +
      '<button class="btn" type="button" data-cmp>⚖ 비교하여보기 (' + picked.length + ")</button></div>" +
      (groups.length ? '<div class="grid">' + groups.map(card).join("") + "</div>" : '<p class="none">상품이 없어요.</p>');
    if (focusId) {
      var el = document.getElementById("g" + focusId);
      if (el) {
        toggleDrop(focusId, true);
        el.scrollIntoView({ block: "start" }); el.classList.add("flash");
        setTimeout(function () { el.classList.remove("flash"); }, 1600);
      }
    } else window.scrollTo(0, 0);
  }
  function toggleDrop(id, force) {
    var d = document.getElementById("d" + id); if (!d) return;
    var open = force != null ? force : d.hidden;
    d.hidden = !open;
    var b = main.querySelector('[data-drop="' + id + '"]');
    if (b) b.textContent = open ? "옵션·가격 ▴" : "옵션·가격 ▾";
  }

  function search(q) {
    var words = q.toLowerCase().split(/\s+/).filter(Boolean);
    list("‘" + esc(q) + "’ 검색 결과", D.groups.filter(function (g) {
      var t = (g.name + " " + g.options.map(function (o) { return o.name; }).join(" ")).toLowerCase();
      return words.every(function (w) { return t.indexOf(w) > -1; });
    }));
  }

  // ---------- 비교 ----------
  function updateCmp() {
    picked = picked.filter(function (id) { return byId[id]; });
    savePicked();
    $("#cmpbar").hidden = !picked.length;
    $("#cmpcount").textContent = "선택한 상품 " + picked.length + "개";
    var b = main.querySelector("[data-cmp]"); if (b) b.textContent = "⚖ 비교하여보기 (" + picked.length + ")";
  }
  function openCompare() {
    if (!picked.length) { toast("비교할 상품의 '비교'를 먼저 체크해 주세요"); return; }
    var gs = picked.map(function (id) { return byId[id]; });
    function row(label, f) { return "<tr><th>" + label + "</th>" + gs.map(function (g) { return "<td>" + f(g) + "</td>"; }).join("") + "</tr>"; }
    var t = '<table class="cmpt"><tbody>' +
      row("사진", function (g) { return g.img ? '<img src="' + esc(g.img) + '" alt="">' : ""; }) +
      row("상품명", function (g) { return '<div class="nm">' + esc(g.name) + '</div><div class="badges" style="margin-top:6px">' + taxBadge(g.tax) + "</div>"; }) +
      row("최저 공급가", function (g) { return "<b>" + won(minPrice(g)) + "</b>"; }) +
      row("옵션·공급가", function (g) { return '<div class="ol">' + g.options.map(function (o) { return "<div><span>" + esc(o.name) + "</span><b>" + won(o.price) + "</b></div>"; }).join("") + "</div>"; }) +
      row("배송비", function (g) { return esc(g.ship || "-"); }) +
      row("제주", function (g) { return esc(g.jeju || "-"); }) +
      row("도서산간", function (g) { return esc(g.island || "-"); }) +
      row("원산지", function (g) { return esc(g.origin || "-"); }) +
      row("비고", function (g) { return '<div class="nt">' + linkify(g.note || "-") + "</div>"; }) +
      row("", function (g) { return (g.link ? '<a class="btn pri" href="' + esc(g.link) + '" target="_blank" rel="noopener">상세페이지 ↗</a> ' : "") + '<button class="btn" type="button" data-unpick="' + g.id + '">빼기</button>'; }) +
      "</tbody></table>";
    $("#cmpTable").innerHTML = t;
    if (!$("#compare").open) $("#compare").showModal();
  }

  // ---------- 화면 고르기 ----------
  function route() {
    if (!D) return;
    var q = $("#q").value.trim();
    var parts = location.hash.replace(/^#\/?/, "").split("/");
    if (q) { sideNav(""); search(q); }
    else if (parts[0] === "c" && parts[1]) {
      sideNav(parts[1]);
      list((ICONS[parts[1]] || "") + " " + esc(catName(parts[1])), D.groups.filter(function (g) { return g.cat === parts[1]; }), parts[2]);
    } else { sideNav("home"); home(); window.scrollTo(0, 0); }
    updateCmp();
  }

  // ---------- 동작 ----------
  var toastTimer;
  function toast(msg) {
    var t = $("#toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.classList.remove("show"); }, 1600);
  }
  document.addEventListener("click", function (e) {
    var v = e.target.closest("[data-video]"); if (v) { playVideo(+v.dataset.video); return; }
    var th = e.target.closest(".thumb");
    if (th && th.dataset.big) { var w = $("#viewer"); w.querySelector("img").src = th.dataset.big; w.showModal(); return; }
    var dr = e.target.closest("[data-drop]"); if (dr) { toggleDrop(dr.dataset.drop); return; }
    if (e.target.closest("[data-cmp]") || e.target.closest("#cmpOpen")) { openCompare(); return; }
    if (e.target.closest("#cmpClear")) { picked = []; route(); return; }
    var un = e.target.closest("[data-unpick]");
    if (un) {
      picked = picked.filter(function (id) { return id !== un.dataset.unpick; });
      var cb = main.querySelector('[data-pick="' + un.dataset.unpick + '"]');
      if (cb) { cb.checked = false; cb.closest(".pc").classList.remove("picked"); }
      updateCmp(); if (picked.length) openCompare(); else $("#compare").close(); return;
    }
    var x = e.target.closest(".x"); if (x) { x.closest("dialog").close(); return; }
    var on = e.target.closest(".oname");
    if (on && navigator.clipboard) navigator.clipboard.writeText(on.firstChild.textContent.trim()).then(function () { toast("옵션명을 복사했어요"); }, function () {});
  });
  $("#viewer").addEventListener("click", function () { this.close(); });
  ["#player", "#compare"].forEach(function (s) { $(s).addEventListener("click", function (e) { if (e.target === this) this.close(); }); });
  main.addEventListener("change", function (e) {
    var cb = e.target.closest("[data-pick]"); if (!cb) return;
    var id = cb.dataset.pick;
    picked = picked.filter(function (x) { return x !== id; });
    if (cb.checked) picked.push(id);
    cb.closest(".pc").classList.toggle("picked", cb.checked);
    updateCmp();
  });
  var qTimer;
  $("#q").addEventListener("input", function () { clearTimeout(qTimer); qTimer = setTimeout(route, 150); });
  window.addEventListener("hashchange", function () { $("#q").value = ""; route(); });

  fetch("data.json?v=" + Date.now()).then(function (r) { return r.json(); }).then(function (d) {
    D = d;
    D.groups.forEach(function (g) { byId[g.id] = g; });
    $("#updated").textContent = "업데이트 " + (D.updated || "");
    route();
  }).catch(function () {
    main.innerHTML = '<p class="none">상품 정보를 불러오지 못했어요. 잠시 후 새로고침 해 주세요.</p>';
  });
})();
