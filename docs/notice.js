/* 공지사항 서식 정리 (관리 프로그램과 셀러 사이트가 같이 씀)
   - 허용한 서식(굵게·기울임·밑줄·취소선·글자색·배경색·크기·글꼴·제목·목록·링크·표)만 남기고 나머지는 지움
   - 글 속의 https://… 주소는 자동으로 링크로 바꿈 */
(function (w) {
  "use strict";
  var TAGS = { B: 1, STRONG: 1, I: 1, EM: 1, U: 1, S: 1, STRIKE: 1, SPAN: 1, FONT: 1, P: 1, DIV: 1, BR: 1, H1: 1, H2: 1, H3: 1,
    UL: 1, OL: 1, LI: 1, A: 1, TABLE: 1, THEAD: 1, TBODY: 1, TR: 1, TD: 1, TH: 1, HR: 1, BLOCKQUOTE: 1 };
  var STYLES = { "color": 1, "background-color": 1, "font-size": 1, "font-family": 1, "font-weight": 1, "font-style": 1,
    "text-decoration": 1, "text-decoration-line": 1, "text-align": 1 };
  var URL_RE = /https?:\/\/[^\s<>"']+/g;

  function cleanStyle(s) {
    return (s || "").split(";").map(function (d) {
      var i = d.indexOf(":"); if (i < 0) return "";
      var k = d.slice(0, i).trim().toLowerCase(), v = d.slice(i + 1).trim();
      if (!STYLES[k] || /url\(|expression|javascript/i.test(v)) return "";
      return k + ":" + v;
    }).filter(Boolean).join(";");
  }

  function linkifyText(node, doc) {
    var t = node.nodeValue; URL_RE.lastIndex = 0;
    if (!URL_RE.test(t)) return;
    var frag = doc.createDocumentFragment(), last = 0; URL_RE.lastIndex = 0;
    t.replace(URL_RE, function (u, at) {
      frag.appendChild(doc.createTextNode(t.slice(last, at)));
      var a = doc.createElement("a"); a.href = u; a.textContent = u; frag.appendChild(a);
      last = at + u.length; return u;
    });
    frag.appendChild(doc.createTextNode(t.slice(last)));
    node.parentNode.replaceChild(frag, node);
  }

  function walk(el, doc, inLink) {
    [].slice.call(el.childNodes).forEach(function (n) {
      if (n.nodeType === 3) { if (!inLink) linkifyText(n, doc); return; }
      if (n.nodeType !== 1) { n.remove(); return; }
      var tag = n.tagName;
      if (!TAGS[tag]) {
        if (/^(SCRIPT|STYLE|IFRAME|OBJECT|EMBED|META|LINK|TITLE)$/.test(tag)) { n.remove(); return; }
        walk(n, doc, inLink);                       // 모르는 태그는 껍데기만 벗기고 내용은 살림
        while (n.firstChild) el.insertBefore(n.firstChild, n);
        n.remove(); return;
      }
      var keep = {};
      if (n.getAttribute("style")) keep.style = cleanStyle(n.getAttribute("style"));
      if (tag === "A") {
        var href = n.getAttribute("href") || "";
        if (/^(https?:|mailto:|tel:)/i.test(href)) { keep.href = href; keep.target = "_blank"; keep.rel = "noopener"; }
      }
      if (tag === "FONT") { ["color", "size", "face"].forEach(function (k) { var v = n.getAttribute(k); if (v && !/[<>"]/.test(v)) keep[k] = v; }); }
      if (tag === "TD" || tag === "TH") { ["colspan", "rowspan"].forEach(function (k) { var v = n.getAttribute(k); if (/^\d+$/.test(v || "")) keep[k] = v; }); }
      [].slice.call(n.attributes).forEach(function (a) { n.removeAttribute(a.name); });
      Object.keys(keep).forEach(function (k) { if (keep[k]) n.setAttribute(k, keep[k]); });
      walk(n, doc, inLink || tag === "A");
    });
  }

  w.FC_cleanHtml = function (html) {
    var doc = new DOMParser().parseFromString("<div>" + (html || "") + "</div>", "text/html");
    var root = doc.body.firstChild;
    walk(root, doc, false);
    return root.innerHTML;
  };
  // 예전처럼 글자만 있던 공지를 서식 있는 공지로 바꿈
  w.FC_textToHtml = function (text) {
    var d = document.createElement("div"); d.textContent = text || "";
    return d.innerHTML.replace(/\n/g, "<br>");
  };
})(window);
