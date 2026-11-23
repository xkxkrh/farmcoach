(function () {
  "use strict";
  var $ = function (s, el) { return (el || document).querySelector(s); };
  var RAW = null, E = null, OPT = {}, CATS = [], sel = null, saveTimer = null;
  var FIELDS = [
    ["name", "상품그룹명", "wide"], ["cat", "카테고리", ""], ["ship", "기본 배송비", ""],
    ["jeju", "제주도 택배비", ""], ["island", "도서산간 택배비", ""],
    ["origin", "원산지 (비우면 비고에서 자동)", ""], ["link", "상세페이지 링크", "wide"], ["img", "썸네일 사진 주소", "wide"], ["note", "비고 (원산지·기타 안내)", "wide"]
  ];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function linkify(s) { return esc(s).replace(/https?:\/\/[^\s<]+/g, function (u) { return '<a href="' + u + '" target="_blank">' + u + "</a>"; }); }
  function toast(msg, err) {
    var t = $("#toast"); t.textContent = msg; t.className = "toast show" + (err ? " err" : "");
    clearTimeout(t._t); t._t = setTimeout(function () { t.className = "toast"; }, err ? 6000 : 2500);
  }
  function api(path, body) {
    return fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) { return r.json(); });
  }
  function lost() { toast("프로그램과 연결이 끊겼어요. 런처에서 '실행'을 다시 눌러 주세요.", true); }
  function catName(c) { var x = CATS.filter(function (k) { return k.code === c; })[0]; return x ? x.name : "미지정"; }

  // ---------- 상태 계산 (build.py와 같은 규칙) ----------
  function ge(id) { return E.groups[id] || {}; }
  function gval(g, k) { var e = ge(g.id); return k in e ? e[k] : (g[k] || ""); }
  function gSoldout(g) { var st = ge(g.id).status || "auto"; return st === "auto" ? g.soldout : st === "soldout"; }
  function gHidden(g) { var v = ge(g.id).visible || "auto"; return v === "hide" || (v === "auto" && g.restricted); }
  function gEdited(g) {
    if (Object.keys(ge(g.id)).length) return true;
    return g.options.some(function (o) { return E.options[o] && Object.keys(E.options[o]).length; });
  }

  // ---------- 저장 ----------
  function save() {
    $("#saved").textContent = "저장 중…";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function () {
      api("/api/edits", E).then(function () { $("#saved").textContent = "✓ 자동 저장됨 (" + new Date().toLocaleTimeString("ko-KR") + ")"; })
        .catch(function () { $("#saved").textContent = "⚠ 저장 못 함"; lost(); });
    }, 500);
  }
  function setEdit(bucket, id, key, value, original) {
    var o = E[bucket][id] || (E[bucket][id] = {});
    if (value === original || value === "auto" || value === false) delete o[key]; else o[key] = value;
    if (!Object.keys(o).length) delete E[bucket][id];
    save();
  }

  // ---------- 누르는 중에는 화면을 다시 그리지 않기 ----------
  // 칸을 고친 직후 다른 것을 누르면, 누르는 도중 화면이 다시 그려져 첫 클릭이 사라지던 문제를 막음
  var mouseDown = false, waitList = false, waitEdit = false, drawing = false;
  function flush() {
    if (mouseDown) return;
    if (waitList) { waitList = false; renderList(); }
    var a = document.activeElement;
    if (waitEdit && !(a && a.tagName === "SELECT" && $("#gedit").contains(a))) { waitEdit = false; renderEdit(); }  // 목록상자를 펼친 중이면 기다림
  }
  function release() { mouseDown = false; setTimeout(flush, 0); }
  document.addEventListener("mousedown", function (e) { mouseDown = e.button === 0; }, true);
  document.addEventListener("mouseup", release, true);
  document.addEventListener("dragend", release, true);
  document.addEventListener("keydown", function () { mouseDown = false; }, true);
  document.addEventListener("change", function (e) { if (e.target.tagName === "SELECT") mouseDown = false; }, true);
  window.addEventListener("blur", release);

  // ---------- 상품 목록 ----------
  function renderList() {
    if (mouseDown) { waitList = true; return; }
    if (!RAW) { $("#glist").innerHTML = '<p class="hint" style="padding:16px">아직 불러온 상품이 없어요.<br>위의 <b>⟳ 팜코치에서 불러오기</b>를 눌러 주세요.</p>'; return; }
    var q = $("#fq").value.trim().toLowerCase(), c = $("#fcat").value, st = $("#fst").value;
    var rows = RAW.groups.slice().sort(function (a, b) { return a.date < b.date ? 1 : -1; }).filter(function (g) {
      if (c && gval(g, "cat") !== c) return false;
      if (st === "sale" && (gSoldout(g) || gHidden(g))) return false;
      if (st === "out" && !gSoldout(g)) return false;
      if (st === "hidden" && !gHidden(g)) return false;
      if (st === "edited" && !gEdited(g)) return false;
      if (q) {
        var t = (gval(g, "name") + " " + g.options.map(function (o) { return OPT[o] ? OPT[o].name : ""; }).join(" ")).toLowerCase();
        if (t.indexOf(q) < 0) return false;
      }
      return true;
    });
    $("#glist").innerHTML = rows.map(function (g) {
      var im = gval(g, "img");
      return '<div class="gi' + (sel === g.id ? " on" : "") + '" data-id="' + g.id + '">' +
        (im ? '<img src="' + esc(im) + '" loading="lazy" alt="">' : '<span class="ni"></span>') +
        '<div><div class="n">' + esc(gval(g, "name")) + '</div><div class="m">' + esc(catName(gval(g, "cat"))) + " · " + esc(g.date.slice(0, 10)) + " " +
        (gSoldout(g) ? '<span class="tag out">품절</span>' : '<span class="tag sale">판매중</span>') +
        (gHidden(g) ? '<span class="tag hide">사이트에 안 보임</span>' : "") +
        (gEdited(g) ? '<span class="tag ed">고침</span>' : "") + "</div></div></div>";
    }).join("") || '<p class="hint" style="padding:16px">조건에 맞는 상품이 없어요.' +
      (st === "out" || st === "hidden" ? "<br>다른 PC에서 받은 자료에는 판매중인 상품만 들어 있어요. <b>⟳ 팜코치에서 불러오기</b>를 누르면 이 PC에서 전체를 볼 수 있어요." : "") + "</p>";
  }

  // ---------- 상품 편집 ----------
  function field(g, k, label, cls) {
    var e = ge(g.id), edited = k in e, v = edited ? e[k] : (g[k] || ""), orig = g[k] || "";
    var input;
    if (k === "cat") {
      input = '<select data-k="cat">' + CATS.map(function (c) { return '<option value="' + c.code + '"' + (c.code === v ? " selected" : "") + ">" + esc(c.name) + "</option>"; }).join("") + "</select>";
    } else if (k === "note") {
      input = '<textarea data-k="note" rows="6">' + esc(v) + "</textarea>";
    } else {
      input = '<input data-k="' + k + '" value="' + esc(v) + '">';
    }
    return '<label class="f ' + cls + (edited ? " edited" : "") + '"><span>' + label +
      (edited ? ' <button type="button" class="reset" data-reset="' + k + '">원래대로</button>' : "") + "</span>" + input +
      (edited ? '<span class="orig">팜코치 원래 값: ' + esc(k === "cat" ? catName(orig) : (orig || "(비어있음)")).slice(0, 120) + "</span>" : "") + "</label>";
  }

  function renderEdit() {
    if (mouseDown) { waitEdit = true; return; }
    // 다시 그려도 커서가 있던 칸을 기억했다가 돌려놓음
    var a = document.activeElement, keep = null;
    if (a && $("#gedit").contains(a)) {
      var tr = a.closest("tr");
      keep = (a.dataset.k ? '[data-k="' + a.dataset.k + '"]' : a.dataset.ok ? 'tr[data-o="' + (tr && tr.dataset.o) + '"] [data-ok="' + a.dataset.ok + '"]' : null);
    }
    var from = null, to = null;
    if (keep) try { from = a.selectionStart; to = a.selectionEnd; } catch (e) {}
    waitEdit = false; drawing = true;      // 다시 그릴 때 생기는 '칸에서 나감' 신호는 무시 (끝없이 다시 그려지던 문제)
    drawEdit();
    drawing = false;
    if (keep) {
      var n = $("#gedit " + keep);
      if (n) { n.focus({ preventScroll: true }); if (from != null) try { n.setSelectionRange(from, to); } catch (e) {} }  // 커서 자리도 그대로
    }
  }
  function drawEdit() {
    var g = RAW && RAW.groups.filter(function (x) { return x.id === sel; })[0];
    var box = $("#gedit");
    if (!g) { box.innerHTML = '<p class="hint">왼쪽에서 상품을 고르세요.</p>'; return; }
    var e = ge(g.id), im = gval(g, "img");
    var h = '<div class="ghead">' + (im ? '<img src="' + esc(im) + '" alt="">' : "") + '<div><h2>' + esc(gval(g, "name")) + "</h2>" +
      '<div class="meta">등록일 ' + esc(g.date) + " · 팜코치 상태: <b>" + (g.soldout ? "품절(노출안함)" : "판매중(노출)") + "</b>" +
      (g.restricted ? ' · <b style="color:#cf3b3b">특정 거래처 전용 상품</b>' : "") + "</div></div></div>";
    h += '<div class="grid">' +
      '<label class="f"><span>셀러 사이트에 보이기</span><select data-k="visible">' +
      opt("auto", "자동" + (g.restricted ? " (거래처 전용이라 숨김)" : " (보임)"), e.visible) + opt("show", "항상 보이기", e.visible) + opt("hide", "숨기기", e.visible) + "</select></label>" +
      '<label class="f"><span>판매 상태</span><select data-k="status">' +
      opt("auto", "자동 (팜코치 따라감: " + (g.soldout ? "품절" : "판매중") + ")", e.status) + opt("sale", "판매중으로 표시", e.status) + opt("soldout", "품절로 표시", e.status) + "</select></label>" +
      FIELDS.map(function (f) { return field(g, f[0], f[1], f[2]); }).join("") + "</div>";
    h += '<div class="sec">옵션 (' + g.options.length + '개)</div><table class="ot"><thead><tr><th>옵션명</th><th class="w-price">공급가</th><th class="w-st">상태</th><th class="w-h">숨김</th></tr></thead><tbody>' +
      g.options.map(function (oid) {
        var o = OPT[oid]; if (!o) return "";
        var oe = E.options[oid] || {};
        return '<tr data-o="' + oid + '"><td class="' + ("name" in oe ? "e" : "") + '"><input data-ok="name" value="' + esc("name" in oe ? oe.name : o.name) + '">' +
          ("name" in oe ? '<div class="orig">원래: ' + esc(o.name) + "</div>" : "") + "</td>" +
          '<td class="' + ("price" in oe ? "e" : "") + '"><input data-ok="price" type="number" value="' + ("price" in oe ? oe.price : o.price) + '">' +
          ("price" in oe ? '<div class="orig">원래: ' + o.price.toLocaleString() + "</div>" : "") + "</td>" +
          '<td class="' + (oe.status ? "e" : "") + '"><select data-ok="status">' + opt("auto", "자동 (" + (o.soldout ? "품절" : "판매중") + ")", oe.status) +
          opt("sale", "판매중", oe.status) + opt("soldout", "품절", oe.status) + "</select></td>" +
          '<td class="w-h"><input type="checkbox" data-ok="hidden"' + (oe.hidden ? " checked" : "") + "></td></tr>";
      }).join("") + "</tbody></table>" +
      '<p class="hint">노란색 칸은 내가 고친 곳이에요. 다음에 팜코치에서 다시 불러와도 고친 내용은 그대로 남아요.</p>';
    box.innerHTML = h;
  }
  function opt(v, label, cur) { return '<option value="' + v + '"' + ((cur || "auto") === v ? " selected" : "") + ">" + esc(label) + "</option>"; }

  $("#gedit").addEventListener("change", onEdit);
  $("#gedit").addEventListener("input", function (ev) { if (ev.target.matches("input:not([type=checkbox]),textarea")) onEdit(ev, true); });
  function onEdit(ev, typing) {
    var t = ev.target, g = RAW.groups.filter(function (x) { return x.id === sel; })[0];
    if (!g) return;
    if (t.dataset.k) {
      var k = t.dataset.k;
      setEdit("groups", g.id, k, t.value, (k === "visible" || k === "status") ? "auto" : (g[k] || ""));
    } else if (t.dataset.ok) {
      var oid = t.closest("tr").dataset.o, o = OPT[oid], ok = t.dataset.ok;
      var v = ok === "hidden" ? t.checked : ok === "price" ? Number(t.value || 0) : t.value;
      setEdit("options", oid, ok, v, ok === "status" ? "auto" : ok === "hidden" ? false : o[ok]);
    } else return;
    renderList();
    if (!typing) renderEdit();
  }
  $("#gedit").addEventListener("focusout", function (ev) {
    if (drawing || !ev.target.matches("input,textarea,select")) return;
    if (!ev.target.matches("select")) waitEdit = true;
    setTimeout(flush, 0); // 다음 칸으로 커서가 옮겨간 뒤에 다시 그림
  });
  $("#gedit").addEventListener("click", function (ev) {
    var r = ev.target.closest("[data-reset]");
    if (!r) return;
    ev.preventDefault();
    delete E.groups[sel][r.dataset.reset];
    if (!Object.keys(E.groups[sel]).length) delete E.groups[sel];
    save(); renderEdit(); renderList();
  });
  $("#glist").addEventListener("click", function (ev) {
    var it = ev.target.closest(".gi"); if (!it) return;
    sel = it.dataset.id; renderList(); renderEdit();
  });
  ["#fq", "#fcat", "#fst"].forEach(function (s) { $(s).addEventListener("input", renderList); });

  // ---------- 공지사항 + 바로가기 버튼 ----------
  var COLORS = [["blue", "파랑"], ["green", "초록"], ["yellow", "노랑"], ["dark", "검정"], ["red", "빨강"]];
  function renderNotice() {
    $("#noticePrev").innerHTML = FC_cleanHtml(E.noticeHtml != null ? E.noticeHtml : FC_textToHtml(E.notice));
    function one(l) {
      return '<a class="lbtn ' + esc(l.color || "blue") + '" href="' + esc(l.url) + '" target="_blank">' + esc(l.label) + " ›</a>";
    }
    var links = (E.links || []).filter(function (l) { return l.label; });
    $("#linkPrev").innerHTML = links.filter(function (l) { return !l.last; }).map(one).join("") + (E.videos || []).map(function (v) { return '<a class="lbtn dark" href="/site/' + esc(v.file) + '" target="_blank">▶ ' + esc(v.title) + "</a>"; }).join("") +
      links.filter(function (l) { return l.last; }).map(one).join("");
  }
  function renderLinks() {
    E.links = E.links || [];
    $("#linkList").innerHTML = E.links.map(function (l, i) {
      return '<div class="lrow" data-i="' + i + '"><input data-f="label" placeholder="버튼 글자 (예: 입점사이트 안내)" value="' + esc(l.label) + '">' +
        '<input data-f="url" placeholder="https://..." value="' + esc(l.url) + '">' +
        '<select data-f="color">' + COLORS.map(function (c) { return '<option value="' + c[0] + '"' + ((l.color || "blue") === c[0] ? " selected" : "") + ">" + c[1] + "</option>"; }).join("") + "</select>" +
        '<span><label title="체크하면 영상 버튼보다 뒤(맨 끝)에 나와요"><input type="checkbox" data-last' + (l.last ? " checked" : "") + '> 맨 뒤</label> <button class="btn sm" data-mv="-1"' + (i ? "" : " disabled") + '>▲</button> <button class="btn sm" data-mv="1"' + (i === E.links.length - 1 ? " disabled" : "") + '>▼</button> <button class="btn sm" data-del>삭제</button></span></div>';
    }).join("") || '<p class="hint">버튼이 없어요.</p>';
    renderNotice();
  }
  // ---- 서식 있는 공지 편집기 (메모장처럼) ----
  var ed = $("#noticeEd");
  try { document.execCommand("defaultParagraphSeparator", false, "div"); } catch (e) {}  // 엔터 = 새 줄(div)
  var COLOR = { foreColor: "#e11d48", hiliteColor: "#fde047" };

  // 줄이 <div> 로 나뉘어 있지 않은 부분(글자, <b>, <br> 로만 이어진 부분)을 한 줄씩 <div> 로 감쌈.
  // 이렇게 해야 '제목', '목록', '정렬'이 고른 줄에만 정확히 적용됨.
  var BLOCK = /^(DIV|P|H1|H2|H3|UL|OL|TABLE|HR|BLOCKQUOTE)$/;
  function normalize() {
    var kids = [].slice.call(ed.childNodes), line = null, changed = false;
    kids.forEach(function (n) {
      if (n.nodeType === 1 && BLOCK.test(n.tagName)) { line = null; return; }
      if (n.nodeType === 1 && n.tagName === "BR") {
        if (!line) { line = document.createElement("div"); ed.insertBefore(line, n); }
        if (!line.childNodes.length) line.appendChild(document.createElement("br"));
        n.remove(); line = null; changed = true; return;
      }
      if (n.nodeType === 3 && !n.nodeValue.trim() && !line) { if (n.nodeValue.indexOf("\n") > -1) n.remove(); return; }
      if (!line) { line = document.createElement("div"); ed.insertBefore(line, n); }
      line.appendChild(n); changed = true;
    });
    return changed;
  }
  function edChanged() {
    E.noticeHtml = FC_cleanHtml(ed.innerHTML);
    E.notice = ed.innerText;            // 글자만 있는 예비본 (검색·예전 화면용)
    renderNotice(); save(); edState();
  }
  function edState() {                   // 지금 커서 위치의 굵게/기울임 등 버튼 켜짐 표시
    document.querySelectorAll("#rtBar button[data-cmd]").forEach(function (b) {
      var on = false;
      if (/^(bold|italic|underline|strikeThrough|insertUnorderedList|insertOrderedList|justifyLeft|justifyCenter)$/.test(b.dataset.cmd)) {
        try { on = document.queryCommandState(b.dataset.cmd); } catch (e) {}
      }
      b.classList.toggle("on", !!on);
    });
  }
  // 고른 글자(선택 영역)를 항상 기억 → 도구 버튼·목록상자·색 고르기를 눌러도 잃어버리지 않음
  var savedRange = null;
  document.addEventListener("selectionchange", function () {
    var s = window.getSelection();
    if (s.rangeCount && ed.contains(s.getRangeAt(0).commonAncestorContainer)) { savedRange = s.getRangeAt(0).cloneRange(); edState(); }
  });
  function restoreSel() {
    ed.focus();
    var s = window.getSelection();
    if (savedRange && ed.contains(savedRange.commonAncestorContainer)) { s.removeAllRanges(); s.addRange(savedRange); }
    else { var r = document.createRange(); r.selectNodeContents(ed); r.collapse(false); s.removeAllRanges(); s.addRange(r); }
  }
  // 선택 영역을 '몇 번째 글자부터 몇 번째 글자까지'로 바꿔 두었다가 되살림 (줄 정리로 모양이 바뀌어도 안 잃어버림)
  function textPos(node, off) {
    var w = document.createTreeWalker(ed, NodeFilter.SHOW_TEXT), n, count = 0;
    if (node.nodeType !== 3) {               // 글자 사이가 아니라 요소 사이를 가리키는 경우
      var r = document.createRange(); r.selectNodeContents(ed); r.setEnd(node, off);
      return r.toString().length;
    }
    while ((n = w.nextNode())) { if (n === node) return count + off; count += n.nodeValue.length; }
    return count;
  }
  function posToPoint(pos, isStart) {
    // 시작점이 줄 끝/다음 줄 처음 경계에 있으면 '다음 줄 처음'으로 잡아야 윗줄이 딸려오지 않음
    var w = document.createTreeWalker(ed, NodeFilter.SHOW_TEXT), n, last = null;
    while ((n = w.nextNode())) {
      var L = n.nodeValue.length;
      if (isStart ? pos < L : pos <= L) return [n, pos];
      pos -= L; last = n;
    }
    return last ? [last, last.nodeValue.length] : [ed, ed.childNodes.length];
  }
  function run(cmd, val) {
    restoreSel();
    if (/^(formatBlock|insertUnorderedList|insertOrderedList|justifyLeft|justifyCenter)$/.test(cmd)) {
      var s0 = window.getSelection().getRangeAt(0);
      var a = textPos(s0.startContainer, s0.startOffset), z = textPos(s0.endContainer, s0.endOffset);
      if (normalize()) {
        var p1 = posToPoint(a, a < z), p2 = posToPoint(z, false), rr = document.createRange();
        rr.setStart(p1[0], p1[1]); rr.setEnd(p2[0], p2[1]);
        var ss = window.getSelection(); ss.removeAllRanges(); ss.addRange(rr); savedRange = rr.cloneRange();
      }
    }
    if (cmd === "removeFormat") {          // 목록·제목·정렬·링크까지 모두 지움
      normalize();
      ["insertUnorderedList", "insertOrderedList"].forEach(function (c) { if (document.queryCommandState(c)) document.execCommand(c); });
      document.execCommand("formatBlock", false, "DIV");
      document.execCommand("justifyLeft");
      document.execCommand("unlink");
    }
    document.execCommand("styleWithCSS", false, cmd === "hiliteColor" || cmd === "foreColor");
    var ok = document.execCommand(cmd, false, val == null ? null : val);
    if (!ok && cmd === "hiliteColor") ok = document.execCommand("backColor", false, val);
    var s = window.getSelection(); if (s.rangeCount) savedRange = s.getRangeAt(0).cloneRange();
    edChanged();
    if (!ok) toast("이 서식은 지금 위치에 적용할 수 없어요. 글자를 다시 골라 주세요.", true);
  }
  ed.addEventListener("input", edChanged);
  ed.addEventListener("paste", function (e) {           // 붙여넣기는 글자만 (이상한 서식 방지)
    e.preventDefault();
    var t = (e.clipboardData || window.clipboardData).getData("text/plain");
    document.execCommand("insertText", false, t);
  });
  // 도구를 눌러도 글 상자에서 커서가 빠지지 않게
  $("#rtBar").addEventListener("mousedown", function (e) { if (e.target.closest("button")) e.preventDefault(); });
  $("#rtBar").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    if (b.dataset.cmd) return run(b.dataset.cmd);
    if (b.dataset.color) return run(b.dataset.color, COLOR[b.dataset.color]);   // 색 버튼: 지금 색으로 바로 칠함
    if (b.dataset.act === "link") {
      var had = savedRange && !savedRange.collapsed;
      var url = prompt("연결할 주소를 넣어 주세요 (https://…)", "https://");
      if (!url || url === "https://") return;
      if (!/^(https?:|mailto:|tel:)/i.test(url)) url = "https://" + url;
      if (had) run("createLink", url);
      else run("insertHTML", '<a href="' + url.replace(/"/g, "%22") + '">' + esc(url) + "</a>&nbsp;");
    } else if (b.dataset.act === "table") {
      var r = parseInt(prompt("줄(가로줄) 수", "3"), 10), c = parseInt(prompt("칸(세로칸) 수", "2"), 10);
      if (!(r > 0 && c > 0 && r <= 30 && c <= 10)) return;
      var h = "<table><tbody>";
      for (var i = 0; i < r; i++) { h += "<tr>"; for (var j = 0; j < c; j++) h += "<td>&nbsp;</td>"; h += "</tr>"; }
      run("insertHTML", h + "</tbody></table><div><br></div>");
    } else if (b.dataset.act === "hr") run("insertHTML", "<hr><div><br></div>");
  });
  $("#rtBar").addEventListener("change", function (e) {
    var t = e.target;
    if (t.dataset.pick) {                                   // ▾ 로 새 색을 고르면 그 색을 기억하고 바로 칠함
      COLOR[t.dataset.pick] = t.value; paintSwatches();
      return run(t.dataset.pick, t.value);
    }
    if (t.tagName === "SELECT" && t.dataset.cmd) {
      var v = t.value; t.value = "";
      if (!v) return;
      run(t.dataset.cmd, t.dataset.cmd === "formatBlock" ? v : v);
    }
  });
  $("#rtBar").addEventListener("input", function (e) {   // 색 고르는 중에도 미리 보여주기
    var t = e.target; if (!t.dataset.pick) return;
    COLOR[t.dataset.pick] = t.value; paintSwatches();
  });
  function paintSwatches() { $("#fcSw").style.borderBottomColor = COLOR.foreColor; $("#bcSw").style.background = COLOR.hiliteColor; }
  $("#linkAdd").onclick = function () { E.links.push({ label: "", url: "", color: "blue" }); renderLinks(); save(); };
  $("#linkList").addEventListener("input", function (ev) {
    var r = ev.target.closest(".lrow"); if (!r || !ev.target.dataset.f) return;
    E.links[+r.dataset.i][ev.target.dataset.f] = ev.target.value.trim(); renderNotice(); save();
  });
  $("#linkList").addEventListener("change", function (ev) {
    if (!ev.target.hasAttribute("data-last")) return;
    var l = E.links[+ev.target.closest(".lrow").dataset.i];
    if (ev.target.checked) l.last = true; else delete l.last;
    renderNotice(); save();
  });
  $("#linkList").addEventListener("click", function (ev) {
    var b = ev.target.closest("button"); if (!b) return;
    var i = +b.closest(".lrow").dataset.i;
    if (b.hasAttribute("data-del")) { if (!confirm("이 버튼을 지울까요?")) return; E.links.splice(i, 1); }
    else { var j = i + Number(b.dataset.mv); if (j < 0 || j >= E.links.length) return; var t = E.links[i]; E.links[i] = E.links[j]; E.links[j] = t; }
    renderLinks(); save();
  });

  // ---------- 영상 ----------
  function renderVideos() {
    E.videos = E.videos || [];
    $("#videoList").innerHTML = E.videos.map(function (v, i) {
      return '<div class="vrow" data-i="' + i + '"><video src="/site/' + esc(v.file) + '" controls preload="metadata"></video>' +
        '<div><label class="f"><span>버튼 이름</span><input class="vt" value="' + esc(v.title) + '"></label><p class="hint">' + esc(v.file) + "</p></div>" +
        '<span><button class="btn sm" data-mv="-1"' + (i ? "" : " disabled") + '>▲</button> <button class="btn sm" data-mv="1"' + (i === E.videos.length - 1 ? " disabled" : "") + '>▼</button> <button class="btn sm" data-del>삭제</button></span></div>';
    }).join("") || '<p class="hint">아직 넣은 영상이 없어요.</p>';
    renderNotice();
  }
  $("#videoList").addEventListener("input", function (ev) {
    if (!ev.target.classList.contains("vt")) return;
    E.videos[+ev.target.closest(".vrow").dataset.i].title = ev.target.value; renderNotice(); save();
  });
  $("#videoList").addEventListener("click", function (ev) {
    var b = ev.target.closest("button"); if (!b) return;
    var i = +b.closest(".vrow").dataset.i;
    if (b.hasAttribute("data-del")) {
      if (!confirm("이 영상을 지울까요? (사이트에 올리기를 누르면 셀러 사이트에서도 사라져요)")) return;
      var gone = E.videos.splice(i, 1)[0];
      api("/api/video-delete", { file: gone.file });
    } else { var j = i + Number(b.dataset.mv); if (j < 0 || j >= E.videos.length) return; var t = E.videos[i]; E.videos[i] = E.videos[j]; E.videos[j] = t; }
    renderVideos(); save();
  });
  $("#videoFile").addEventListener("change", function () {
    var f = this.files[0]; this.value = "";
    if (!f) return;
    if (f.size > 90e6) { toast("영상이 너무 커요 (" + Math.round(f.size / 1e6) + "MB). 90MB 이하로 줄여 주세요.", true); return; }
    $("#busy").hidden = false; $("#busyMsg").textContent = "영상 넣는 중… (" + Math.round(f.size / 1e6) + "MB)"; $("#busyBar").style.width = "50%";
    fetch("/api/video", { method: "POST", headers: { "X-Filename": encodeURIComponent(f.name) }, body: f })
      .then(function (r) { return r.json(); }).then(function (r) {
        $("#busy").hidden = true;
        if (!r.ok) return toast(r.msg, true);
        E.videos.push({ title: f.name.replace(/\.[^.]+$/, ""), file: r.file });
        renderVideos(); save(); toast("영상을 넣었어요. 버튼 이름을 확인해 주세요.");
      }).catch(function () { $("#busy").hidden = true; toast("영상 넣기 실패", true); });
  });

  // ---------- MD추천 (저장하기를 눌러야 적용) ----------
  var MDD = [], mdDirty = false;
  function mdMark(d) {
    mdDirty = d;
    $("#mdState").textContent = d ? "● 저장 안 된 변경이 있어요. '저장하기'를 눌러 주세요." : "✓ 저장됨";
    $("#mdState").className = "hint" + (d ? " dirty" : "");
  }
  function groupById(id) { return RAW && RAW.groups.filter(function (g) { return g.id === id; })[0]; }
  function groupLabel(g) { return gval(g, "name") + "  [" + g.id + "]"; }
  function renderMD() {
    if (RAW) {
      $("#groupNames").innerHTML = RAW.groups.filter(function (g) { return !gHidden(g) && !gSoldout(g); })
        .sort(function (a, b) { return a.date < b.date ? 1 : -1; })
        .map(function (g) { return '<option value="' + esc(groupLabel(g)) + '">'; }).join("");
    }
    $("#mdList").innerHTML = MDD.map(function (p, i) {
      var g = groupById(p.g), im = g && gval(g, "img");
      return '<div class="mdc" data-i="' + i + '">' + (im ? '<img src="' + esc(im) + '" alt="">' : '<span class="ni"></span>') +
        '<div><input list="groupNames" class="mdg" placeholder="상품 이름을 입력해서 고르세요" value="' + (g ? esc(groupLabel(g)) : "") + '">' +
        (g ? '<div class="opts">' + g.options.map(function (oid) {
          var o = OPT[oid]; if (!o) return "";
          return '<label><input type="checkbox" class="mdo" value="' + oid + '"' + (p.o.indexOf(oid) > -1 ? " checked" : "") + ">" + esc(o.name) + " (" + o.price.toLocaleString() + "원)</label>";
        }).join("") + "</div>" : "") +
        '<textarea class="mdt" rows="2" placeholder="추천 문구 (예: 이번 주 최저가! 당도 보장)">' + esc(p.text) + "</textarea>" +
        (g && gSoldout(g) ? '<p class="hint" style="color:#cf3b3b">⚠ 지금 품절이라 셀러 사이트에는 안 나와요.</p>' : "") + "</div>" +
        '<div class="ctl"><button class="btn sm" data-mv="-1"' + (i ? "" : " disabled") + '>▲</button><button class="btn sm" data-mv="1"' + (i === MDD.length - 1 ? " disabled" : "") + '>▼</button><button class="btn sm" data-del>삭제</button></div></div>';
    }).join("") || '<p class="hint">아직 추천 상품이 없어요.</p>';
  }
  $("#mdAdd").onclick = function () { MDD.push({ g: "", o: [], text: "" }); renderMD(); mdMark(true); };
  $("#mdSave").onclick = function () {
    E.md = JSON.parse(JSON.stringify(MDD.filter(function (p) { return p.g; })));
    MDD = JSON.parse(JSON.stringify(E.md));
    save(); renderMD(); mdMark(false); toast("MD추천을 저장했어요. '사이트에 올리기'를 누르면 셀러 사이트에 나와요.");
  };
  $("#mdList").addEventListener("change", function (ev) {
    var c = ev.target.closest(".mdc"); if (!c) return;
    var p = MDD[+c.dataset.i];
    if (ev.target.classList.contains("mdg")) {
      var m = ev.target.value.match(/\[(\d+)\]\s*$/);
      p.g = m ? m[1] : ""; p.o = [];
      if (!m) toast("목록에서 상품을 골라 주세요", true);
      renderMD();
    } else if (ev.target.classList.contains("mdo")) {
      p.o = Array.prototype.map.call(c.querySelectorAll(".mdo:checked"), function (x) { return x.value; });
    }
    mdMark(true);
  });
  $("#mdList").addEventListener("input", function (ev) {
    if (!ev.target.classList.contains("mdt")) return;
    MDD[+ev.target.closest(".mdc").dataset.i].text = ev.target.value; mdMark(true);
  });
  $("#mdList").addEventListener("click", function (ev) {
    var b = ev.target.closest("button"); if (!b) return;
    var i = +b.closest(".mdc").dataset.i;
    if (b.hasAttribute("data-del")) { if (!confirm("이 추천 상품을 지울까요?")) return; MDD.splice(i, 1); }
    else { var j = i + Number(b.dataset.mv); if (j < 0 || j >= MDD.length) return; var t = MDD[i]; MDD[i] = MDD[j]; MDD[j] = t; }
    renderMD(); mdMark(true);
  });
  window.addEventListener("beforeunload", function (e) { if (mdDirty) { e.preventDefault(); e.returnValue = ""; } });

  // ---------- 설정 ----------
  $("#hidePrefix").addEventListener("change", function () { E.hideFarmPrefix = this.checked; save(); });
  $("#forget").onclick = function () { api("/api/forget", {}).then(function () { toast("로그인 정보를 지웠어요"); load(); }).catch(lost); };

  // ---------- 탭 ----------
  $("#tabs").addEventListener("click", function (ev) {
    var b = ev.target.closest("button[data-tab]"); if (!b) return;
    document.querySelectorAll("#tabs button").forEach(function (x) { x.classList.toggle("on", x === b); });
    document.querySelectorAll(".tab").forEach(function (x) { x.classList.toggle("on", x.id === "tab-" + b.dataset.tab); });
    if (b.dataset.tab === "md") renderMD();
    if (b.dataset.tab === "video") renderVideos();
  });

  // ---------- 불러오기 / 올리기 ----------
  function startSync(body) {
    api("/api/sync", body || {}).then(function (r) {
      if (r.needLogin) { $("#login").showModal(); return; }
      $("#busy").hidden = false; poll();
    }).catch(lost);
  }
  var pollFail = 0;
  function poll() {
    api("/api/progress").then(function (s) {
      pollFail = 0;
      $("#busyMsg").textContent = s.msg || "불러오는 중…";
      $("#busyBar").style.width = (s.total ? Math.max(5, 100 * s.done / s.total) : 5) + "%";
      if (s.busy) return setTimeout(poll, 700);
      $("#busy").hidden = true;
      if (s.error) { toast(s.error, true); if (/로그인 실패/.test(s.error)) $("#login").showModal(); }
      else { toast(s.msg); load(); }
    }).catch(function () {   // 잠깐 끊긴 것일 수 있어 몇 번 더 물어봄
      if (++pollFail < 4) return setTimeout(poll, 1000);
      pollFail = 0; $("#busy").hidden = true; lost();
    });
  }
  $("#btnSync").onclick = function () { startSync(); };
  // 새로고침: 저장된 내용을 다시 읽어서 화면을 새로 그림 (보던 상품·탭은 그대로)
  function reload() {
    if (mdDirty && !confirm("MD추천에 저장 안 된 변경이 있어요. 새로고침하면 사라져요. 계속할까요?")) return;
    load(function () { toast("새로고침 했어요"); });
  }
  $("#btnReload").onclick = reload;

  // 런처에서 업데이트하면 프로그램이 새 버전으로 다시 켜짐 → 열려 있던 이 화면도 15초 안에 스스로 새 화면으로 바뀜
  var LOADED_VERSION = null, updateNotified = false;
  setInterval(function () {
    fetch("/api/progress", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (s) {
      if (!s.version) return;
      if (LOADED_VERSION === null) { LOADED_VERSION = s.version; return; }
      if (s.version === LOADED_VERSION || s.busy) return;
      if (mdDirty) {
        if (!updateNotified) { updateNotified = true; toast("새 버전(v" + s.version + ")이 적용됐어요. MD추천을 저장한 뒤 [↻ 새로고침]을 눌러 주세요.", true); }
        return;
      }
      location.reload();
    }).catch(function () {});
  }, 15000);
  document.addEventListener("keydown", function (e) {
    if (e.key === "F5" && !e.ctrlKey) { e.preventDefault(); reload(); }
  });
  $("#login").addEventListener("close", function () {
    var f = $("#loginForm");
    if (this.returnValue === "ok") startSync({ id: f.id.value.trim(), pw: f.pw.value, remember: f.remember.checked });
    f.pw.value = "";
    this.returnValue = "";
  });
  $("#btnPublish").onclick = function () {
    if (mdDirty && !confirm("MD추천에 저장 안 된 변경이 있어요. 저장하지 않고 올릴까요?")) return;
    if (!confirm("지금 내용을 셀러 사이트에 올릴까요?")) return;
    var b = this; b.disabled = true; b.textContent = "올리는 중…";
    clearTimeout(saveTimer);
    function done(r) {
      // 같은 곳을 다른 사람도 고쳤으면 → 무엇이 겹쳤는지 보여주고 누구 것을 남길지 고르게 함
      if (!r.ok && r.conflict && r.conflict.length) {
        var keepMine = confirm("같은 곳을 다른 사람도 고쳤어요:\n\n- " + r.conflict.join("\n- ") +
          "\n\n[확인] = 이 칸들은 내 것으로 올리기\n[취소] = 이 칸들은 다른 사람 것으로 받기\n\n(겹치지 않은 나머지는 둘 다 그대로 합쳐져요)");
        return api("/api/publish", { resolve: keepMine ? "mine" : "theirs" }).then(done);
      }
      toast(r.msg, !r.ok);
      if (r.received) load();   // 다른 사람이 올린 내용이 합쳐졌으니 화면도 새로 그림
    }
    api("/api/edits", E).then(function () { return api("/api/publish", {}); }).then(done).catch(lost)
      .finally(function () { b.disabled = false; b.textContent = "⬆ 사이트에 올리기"; });
  };

  function load(done) {
    api("/api/state").then(function (s) {
      RAW = s.raw; E = s.edits; OPT = (RAW && RAW.options) || {};
      CATS = (RAW && RAW.categories) || [];
      $("#ver").textContent = s.version ? "v" + s.version : "";
      if (s.version) LOADED_VERSION = s.version;
      var keepCat = $("#fcat").value;
      $("#fcat").innerHTML = '<option value="">전체 카테고리</option>' + CATS.map(function (c) { return '<option value="' + c.code + '">' + esc(c.name) + "</option>"; }).join("");
      $("#fcat").value = keepCat;
      $("#status").textContent = RAW ? "마지막 불러오기: " + (RAW.synced || "-") + " · 상품그룹 " + RAW.groups.length + "개" : "아직 불러온 적 없음";
      $("#loginInfo").textContent = s.hasPassword ? "저장됨 (아이디: " + s.savedId + ")" : "저장 안 됨";
      $("#noticeEd").innerHTML = FC_cleanHtml(E.noticeHtml != null ? E.noticeHtml : FC_textToHtml(E.notice)); normalize(); renderLinks(); renderVideos();
      MDD = JSON.parse(JSON.stringify(E.md || [])); mdMark(false);
      $("#hidePrefix").checked = E.hideFarmPrefix !== false;
      if ($("#login input[name=id]")) $("#login input[name=id]").value = s.savedId || "";
      renderList(); renderEdit(); renderMD();
      if (done) done();
    }).catch(lost);
  }
  load();
})();
