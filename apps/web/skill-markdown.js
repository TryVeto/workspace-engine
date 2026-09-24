(()=>{
// Small, dependency-free Markdown reader. Raw HTML is always text.
const node = (tag, text) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; return el; };

function inline(parent, text, link) {
  const pattern = /(!?\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|__([^_]+)__|\x60([^\x60]+)\x60|\*([^*\n]+)\*)/g;
  let last = 0, match;
  while ((match = pattern.exec(text))) {
    parent.append(document.createTextNode(text.slice(last, match.index)));
    if (match[2] !== undefined) {
      const target = match[3].trim().replace(/^<|>$/g, "");
      const anchor = link(target, match[2], match[0].startsWith("!"));
      parent.append(anchor);
    } else {
      const tag = match[4] || match[5] ? "strong" : match[6] ? "code" : "em";
      parent.append(node(tag, match[4] || match[5] || match[6] || match[7]));
    }
    last = pattern.lastIndex;
  }
  parent.append(document.createTextNode(text.slice(last)));
}

function markdown(text, link, omitTitle = false) {
  const root = document.createDocumentFragment();
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  let i = 0, titleSkipped = false;
  const append = (tag, content, parent = root) => { const el = node(tag); inline(el, content, link); parent.append(el); return el; };
  const isBlock = s => /^(#{1,6}\s|\s*[-*+]\s|\s*\d+[.)]\s|>|\x60{3}|~{3}|\s*$|---+$|\*\*\*+$)/.test(s);
  while (i < lines.length) {
    let line = lines[i++];
    if (!line.trim()) continue;
    const fence = line.match(/^\s*(\x60{3,}|~{3,})/);
    if (fence) {
      const code = [];
      while (i < lines.length && !lines[i].trimStart().startsWith(fence[1])) code.push(lines[i++]);
      i++;
      const pre = node("pre"); pre.append(node("code", code.join("\n"))); root.append(pre); continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*$/);
    if (heading) {
      if (omitTitle && heading[1] === "#" && !titleSkipped) { titleSkipped = true; continue; }
      const h = append("h" + Math.min(heading[1].length, 4), heading[2]);
      h.id = heading[2].toLowerCase().replace(/[^a-z0-9\s-]/g, "").replace(/\s+/g, "-");
      continue;
    }
    if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) { root.append(node("hr")); continue; }
    if (line.includes("|") && i < lines.length && /^\s*\|?\s*:?-{3}/.test(lines[i])) {
      const table = node("table"), wrap = node("div"); wrap.className = "table-wrap";
      const cells = value => value.trim().replace(/^\||\|$/g, "").split("|").map(x => x.trim());
      let tr = node("tr");
      cells(line).forEach(x => append("th", x, tr));
      const head = node("thead"); head.append(tr); table.append(head); i++;
      const body = node("tbody");
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        tr = node("tr"); cells(lines[i++]).forEach(x => append("td", x, tr)); body.append(tr);
      }
      table.append(body); wrap.append(table); root.append(wrap); continue;
    }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
      const ordered = /^\s*\d/.test(line), list = node(ordered ? "ol" : "ul");
      const marker = ordered ? /^\s*\d+[.)]\s+/ : /^\s*[-*+]\s+/;
      do {
        let item = line.replace(marker, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) item += "\n" + lines[i++].trim();
        append("li", item, list);
        if (i >= lines.length || !marker.test(lines[i])) break;
        line = lines[i++];
      } while (true);
      root.append(list); continue;
    }
    if (/^>\s?/.test(line)) {
      const parts = [line.replace(/^>\s?/, "")];
      while (i < lines.length && /^>/.test(lines[i])) parts.push(lines[i++].replace(/^>\s?/, ""));
      append("blockquote", parts.join("\n")); continue;
    }
    const parts = [line];
    while (i < lines.length && !isBlock(lines[i])) parts.push(lines[i++]);
    append("p", parts.join("\n"));
  }
  return root;
}

window.skillMarkdown=markdown;
})();
