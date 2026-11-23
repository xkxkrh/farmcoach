(function () {
  "use strict";
  var ICONS = { "001": "🥬", "002": "🥩", "003": "🐟", "004": "🥢", "005": "🥫" };
  var LINK_ICONS = { blue: "🏬", green: "📘", yellow: "💬", dark: "📌", red: "📣" };
  var D = null, byId = {}, picked = [];
  var $ = function (s) { return document.querySelector(s); };
  var main = $("#main");

  // 비교 선택은 이 탭을 닫으면 지워짐 (새로고침에는 남음). 예전에 계속 남던 기록도 지움
  try { localStorage.removeItem("fc_compare"); } catch (e) {}
  try { picked = JSON.parse(sessionStorage.getItem("fc_compare") || "[]"); } catch (e) { picked = []; }
  function savePicked() { try { sessionStorage.setItem("fc_compare", JSON.stringify(picked)); } catch (e) {} }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function linkify(s) {
    return esc(s).replace(/https?:\/\/[^\s<]+/g, function (u) { return '<a href="' + u + '" target="_blank" rel="noopener">' + u + "</a>"; });
  }
  function won(n) { return Number(n || 0).toLocaleString("ko-KR") + "원"; }
  // big=true: 카드처럼 크게 보이는 곳은 원본(1000px) 사진, 작은 자리는 100px 미리보기 사진
  function img(g, big) {
    var src = big ? (g.big || g.img) : g.img;
    return src ? '<img src="' + esc(src) + '" alt="" loading="lazy" decoding="async">' : '<span class="noimg">사진 없음</span>';
  }
  // NEW: 상품그룹 등록일부터 2주. 2주 안에 새 상품이 하나도 없으면 가장 최근 2개 (목록은 최신순)
  var newIds = null;
  function isNew(g) {
    if (!newIds) {
      var since = new Date(); since.setHours(0, 0, 0, 0); since.setDate(since.getDate() - 14);
      var fresh = D.groups.filter(function (x) { return new Date(x.date.replace(" ", "T")) >= since; });
      if (!fresh.length) fresh = D.groups.slice(0, 2);
      newIds = fresh.map(function (x) { return x.id; });
    }
    return newIds.indexOf(g.id) > -1;
  }
  function catName(code) {
    for (var i = 0; i < D.categories.length; i++) if (D.categories[i].code === code) return D.categories[i].name;
    return "기타";
  }
  function minPrice(g) { return Math.min.apply(null, g.options.map(function (o) { return o.price; })); }
  function taxBadge(t) { return t === "면세" ? '<span class="b b-free">면세</span>' : t === "과세" ? '<span class="b b-tax">과세</span>' : t === "혼합" ? '<span class="b b-tax">과세·면세</span>' : ""; }

  // 최근 공급가 인상/인하: 바뀐 날을 1일째로 세어 평일 3일째까지만 보임 (주말은 세지 않음)
  function workdays(day) {
    var a = new Date(day + "T00:00:00"), b = new Date(), n = 0;
    b.setHours(0, 0, 0, 0);
    if (a > b) return 99;
    for (; a <= b && n < 4; a.setDate(a.getDate() + 1)) if (a.getDay() % 6) n++;
    return n;
  }
  function chgSign(o) {
    var sum = (o.chg || []).reduce(function (t, c) { return workdays(c[0]) <= 3 ? t + c[1] : t; }, 0);
    return sum > 0 ? 1 : sum < 0 ? -1 : 0;
  }
  function chgBadges(opts) {
    var s = opts.map(chgSign);
    return (s.indexOf(1) > -1 ? '<span class="b b-up">▲ 인상</span>' : "") + (s.indexOf(-1) > -1 ? '<span class="b b-down">▼ 인하</span>' : "");
  }

  // ---------- 바로가기 버튼 + 영상 ----------
  function linkButtons() {
    function one(l) {
      var c = l.color || "blue", m = l.label.match(/^(\p{Extended_Pictographic}\uFE0F?)\s*(.+)$/u);  // 이름 앞 그림글자가 있으면 그걸 아이콘으로
      return '<a class="lbtn ' + esc(c) + '" href="' + esc(l.url) + '" target="_blank" rel="noopener"><span class="i">' + (m ? m[1] : LINK_ICONS[c] || "🔗") +
        "</span>" + esc(m ? m[2] : l.label) + '<span class="go">›</span></a>';
    }
    var links = D.links || [];
    return links.filter(function (l) { return !l.last; }).map(one).join("") + (D.videos || []).map(function (v, i) {
      return '<button type="button" class="lbtn video" data-video="' + i + '"><span class="i">▶</span>' + esc(v.title) + '<span class="go">›</span></button>';
    }).join("") + links.filter(function (l) { return l.last; }).map(one).join("");
  }
  function playVideo(i) {
    var v = D.videos[i]; if (!v) return;
    $("#playerTitle").textContent = v.title;
    var el = $("#playerVideo"); el.src = v.file;
    chaps = chapters(v.chapters); curChap = -1;
    $("#player").classList.toggle("wide", !!chaps.length);
    $("#chapters").hidden = !chaps.length;
    $("#chapters").innerHTML = '<b class="ct">타임라인</b>' + chaps.map(function (c, k) {
      return '<button type="button" data-chap="' + k + '"><span>' + c.label + "</span>" + esc(c.title) + "</button>";
    }).join("");
    $("#player").showModal(); $("#chapters").scrollTop = 0; markChap();
    var p = el.play(); if (p && p.catch) p.catch(function () {});
  }
  // 타임라인: "0:28 1단계 엑셀 업로드" 처럼 적은 줄을 읽어서 누르면 그 장면으로
  var chaps = [], curChap = -1;
  function chapters(text) {
    return String(text || "").split("\n").map(function (l) {
      var m = l.trim().match(/^(?:(\d+):)?(\d{1,3}):(\d{2})\s+(.+)$/);
      return m && { t: (+m[1] || 0) * 3600 + m[2] * 60 + +m[3], label: (m[1] ? m[1] + ":" : "") + m[2] + ":" + m[3], title: m[4] };
    }).filter(Boolean).sort(function (a, b) { return a.t - b.t; });
  }
  function markChap() {   // 지금 나오는 장면을 진하게
    var t = $("#playerVideo").currentTime + 0.05, n = -1, box = $("#chapters");
    chaps.forEach(function (c, k) { if (c.t <= t) n = k; });
    if (n === curChap) return;
    curChap = n;
    box.querySelectorAll("[data-chap]").forEach(function (b, k) {
      b.classList.toggle("on", k === n);
      if (k === n) { b.setAttribute("aria-current", "true"); box.scrollTop = b.offsetTop - box.offsetTop - box.clientHeight / 2 + b.offsetHeight / 2; } else b.removeAttribute("aria-current");
    });
  }
  $("#playerVideo").addEventListener("timeupdate", markChap);
  $("#playerVideo").addEventListener("seeking", markChap);
  $("#chapters").addEventListener("click", function (e) {
    var b = e.target.closest("[data-chap]"); if (!b) return;
    var el = $("#playerVideo"), t = chaps[+b.dataset.chap].t;
    function go() { el.currentTime = t; var p = el.play(); if (p && p.catch) p.catch(function () {}); }
    if (el.readyState) go(); else { el.addEventListener("loadedmetadata", go, { once: true }); el.load(); }
  });
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
      '<section class="card notice"><h2 class="h">📢 공지사항</h2>' +
      (D.noticeHtml != null && window.FC_cleanHtml ? '<div class="body rich">' + FC_cleanHtml(D.noticeHtml) + "</div>" : '<div class="body">' + linkify(D.notice) + "</div>") +
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
        '</td><td class="pr">' + chgBadges([o]) + won(o.price) + "</td></tr>";
    }).join("");
    return '<article class="card pc' + (on ? " picked" : "") + '" id="g' + g.id + '">' +
      '<label class="pick"><input type="checkbox" data-pick="' + g.id + '"' + (on ? " checked" : "") + ' aria-label="비교에 담기"><span class="ck"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg></span><span class="cl">비교</span></label>' +
      '<div class="thumb">' + img(g, true) + "</div>" +
      '<div class="pb"><div class="badges">' + (isNew(g) ? '<span class="b b-new">NEW</span>' : "") + taxBadge(g.tax) + chgBadges(g.options) + "</div>" +
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
    measure();
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
    $("#cmpcount").textContent = picked.length === 1 ? "1개 선택 · 하나 더 고르세요" : picked.length + "개 선택 · 비교할 수 있어요";
    $("#cmpOpen").disabled = picked.length < 2;
    var b = main.querySelector("[data-cmp]"); if (b) b.textContent = "⚖ 비교하여보기 (" + picked.length + ")";
  }
  function openCompare() {
    if (picked.length < 2 && !$("#compare").open) {
      toast(picked.length ? "하나 더 고르면 비교할 수 있어요" : "비교할 상품의 '비교'를 먼저 체크해 주세요"); return;
    }
    var gs = picked.map(function (id) { return byId[id]; });
    function row(label, f) { return "<tr><th>" + label + "</th>" + gs.map(function (g) { return "<td>" + f(g) + "</td>"; }).join("") + "</tr>"; }
    var t = '<table class="cmpt"><tbody>' +
      row("사진", function (g) { return g.img ? '<img src="' + esc(g.big || g.img) + '" alt="">' : ""; }) +
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
    } else { sideNav("home"); home(); noticeColors(); window.scrollTo(0, 0); }
    updateCmp();
  }

  // 휴대폰: 따라오는 윗부분 높이를 재서 겹치지 않게 (글자 크기가 달라도)
  function measure() {
    var s = document.documentElement.style;
    s.setProperty("--top", document.querySelector(".top").offsetHeight + "px");
    s.setProperty("--side", document.querySelector(".side").offsetHeight + "px");
  }
  window.addEventListener("resize", measure);
  if (window.ResizeObserver) { var ro = new ResizeObserver(measure); ro.observe(document.querySelector(".top")); ro.observe(document.querySelector(".side")); }

  // ---------- 밝게/어둡게 ----------
  // 처음에는 휴대폰 설정을 따르고, 버튼을 누르면 그 선택을 기억함. 휴대폰 설정과 같아지면 다시 설정을 따라감
  var root = document.documentElement, sys = window.matchMedia("(prefers-color-scheme: dark)");
  function isDark() { return root.dataset.theme ? root.dataset.theme === "dark" : sys.matches; }
  function applyTheme() {
    var d = isDark(), label = d ? "밝은 화면으로 바꾸기" : "어두운 화면으로 바꾸기";
    root.classList.toggle("is-dark", d);
    $("#theme").title = label; $("#theme").setAttribute("aria-label", label);
    $('meta[name="theme-color"]').content = d ? "#1c211e" : "#ffffff";
    noticeColors();
  }
  $("#theme").addEventListener("click", function () {
    var t = isDark() ? "light" : "dark", same = (t === "dark") === sys.matches;
    if (same) delete root.dataset.theme; else root.dataset.theme = t;
    try { if (same) localStorage.removeItem("fc_theme"); else localStorage.setItem("fc_theme", t); } catch (e) {}
    applyTheme();
  });
  if (sys.addEventListener) sys.addEventListener("change", applyTheme); else if (sys.addListener) sys.addListener(applyTheme);

  // 공지에 직접 고른 글자색이 어두운 화면에서 안 보이면, 같은 계열의 밝은(또는 어두운) 색으로만 바꿔 보여 줌
  function rgb(v) { var m = /rgba?\(([^)]+)\)/.exec(v || ""), p = m && m[1].split(/[ ,/]+/).map(Number); return p && (p.length < 4 || p[3] > 0.5) ? p.slice(0, 3) : null; }
  function lum(c) { var v = c.map(function (x) { x /= 255; return x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; }
  function ratio(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
  function noticeColors() {
    var box = document.querySelector(".notice .rich"); if (!box) return;
    var els = [].slice.call(box.querySelectorAll("[style],font[color],a"));
    els.forEach(function (el) {   // 먼저 원래 색으로 되돌림
      if (el.dataset.c != null) { el.style.color = el.dataset.c; delete el.dataset.c; }
    });
    if (!isDark()) return;
    els.forEach(function (el) {
      var bg = null, n = el;
      for (; n && !bg; n = n.parentElement) bg = rgb(getComputedStyle(n).backgroundColor);
      var c = rgb(getComputedStyle(el).color);
      if (!c || !bg || ratio(c, bg) >= 4.5) return;
      var to = ratio([255, 255, 255], bg) >= ratio([0, 0, 0], bg) ? 255 : 0, k, x = c;
      for (k = 1; k <= 20 && ratio(x, bg) < 4.5; k++) x = c.map(function (v) { return Math.round(v + (to - v) * k / 20); });
      el.dataset.c = el.style.color; el.style.color = "rgb(" + x.join(",") + ")";
    });
  }
  applyTheme();

  // 삼성 인터넷은 사이트 색 위에 어두운 색을 덧칠하는 설정이 있음 (사이트에서는 켜졌는지 알 수 없음). 한 번만 안내
  var tipSeen = false;
  try { tipSeen = !!localStorage.getItem("fc_tip"); } catch (e) {}
  $("#tip").hidden = tipSeen || !/SamsungBrowser\//.test(navigator.userAgent);
  $("#tipOk").addEventListener("click", function () { $("#tip").hidden = true; try { localStorage.setItem("fc_tip", "1"); } catch (e) {} });

  // ---------- 동작 ----------
  var toastTimer;
  function toast(msg) {
    var t = $("#toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.classList.remove("show"); }, 1600);
  }
  document.addEventListener("click", function (e) {
    // 검색 중에 메뉴를 누르면 검색을 지우고 그 메뉴로 (같은 메뉴라 주소가 안 바뀌어도)
    var nav = e.target.closest('a[href^="#/"]');
    if (nav && !e.ctrlKey && !e.metaKey && !e.shiftKey && $("#q").value) {
      $("#q").value = ""; clearTimeout(qTimer);
      if ((location.hash || "#/") === nav.getAttribute("href")) { e.preventDefault(); route(); }
      return;
    }
    var v = e.target.closest("[data-video]"); if (v) { playVideo(+v.dataset.video); return; }
    var dr = e.target.closest("[data-drop]"); if (dr) { toggleDrop(dr.dataset.drop); return; }
    if (e.target.closest("[data-cmp]") || e.target.closest("#cmpOpen")) { openCompare(); return; }
    if (e.target.closest("#cmpClear")) {
      // 화면을 다시 그리지 않고 체크만 풀어서, 보던 스크롤 위치가 그대로 남게 함
      picked = [];
      main.querySelectorAll("[data-pick]").forEach(function (cb) { cb.checked = false; });
      main.querySelectorAll(".pc.picked").forEach(function (c) { c.classList.remove("picked"); });
      updateCmp(); return;
    }
    var un = e.target.closest("[data-unpick]");
    if (un) {
      picked = picked.filter(function (id) { return id !== un.dataset.unpick; });
      var cb = main.querySelector('[data-pick="' + un.dataset.unpick + '"]');
      if (cb) { cb.checked = false; cb.closest(".pc").classList.remove("picked"); }
      updateCmp(); if (picked.length) openCompare(); else $("#compare").close(); return;
    }
    var x = e.target.closest(".x"); if (x) { x.closest("dialog").close(); return; }
    var on = e.target.closest(".oname");
    if (on && navigator.clipboard) navigator.clipboard.writeText(on.firstChild.textContent.trim()).then(function () { toast("옵션명을 복사했어요"); }, function () { toast("복사하지 못했어요. 글자를 길게 눌러 복사해 주세요"); });
  });
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
