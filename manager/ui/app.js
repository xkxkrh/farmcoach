(function () {
  "use strict";
  var $ = function (s, el) { return (el || document).querySelector(s); };
  var RAW = null, E = null, OPT = {}, CATS = [], sel = null, saveTimer = null;
  var FIELDS = [
    ["name", "상품그룹명", "wide"], ["cat", "카테고리", ""], ["ship", "기본 배송비", ""],
    ["jeju", "제주도 택배비", ""], ["island", "도서산간 택배비", ""],
    ["link", "상세페이지 링크", "wide"], ["img", "썸네일 사진 주소", "wide"], ["note", "비고 (원산지·기타 안내)", "wide"]
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
      api("/api/edits", E).then(function () { $("#saved").textContent = "✓ 자동 저장됨 (" + new Date().toLocaleTimeString("ko-KR") + ")"; });
    }, 500);
  }
  function setEdit(bucket, id, key, value, original) {
    var o = E[bucket][id] || (E[bucket][id] = {});
    if (value === original || value === "auto" || value === false) delete o[key]; else o[key] = value;
    if (!Object.keys(o).length) delete E[bucket][id];
    save();
  }

  // ---------- 상품 목록 ----------
  function renderList() {
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
    }).join("") || '<p class="hint" style="padding:16px">조건에 맞는 상품이 없어요.</p>';
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
    // 다시 그려도 커서가 있던 칸을 기억했다가 돌려놓음
    var a = document.activeElement, keep = null;
    if (a && $("#gedit").contains(a)) {
      var tr = a.closest("tr");
      keep = (a.dataset.k ? '[data-k="' + a.dataset.k + '"]' : a.dataset.ok ? 'tr[data-o="' + (tr && tr.dataset.o) + '"] [data-ok="' + a.dataset.ok + '"]' : null);
    }
    drawEdit();
    if (keep) { var n = $("#gedit " + keep); if (n) n.focus(); }
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
    if (!ev.target.matches("input,textarea")) return;
    setTimeout(renderEdit, 0); // 다음 칸으로 커서가 옮겨간 뒤에 다시 그림
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

  // ---------- 공지사항 ----------
  function renderNotice() { $("#noticePrev").innerHTML = linkify(E.notice); }
  $("#notice").addEventListener("input", function () { E.notice = this.value; renderNotice(); save(); });

  // ---------- MD추천 ----------
  function groupById(id) { return RAW && RAW.groups.filter(function (g) { return g.id === id; })[0]; }
  function groupLabel(g) { return gval(g, "name") + "  [" + g.id + "]"; }
  function renderMD() {
    if (RAW) {
      $("#groupNames").innerHTML = RAW.groups.filter(function (g) { return !gHidden(g); })
        .sort(function (a, b) { return a.date < b.date ? 1 : -1; })
        .map(function (g) { return '<option value="' + esc(groupLabel(g)) + '">'; }).join("");
    }
    $("#mdList").innerHTML = E.md.map(function (p, i) {
      var g = groupById(p.g), im = g && gval(g, "img");
      return '<div class="mdc" data-i="' + i + '">' + (im ? '<img src="' + esc(im) + '" alt="">' : '<span class="ni"></span>') +
        '<div><input list="groupNames" class="mdg" placeholder="상품 이름을 입력해서 고르세요" value="' + (g ? esc(groupLabel(g)) : "") + '">' +
        (g ? '<div class="opts">' + g.options.map(function (oid) {
          var o = OPT[oid]; if (!o) return "";
          return '<label><input type="checkbox" class="mdo" value="' + oid + '"' + (p.o.indexOf(oid) > -1 ? " checked" : "") + ">" + esc(o.name) + " (" + o.price.toLocaleString() + "원)</label>";
        }).join("") + "</div>" : "") +
        '<textarea class="mdt" rows="2" placeholder="추천 문구 (예: 이번 주 최저가! 당도 보장 🍊)">' + esc(p.text) + "</textarea>" +
        (g && gSoldout(g) ? '<p class="hint" style="color:#cf3b3b">⚠ 지금 품절 상태인 상품이에요.</p>' : "") + "</div>" +
        '<div class="ctl"><button class="btn sm" data-mv="-1">▲</button><button class="btn sm" data-mv="1">▼</button><button class="btn sm" data-del>삭제</button></div></div>';
    }).join("") || '<p class="hint">아직 추천 상품이 없어요.</p>';
  }
  $("#mdAdd").onclick = function () { E.md.push({ g: "", o: [], text: "" }); renderMD(); save(); };
  $("#mdList").addEventListener("change", function (ev) {
    var c = ev.target.closest(".mdc"); if (!c) return;
    var p = E.md[+c.dataset.i];
    if (ev.target.classList.contains("mdg")) {
      var m = ev.target.value.match(/\[(\d+)\]\s*$/);
      p.g = m ? m[1] : ""; p.o = [];
      if (!m) toast("목록에서 상품을 골라 주세요", true);
      renderMD();
    } else if (ev.target.classList.contains("mdo")) {
      p.o = Array.prototype.map.call(c.querySelectorAll(".mdo:checked"), function (x) { return x.value; });
    }
    save();
  });
  $("#mdList").addEventListener("input", function (ev) {
    if (!ev.target.classList.contains("mdt")) return;
    E.md[+ev.target.closest(".mdc").dataset.i].text = ev.target.value; save();
  });
  $("#mdList").addEventListener("click", function (ev) {
    var b = ev.target.closest("button"); if (!b) return;
    var i = +b.closest(".mdc").dataset.i;
    if (b.hasAttribute("data-del")) { if (!confirm("이 추천 상품을 지울까요?")) return; E.md.splice(i, 1); }
    else { var j = i + Number(b.dataset.mv); if (j < 0 || j >= E.md.length) return; var t = E.md[i]; E.md[i] = E.md[j]; E.md[j] = t; }
    renderMD(); save();
  });

  // ---------- 설정 ----------
  $("#hidePrefix").addEventListener("change", function () { E.hideFarmPrefix = this.checked; save(); });
  $("#forget").onclick = function () { api("/api/forget", {}).then(function () { toast("로그인 정보를 지웠어요"); load(); }); };

  // ---------- 탭 ----------
  $("#tabs").addEventListener("click", function (ev) {
    var b = ev.target.closest("button[data-tab]"); if (!b) return;
    document.querySelectorAll("#tabs button").forEach(function (x) { x.classList.toggle("on", x === b); });
    document.querySelectorAll(".tab").forEach(function (x) { x.classList.toggle("on", x.id === "tab-" + b.dataset.tab); });
    if (b.dataset.tab === "md") renderMD();
  });

  // ---------- 불러오기 / 올리기 ----------
  function startSync(body) {
    api("/api/sync", body || {}).then(function (r) {
      if (r.needLogin) { $("#login").showModal(); return; }
      $("#busy").hidden = false; poll();
    });
  }
  function poll() {
    api("/api/progress").then(function (s) {
      $("#busyMsg").textContent = s.msg || "불러오는 중…";
      $("#busyBar").style.width = (s.total ? Math.max(5, 100 * s.done / s.total) : 5) + "%";
      if (s.busy) return setTimeout(poll, 700);
      $("#busy").hidden = true;
      if (s.error) { toast(s.error, true); if (/로그인 실패/.test(s.error)) $("#login").showModal(); }
      else { toast(s.msg); load(); }
    });
  }
  $("#btnSync").onclick = function () { startSync(); };
  $("#login").addEventListener("close", function () {
    var f = $("#loginForm");
    if (this.returnValue === "ok") startSync({ id: f.id.value.trim(), pw: f.pw.value, remember: f.remember.checked });
    f.pw.value = "";
    this.returnValue = "";
  });
  $("#btnPublish").onclick = function () {
    if (!confirm("지금 내용을 셀러 사이트에 올릴까요?")) return;
    var b = this; b.disabled = true; b.textContent = "올리는 중…";
    clearTimeout(saveTimer);
    api("/api/edits", E).then(function () { return api("/api/publish", {}); }).then(function (r) {
      toast(r.msg, !r.ok);
    }).finally(function () { b.disabled = false; b.textContent = "⬆ 사이트에 올리기"; });
  };

  function load() {
    api("/api/state").then(function (s) {
      RAW = s.raw; E = s.edits; OPT = (RAW && RAW.options) || {};
      CATS = (RAW && RAW.categories) || [];
      $("#fcat").innerHTML = '<option value="">전체 카테고리</option>' + CATS.map(function (c) { return '<option value="' + c.code + '">' + esc(c.name) + "</option>"; }).join("");
      $("#status").textContent = RAW ? "마지막 불러오기: " + (RAW.synced || "-") + " · 상품그룹 " + RAW.groups.length + "개" : "아직 불러온 적 없음";
      $("#loginInfo").textContent = s.hasPassword ? "저장됨 (아이디: " + s.savedId + ")" : "저장 안 됨";
      $("#notice").value = E.notice; renderNotice();
      $("#hidePrefix").checked = E.hideFarmPrefix !== false;
      if ($("#login input[name=id]")) $("#login input[name=id]").value = s.savedId || "";
      renderList(); renderEdit(); renderMD();
    });
  }
  load();
})();
