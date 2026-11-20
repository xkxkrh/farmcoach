(function () {
  "use strict";
  var ICONS = { "001": "🥬", "002": "🥩", "003": "🐟", "004": "🥢", "005": "🥫" };
  var D = null, byId = {}, showOut = false;
  var $ = function (s) { return document.querySelector(s); };
  var main = $("#main");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function linkify(s) {
    return esc(s).replace(/https?:\/\/[^\s<]+/g, function (u) {
      return '<a href="' + u + '" target="_blank" rel="noopener">' + u + "</a>";
    });
  }
  function won(n) { return Number(n || 0).toLocaleString("ko-KR") + "원"; }
  function img(g, cls) {
    return g.img ? '<img class="' + (cls || "") + '" src="' + esc(g.img) + '" alt="" loading="lazy">'
      : '<span class="noimg ' + (cls || "") + '">사진 없음</span>';
  }
  function isNew(g) {
    var a = new Date(g.date.replace(" ", "T")), b = new Date((D.updated || "").replace(" ", "T"));
    return (b - a) / 86400000 <= 7;
  }
  function catName(code) {
    for (var i = 0; i < D.categories.length; i++) if (D.categories[i].code === code) return D.categories[i].name;
    return "기타";
  }

  // ---------- 그리기 ----------
  function sideNav(route) {
    var h = '<a href="#/" class="' + (route === "home" ? "on" : "") + '"><span class="ico">🏠</span>홈</a><hr>';
    D.categories.forEach(function (c) {
      var n = D.groups.filter(function (g) { return g.cat === c.code && !g.soldout; }).length;
      h += '<a href="#/c/' + c.code + '" class="' + (route === c.code ? "on" : "") + '"><span class="ico">' +
        (ICONS[c.code] || "📦") + "</span>" + esc(c.name) + '<span class="n">' + n + "</span></a>";
    });
    $("#side").innerHTML = h;
  }

  function home() {
    var md = (D.md || []).map(function (p) {
      var g = byId[p.g];
      if (!g) return "";
      var opts = (p.o && p.o.length ? g.options.filter(function (o) { return p.o.indexOf(o.id) > -1; }) : g.options.slice(0, 3));
      return '<a class="md-item" href="#/c/' + g.cat + "/" + g.id + '">' + img(g) + "<div><b>" + esc(g.name) + "</b>" +
        opts.map(function (o) {
          return '<div class="md-opt"><span>' + esc(o.name) + "</span><span>" + (o.soldout ? "품절" : won(o.price)) + "</span></div>";
        }).join("") + "</div>" + (p.text ? '<div class="md-text">' + esc(p.text) + "</div>" : "") + "</a>";
    }).join("");
    var latest = D.groups.filter(function (g) { return !g.soldout; }).slice(0, 8).map(function (g) {
      return '<a href="#/c/' + g.cat + "/" + g.id + '">' + img(g) + '<div><div class="t">' + esc(g.name) +
        '</div><div class="d">' + esc(catName(g.cat)) + " · " + esc(g.date.slice(0, 10)) + "</div></div>" +
        (isNew(g) ? '<span class="b b-new">NEW</span>' : "<span></span>") + "</a>";
    }).join("");
    main.innerHTML = '<div class="home"><div>' +
      '<section class="card notice"><h2 class="h">📢 공지사항</h2><div class="body">' + linkify(D.notice) + "</div></section>" +
      '<section class="card latest"><h2 class="h">🆕 최근 등록 상품</h2>' + (latest || '<p class="empty">아직 상품이 없어요.</p>') + "</section>" +
      '</div><aside class="card md"><h2 class="h">⭐ 금주의 MD추천 상품!</h2>' +
      (md || '<p class="empty">이번 주 추천 상품을 준비 중이에요.</p>') + "</aside></div>";
  }

  function groupCard(g) {
    var badges = (isNew(g) && !g.soldout ? '<span class="b b-new">NEW</span>' : "") +
      (g.tax === "면세" ? '<span class="b b-free">면세</span>' : g.tax === "과세" ? '<span class="b b-tax">과세</span>' : "") +
      (g.soldout ? '<span class="b b-out">품절</span>' : "");
    var pills = [["배송비", g.ship], ["제주", g.jeju], ["도서산간", g.island]].filter(function (p) { return p[1]; })
      .map(function (p) {
        return '<span class="pill' + (/불가/.test(p[1]) ? " no" : "") + '">' + p[0] + "<b>" + esc(p[1]) + "</b></span>";
      }).join("");
    var rows = g.options.map(function (o) {
      var tax = o.tax ? ' <span class="b ' + (o.tax === "면세" ? "b-free" : "b-tax") + '">' + o.tax + "</span>" : "";
      return '<tr class="' + (o.soldout ? "so" : "") + '"><td class="oname" title="눌러서 옵션명 복사">' + esc(o.name) + tax +
        '</td><td class="price">' + won(o.price) + '</td><td class="ost">' + (o.soldout ? '<span class="b b-out">품절</span>' : "") + "</td></tr>";
    }).join("");
    var first = (g.note || "").split("\n")[0];
    return '<article class="card g' + (g.soldout ? " out" : "") + '" id="g' + g.id + '">' +
      '<button class="thumb" type="button" data-big="' + esc(g.big || g.img) + '" aria-label="사진 크게 보기">' + img(g) + "</button>" +
      '<div class="gtop"><div class="gtitle"><h3>' + esc(g.name) + "</h3>" + badges + "</div>" +
      '<div class="gdate">등록일 ' + esc(g.date.slice(0, 10)) + "</div></div>" +
      '<div class="gmain">' + (pills ? '<div class="info">' + pills + "</div>" : "") +
      '<table class="opts"><tbody>' + rows + "</tbody></table>" +
      (g.note ? '<details class="note"><summary>비고 · ' + esc(first) + '</summary><div class="nb">' + linkify(g.note) + "</div></details>" : "") +
      (g.link ? '<div class="actions"><a class="btn pri" href="' + esc(g.link) + '" target="_blank" rel="noopener">상세페이지 보기 ↗</a></div>' : "") +
      "</div></article>";
  }

  function list(title, groups, focusId) {
    var sale = groups.filter(function (g) { return !g.soldout; });
    var out = groups.filter(function (g) { return g.soldout; });
    if (focusId && out.some(function (g) { return g.id === focusId; })) showOut = true;
    var h = '<div class="listhead"><h2 class="h">' + title + ' <span class="sub">판매중 ' + sale.length + "개</span></h2>" +
      (out.length ? '<button class="chip' + (showOut ? " on" : "") + '" id="toggleOut" type="button">품절 상품도 보기 (' + out.length + ")</button>" : "") +
      "</div>";
    h += sale.length ? '<div class="groups">' + sale.map(groupCard).join("") + "</div>" : '<p class="none">판매중인 상품이 없어요.</p>';
    if (showOut && out.length) h += '<div class="outhead">품절 상품</div><div class="groups">' + out.map(groupCard).join("") + "</div>";
    main.innerHTML = h;
    var t = $("#toggleOut");
    if (t) t.onclick = function () { showOut = !showOut; route(); };
  }

  function search(q) {
    var words = q.toLowerCase().split(/\s+/).filter(Boolean);
    var hits = D.groups.filter(function (g) {
      var text = (g.name + " " + g.options.map(function (o) { return o.name; }).join(" ")).toLowerCase();
      return words.every(function (w) { return text.indexOf(w) > -1; });
    });
    list("‘" + esc(q) + "’ 검색 결과", hits);
  }

  function route() {
    if (!D) return;
    var q = $("#q").value.trim();
    var parts = location.hash.replace(/^#\/?/, "").split("/");
    if (q) { sideNav(""); return search(q); }
    if (parts[0] === "c" && parts[1]) {
      sideNav(parts[1]);
      list((ICONS[parts[1]] || "") + " " + esc(catName(parts[1])), D.groups.filter(function (g) { return g.cat === parts[1]; }), parts[2]);
      if (parts[2]) {
        var el = document.getElementById("g" + parts[2]);
        if (el) { el.scrollIntoView({ block: "start" }); el.classList.add("flash"); setTimeout(function () { el.classList.remove("flash"); }, 1600); }
      } else window.scrollTo(0, 0);
      return;
    }
    sideNav("home");
    home();
    window.scrollTo(0, 0);
  }

  // ---------- 동작 ----------
  var toastTimer;
  function toast(msg) {
    var t = $("#toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove("show"); }, 1500);
  }
  function copy(text) {
    var done = function () { toast("옵션명을 복사했어요"); };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () {});
  }

  main.addEventListener("click", function (e) {
    var th = e.target.closest(".thumb");
    if (th && th.dataset.big) {
      var v = $("#viewer");
      v.querySelector("img").src = th.dataset.big;
      v.showModal();
      return;
    }
    var on = e.target.closest(".oname");
    if (on) copy(on.firstChild.textContent.trim());
  });
  $("#viewer").addEventListener("click", function () { this.close(); });

  var qTimer;
  $("#q").addEventListener("input", function () { clearTimeout(qTimer); qTimer = setTimeout(route, 150); });
  window.addEventListener("hashchange", function () { $("#q").value = ""; showOut = false; route(); });

  fetch("data.json?v=" + Date.now()).then(function (r) { return r.json(); }).then(function (d) {
    D = d;
    D.groups.forEach(function (g) { byId[g.id] = g; });
    $("#updated").textContent = "업데이트 " + (D.updated || "");
    route();
  }).catch(function () {
    main.innerHTML = '<p class="none">상품 정보를 불러오지 못했어요. 잠시 후 새로고침 해 주세요.</p>';
  });
})();
