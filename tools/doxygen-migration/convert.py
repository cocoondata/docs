"""Convert the legacy Doxygen docs site (docs.cocoondata.com) into a Mintlify project.

Usage: python convert.py <doxygen-site-root> <mintlify-repo-root>

Writes <version>/<section>/<page>.mdx, images/<hash>-<name>, and returns navigation and redirects
in nav.json next to this script for build_config.py to merge into docs.json.
"""

import hashlib
import json
import os
import posixpath
import re
import shutil
import sys
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import MarkdownConverter

# Newest first; the first entry is the default version.
VERSIONS = ["CS1.2", "CS1.0", "3.5", "3.4", "3.3", "3.2", "3.1", "3.0", "2.16"]
LATEST = "CS1.2"

# Private-use placeholders survive markdownify untouched, then become MDX-safe text.
LBRACE, RBRACE, LT, GT = "", "", "", ""
ANCHOR_OPEN, ANCHOR_CLOSE = "", ""
CALLOUT_OPEN, CALLOUT_CLOSE = "", ""
BR = ""

CALLOUTS = [
    (re.compile(r"^(?:[*\d]+\s*)?(?:Additional\s+|Weitere\s+)?(Tip|Tipp|Tips|Tipps)\b", re.I), "Tip"),
    (re.compile(r"^(?:[*\d]+\s*)?(Warning|Warnung|Important|Wichtig|Caution|Achtung)\b", re.I), "Warning"),
    (re.compile(r"^(?:[*\d]+\s*)?(?:Additional\s+|Weitere\s+)?(Note|Notes|Hinweis|Hinweise)\b", re.I), "Note"),
]

CODE_OPEN, CODE_CLOSE = "\ue040", "\ue041"
code_blocks = []
LABEL = re.compile(r"^\s*(Note|Notes|Tip|Tips|Tipp|Tipps|Hinweis|Hinweise|Warning|Warnung|Important|Wichtig|Caution|Achtung)\s*:?\s*$", re.I)

SRC = DST = None
# Symlinked section folders that point inside the same version (for example 3.2/restapi -> api).
ALIASES = {}
image_cache = {}
problems = []


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text).strip("-")


def page_path(site_rel_html):
    """'3.4/user/signing-in.html' -> '3.4/user/signing-in'."""
    p = site_rel_html[:-5] if site_rel_html.endswith(".html") else site_rel_html
    return p


def resolve_site_path(current_rel, href):
    """Resolve an href relative to the current page into a site-relative path, or None if external."""
    parts = urlsplit(href)
    if parts.scheme or parts.netloc or href.startswith(("mailto:", "#", "javascript:")):
        return None, parts.fragment
    path = unquote(parts.path)
    if not path:
        return current_rel, parts.fragment
    base = posixpath.dirname(current_rel)
    joined = posixpath.normpath(posixpath.join(base, path)) if not path.startswith("/") else path.lstrip("/")
    if path.endswith("/"):
        joined = posixpath.join(joined, "index.html")
    joined = re.sub(r"^latest/", LATEST + "/", joined)
    for alias, target in ALIASES.items():
        if joined.startswith(alias + "/"):
            joined = target + joined[len(alias):]
    return joined, parts.fragment


_image_index = None


def image_index():
    """Map image file names to every path in the source tree that has them."""
    global _image_index
    if _image_index is None:
        _image_index = {}
        for root, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            for name in files:
                if "/images" in root:
                    _image_index.setdefault(name, []).append(os.path.join(root, name))
    return _image_index


def copy_image(abs_path):
    if abs_path in image_cache:
        return image_cache[abs_path]
    if not os.path.isfile(abs_path):
        # Some pages reference screenshots that only exist in another version's folder (missing on the legacy
        # site too). Use the same file name from elsewhere, preferring the same language.
        german = "/de/" in abs_path
        candidates = sorted(image_index().get(os.path.basename(abs_path), []), key=lambda c: ("/de/" in c) != german)
        if candidates:
            abs_path = candidates[0]
    if not os.path.isfile(abs_path):
        problems.append("missing image " + os.path.relpath(abs_path, SRC))
        return None
    data = open(abs_path, "rb").read()
    digest = hashlib.sha1(data).hexdigest()[:12]
    name = re.sub(r"[^A-Za-z0-9._-]", "-", os.path.basename(abs_path)).lower()
    rel = "images/%s-%s" % (digest, name)
    out = os.path.join(DST, rel)
    if not os.path.exists(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as fh:
            fh.write(data)
    image_cache[abs_path] = "/" + rel
    return image_cache[abs_path]


def copy_asset(site_rel):
    """Copy a linked non-HTML file (for example a PDF) into assets/ and return its URL."""
    abs_path = os.path.join(SRC, site_rel)
    if not os.path.isfile(abs_path):
        problems.append("missing asset " + site_rel)
        return None
    rel = "assets/" + site_rel
    out = os.path.join(DST, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copyfile(abs_path, out)
    return "/" + rel


class MintConverter(MarkdownConverter):
    def convert_a(self, el, text, convert_as_inline):
        href = el.get("href")
        if not href or not text.strip():
            return text
        return "[%s](%s)" % (text.strip(), href)

    def convert_img(self, el, text, convert_as_inline):
        return "![%s](%s)" % ((el.get("alt") or "").replace("]", ""), el.get("src", ""))

    def convert_br(self, el, text, convert_as_inline):
        return BR

    def convert_sup(self, el, text, convert_as_inline):
        # Footnote markers are often "*", which MDX would read as emphasis.
        return "<sup>%s</sup>" % text.strip().replace("*", "&#42;") if text.strip() else ""

    def convert_sub(self, el, text, convert_as_inline):
        return "<sub>%s</sub>" % text.strip().replace("*", "&#42;") if text.strip() else ""

    def convert_list(self, el, text, convert_as_inline):
        # Nested lists are indented by their parent item (see convert_li), so add no indent here.
        nested = el.find_parent("li") is not None
        if nested:
            return "\n\n" + text.strip("\n") + "\n\n"
        return "\n\n" + text.strip("\n") + "\n\n"

    convert_ul = convert_list
    convert_ol = convert_list

    def convert_li(self, el, text, convert_as_inline):
        parent = el.parent
        if parent is not None and parent.name == "ol":
            start = int(parent.get("start")) if str(parent.get("start") or "").isnumeric() else 1
            bullet = "%d." % (start + parent.find_all("li", recursive=False).index(el))
        else:
            bullet = "-"
        body = re.sub(r"\n{3,}", "\n\n", (text or "").strip())
        pad = " " * (len(bullet) + 1)
        lines = body.split("\n")
        body = "\n".join([lines[0]] + [(pad + l) if l.strip() else "" for l in lines[1:]])
        return "%s %s\n" % (bullet, body)


RAW = "\ue060"
KEEP_TAGS = {"table", "thead", "tbody", "tr", "td", "th", "b", "strong", "em", "i", "code", "a", "br", "ul", "ol", "li", "p", "sup", "sub", "img"}


def jsx_html(el):
    """Serialize a table to HTML that is valid JSX: known tags, safe attributes, escaped text."""
    if isinstance(el, NavigableString):
        # One line, so the table can sit inside an indented list item.
        text = re.sub(r"\s+", " ", str(el))
        for a, b in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ("{", "&#123;"), ("}", "&#125;")):
            text = text.replace(a, b)
        return text
    inner = "".join(jsx_html(c) for c in el.children)
    if el.name not in KEEP_TAGS:
        return inner
    attrs = []
    for name, jsx in (("colspan", "colSpan"), ("rowspan", "rowSpan"), ("href", "href"), ("src", "src"), ("alt", "alt")):
        if el.get(name):
            attrs.append('%s="%s"' % (jsx, str(el.get(name)).replace('"', "&quot;")))
    open_tag = "<%s%s" % (el.name, (" " + " ".join(attrs)) if attrs else "")
    if el.name in ("br", "img"):
        return open_tag + " />"
    return "%s>%s</%s>" % (open_tag, inner.strip() if el.name in ("td", "th", "li", "p") else inner, el.name)


def prepare(soup, current_rel):
    """Rewrite the Doxygen DOM in place so markdownify produces clean Mintlify MDX."""
    contents = soup.select_one("div.contents") or soup.body
    # Line numbers are followed by a separating non-breaking space; remove both.
    for lineno in contents.select("span.lineno"):
        nxt = lineno.next_sibling
        if isinstance(nxt, NavigableString) and nxt.startswith("\xa0"):
            nxt.replace_with(nxt[1:])
        lineno.decompose()
    # Doxygen's topic index (table.directory) becomes a plain list of links.
    for directory in contents.select("div.directory"):
        links = directory.select("a.el")
        listing = soup.new_tag("ul")
        for link in links:
            item = soup.new_tag("li")
            item.append(link.extract())
            listing.append(item)
        directory.replace_with(listing)
    for junk in contents.select("script, noscript, a.dsq-brlink, span.logo-disqus, div.levels"):
        junk.decompose()

    # Lightbox links that only wrap an image add nothing; keep the image.
    for a in contents.find_all("a", href=True):
        kids = [c for c in a.contents if not (isinstance(c, NavigableString) and not c.strip())]
        if len(kids) == 1 and getattr(kids[0], "name", None) == "img":
            a.unwrap()

    # Links and images.
    for a in contents.find_all("a", href=True):
        target, frag = resolve_site_path(current_rel, a["href"])
        if target is None:
            continue
        if target.endswith(".html") and os.path.isfile(os.path.join(SRC, target)):
            a["href"] = "/" + page_path(target) + ("#" + frag if frag else "")
        elif os.path.isfile(os.path.join(SRC, target)):
            asset = copy_asset(target)
            if asset:
                a["href"] = asset
        else:
            # Already broken on the legacy site: keep the text, drop the dead link.
            problems.append("broken link %s -> %s" % (current_rel, a["href"]))
            a.unwrap()
    for img in contents.find_all("img"):
        src = img.get("src", "")
        target, _ = resolve_site_path(current_rel, src)
        url = copy_image(os.path.join(SRC, target)) if target else src
        if url:
            img["src"] = url
        else:
            img.decompose()

    # Code fragments become fenced blocks; keep their raw text.
    for frag in contents.select("div.fragment, pre.fragment"):
        lines = [l.get_text() for l in frag.select("div.line")] or frag.get_text().split("\n")
        code = "\n".join(l.replace("\xa0", " ").rstrip() for l in lines).strip("\n")
        first = code.lstrip()
        if first.startswith(("{", "[")):
            lang = "json"
        elif first.startswith("curl "):
            lang = "bash"
        elif re.match(r"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) ", first):
            lang = "http"
        else:
            lang = "text"
        code_blocks.append("```%s\n%s\n```" % (lang, code))
        holder = soup.new_tag("p")
        holder.string = CODE_OPEN + str(len(code_blocks) - 1) + CODE_CLOSE
        frag.replace_with(holder)

    # Figures are blocks: make them paragraphs so they stay inside list items.
    for fig in contents.select("div.image"):
        fig.name = "p"

    # Inline content that follows a nested list or block inside a list item starts a new paragraph.
    for li in contents.find_all("li"):
        run, after_block = [], False
        for child in list(li.children):
            is_block = getattr(child, "name", None) in ("ul", "ol", "p", "div", "table", "blockquote", "pre")
            if is_block:
                if run:
                    wrapper = soup.new_tag("p")
                    run[0].insert_before(wrapper)
                    for node in run:
                        wrapper.append(node.extract())
                    run = []
                after_block = True
            elif after_block:
                run.append(child)
        if run and any(not isinstance(n, NavigableString) or n.strip() for n in run):
            wrapper = soup.new_tag("p")
            run[0].insert_before(wrapper)
            for node in run:
                wrapper.append(node.extract())

    # Headings: collapse whitespace so the anchor and text stay on one line.
    for h in contents.find_all(["h1", "h2", "h3", "h4"]):
        anchors = [a.extract() for a in h.select("a.anchor")]
        text = " ".join(h.get_text().split())
        h.clear()
        h.append(NavigableString(text + (" " if anchors else "")))
        for a in anchors:
            h.append(a)

    # Callouts.
    for bq in contents.select("blockquote"):
        text = " ".join(bq.get_text(" ").split())
        kind = "Info"
        for pattern, name in CALLOUTS:
            if pattern.match(text):
                kind = name
                break
        first = bq.find(["b", "strong"])
        if first is not None and LABEL.match(first.get_text()) and text.startswith(" ".join(first.get_text().split())):
            nxt = first.next_sibling
            first.decompose()
            if isinstance(nxt, NavigableString):
                nxt.replace_with(nxt.lstrip())
        bq.insert(0, NavigableString(CALLOUT_OPEN + kind + CALLOUT_CLOSE + "\n\n"))
        bq.append(NavigableString("\n\n" + CALLOUT_OPEN + "/" + kind + CALLOUT_CLOSE))
        bq.unwrap()

    # Anchors: keep only ids that Mintlify's own heading slugs would not reproduce.
    for a in contents.select("a.anchor"):
        anchor_id = a.get("id")
        parent = a.parent
        if parent and parent.name in ("h1", "h2", "h3", "h4") and slugify(parent.get_text()) == anchor_id:
            a.decompose()
            continue
        a.replace_with(NavigableString(ANCHOR_OPEN + anchor_id + ANCHOR_CLOSE) if anchor_id else "")

    # Doxygen uses h1 for sections; the page title is separate, so shift headings down a level.
    for level in ("h3", "h2", "h1"):
        for h in contents.find_all(level):
            h.name = "h%d" % (int(level[1]) + 1)

    for table in contents.find_all("table"):
        if table.find(["td", "th"], attrs={"colspan": True}) or table.find(["td", "th"], attrs={"rowspan": True}):
            code_blocks.append(RAW + jsx_html(table))
            holder = soup.new_tag("p")
            holder.string = CODE_OPEN + str(len(code_blocks) - 1) + CODE_CLOSE
            table.replace_with(holder)

    # Table cells cannot hold block elements in Markdown tables: flatten them to inline content.
    for cell in contents.select("td, th"):
        for blk in cell.find_all(["p", "div", "ul", "ol", "li"]):
            if blk.name == "li":
                blk.insert(0, NavigableString(BR + "\u2022 "))
            blk.append(NavigableString(BR))
            blk.unwrap()

    # Escape MDX-significant characters in prose (not in code).
    for node in contents.find_all(string=True):
        if node.find_parent(["code", "pre"]):
            continue
        s = str(node)
        if any(c in s for c in "{}<>"):
            node.replace_with(NavigableString(s.replace("{", LBRACE).replace("}", RBRACE).replace("<", LT).replace(">", GT)))
    return contents


def finish(md):
    """Turn placeholders into MDX and tidy whitespace."""
    out, in_fence = [], False
    for line in md.split("\n"):
        # Nested list indentation: tabs to four spaces.
        stripped = line.lstrip("\t")
        line = "    " * (len(line) - len(stripped)) + stripped
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if in_fence or line.strip().startswith("```"):
            line = line.replace(LBRACE, "{").replace(RBRACE, "}").replace(LT, "<").replace(GT, ">")
        else:
            line = line.replace(LBRACE, "\\{").replace(RBRACE, "\\}").replace(LT, "&lt;").replace(GT, "&gt;")
        out.append(line)
    md = "\n".join(out)
    md = re.sub(ANCHOR_OPEN + r"([^" + ANCHOR_CLOSE + r"]+)" + ANCHOR_CLOSE, r'<a id="\1" />', md)
    md = re.sub(CALLOUT_OPEN + r"(/?)(\w+)" + CALLOUT_CLOSE, r"<\1\2>", md)
    # Callout tags must sit on their own lines, without blockquote markers left by nested content.
    md = re.sub(r"[ \t]*(</?(?:Note|Tip|Warning|Info)>)[ \t]*", r"\n\1\n", md)
    # A line break followed by more text keeps the break; a trailing one is dropped.
    md = re.sub(BR + r"[ \t]*\n(?=[ \t]*\S)", "<br />\n", md)
    md = re.sub(BR + r"[ \t]*(?=\n|$)", "", md)
    md = md.replace(BR, "<br />")
    md = re.sub(r"(<br />\s*)+\|", " |", md)
    md = re.sub(r"\|\s*(<br />\s*)+", "| ", md)
    md = re.sub(r"(<br />\s*){2,}", "<br />", md)
    md = re.sub(r"\n{3,}", "\n\n", md)

    # Code blocks go back in last, raw. A token can sit mid-line (after a label) or inside a table row.
    token = re.compile(CODE_OPEN + r"(\d+)" + CODE_CLOSE)
    out = []
    for line in md.split("\n"):
        if not token.search(line):
            out.append(line)
            continue
        if line.lstrip().startswith("|"):
            # Fenced blocks cannot live in table cells: show the code inline.
            def inline(m):
                body = code_blocks[int(m.group(1))].split("\n")[1:-1]
                return "`" + " ".join(l.strip() for l in body).replace("`", "'") + "`"
            out.append(token.sub(inline, line))
            continue
        lead = re.match(r"[ \t]*(?:(?:[-*+]|\d+\.)[ \t]+)?", line).group(0)
        indent = " " * len(lead.expandtabs(4))
        parts = token.split(line)
        for i, part in enumerate(parts):
            if i % 2 == 0:
                text = part if i == 0 else indent + part.strip()
                if text.strip():
                    out.append(text.rstrip())
            else:
                block = code_blocks[int(part)]
                if block.startswith(RAW):
                    out.append("")
                    out.append(indent + block[len(RAW):])
                    out.append("")
                    continue
                if not block.split("\n")[1:-1] or not "".join(block.split("\n")[1:-1]).strip():
                    continue  # Empty example in the source.
                out.append("")
                out.extend((indent + l) if l else "" for l in block.split("\n"))
                out.append("")
    md = "\n".join(out)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def convert_page(site_rel_html):
    html = open(os.path.join(SRC, site_rel_html), encoding="utf-8", errors="ignore").read()
    # The HTML parser collapses runs of spaces; protect indentation inside code lines first.
    html = re.sub(
        r'(<div class="line">)(.*?)(</div>)',
        lambda m: m.group(1) + re.sub(r" {2,}", lambda w: "\xa0" * len(w.group(0)), m.group(2)) + m.group(3),
        html,
    )
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one("div.headertitle div.title") or soup.title
    title = " ".join(title_el.get_text().split()) if title_el else posixpath.basename(site_rel_html)
    contents = prepare(soup, site_rel_html)
    md = MintConverter(heading_style="ATX", bullets="-", escape_underscores=False, escape_asterisks=False, escape_misc=False).convert_soup(contents)
    body = finish(md)
    body = re.sub(r"^#\s+" + re.escape(title) + r"\s*\n", "", body)
    fm_title = title.replace("\\", "\\\\").replace('"', '\\"')
    out_rel = page_path(site_rel_html) + ".mdx"
    out_abs = os.path.join(DST, out_rel)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    with open(out_abs, "w", encoding="utf-8") as fh:
        fh.write('---\ntitle: "%s"\n---\n\n%s' % (fm_title, body))
    return title


def read_navtree(section_dir):
    path = os.path.join(SRC, section_dir, "navtreedata.js")
    if not os.path.isfile(path):
        return None
    js = open(path, encoding="utf-8", errors="ignore").read()
    m = re.search(r"var NAVTREE =\s*(\[.*?\]);\s*\n", js, re.S)
    if not m:
        return None
    data = m.group(1).replace("null", "null")
    return json.loads(re.sub(r",\s*\]", "]", data))


def nav_entries(section_dir, children, seen):
    """Map navtree children to Mintlify page paths and nested groups."""
    pages = []
    for title, url, sub in children or []:
        if not url or "#" in url:
            continue
        rel = posixpath.join(section_dir, url)
        if rel in seen or not os.path.isfile(os.path.join(SRC, rel)):
            continue
        seen.add(rel)
        nested = nav_entries(section_dir, sub, seen) if isinstance(sub, list) else []
        if nested:
            pages.append({"group": title, "pages": [page_path(rel)] + nested})
        else:
            pages.append(page_path(rel))
    return pages


def is_alias(link_rel):
    """Return the target when a symlinked folder points inside its own version; None when it points at another version."""
    version = link_rel.split("/")[0]
    target = posixpath.normpath(posixpath.join(posixpath.dirname(link_rel), os.readlink(os.path.join(SRC, link_rel))))
    return target if target.split("/")[0] == version else None


def section_dirs(version):
    base = os.path.join(SRC, version)
    out = []
    candidates = []
    for name in sorted(os.listdir(base)):
        full = os.path.join(base, name)
        if not os.path.isdir(full):
            continue
        if name == "de" and not os.path.islink(full):
            candidates += [posixpath.join(version, "de", sub) for sub in sorted(os.listdir(full))]
        else:
            candidates.append(posixpath.join(version, name))
    for rel in candidates:
        full = os.path.join(SRC, rel)
        if not os.path.isdir(full):
            continue
        if os.path.islink(full):
            target = is_alias(rel)
            if target is not None:
                # Same-version alias: redirect instead of duplicating; skip self-referencing loops.
                if target != version and not target.startswith(rel):
                    ALIASES[rel] = target
                continue
        out.append(rel)
    return out


def main():
    global SRC, DST
    SRC, DST = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    versions_nav, redirects, count = [], [], 0
    # Discover every alias first so links into alias folders resolve from any version.
    sections = {version: section_dirs(version) for version in VERSIONS}
    for version in VERSIONS:
        groups = []
        for sdir in sections[version]:
            htmls = sorted(f for f in os.listdir(os.path.join(SRC, sdir)) if f.endswith(".html"))
            if not htmls:
                continue
            tree = read_navtree(sdir)
            seen = set()
            index_rel = posixpath.join(sdir, "index.html")
            pages = []
            if os.path.isfile(os.path.join(SRC, index_rel)):
                seen.add(index_rel)
                pages.append(page_path(index_rel))
            pages += nav_entries(sdir, tree[0][2] if tree else [], seen)
            titles = {}
            for f in htmls:
                rel = posixpath.join(sdir, f)
                count += 1
                titles[rel] = convert_page(rel)
                redirects.append({"source": "/" + rel, "destination": "/" + page_path(rel)})
                if version == LATEST:
                    redirects.append({"source": "/latest/" + rel[len(LATEST) + 1:], "destination": "/" + page_path(rel)})
                    redirects.append({"source": "/latest/" + page_path(rel)[len(LATEST) + 1:], "destination": "/" + page_path(rel)})
            # Pages the Doxygen tree did not list (or sections without a tree) go last, so every page stays reachable.
            pages += [page_path(posixpath.join(sdir, f)) for f in htmls if posixpath.join(sdir, f) not in seen]
            root_title = tree[0][0] if tree else titles.get(index_rel, sdir)
            for d in [sdir] + ([sdir.replace(LATEST, "latest", 1)] if version == LATEST else []):
                redirects.append({"source": "/" + d, "destination": "/" + sdir + "/index"})
            groups.append({"group": root_title, "pages": pages})
        entry = {"version": version, "groups": groups}
        if version == LATEST:
            entry["tag"] = "Latest"
        versions_nav.append(entry)
    for alias, target in sorted(ALIASES.items()):
        redirects.append({"source": "/%s/:slug*" % alias, "destination": "/%s/:slug*" % target})
        redirects.append({"source": "/" + alias, "destination": "/" + target + "/index"})
    redirects.append({"source": "/latest", "destination": "/"})
    redirects.append({"source": "/index.html", "destination": "/"})
    json.dump({"versions": versions_nav, "redirects": redirects}, open(os.path.join(os.path.dirname(__file__), "nav.json"), "w"), indent=2)
    print("pages", count, "images", len(set(image_cache.values())), "redirects", len(redirects))
    print("problems", len(problems))
    for p in sorted(set(problems))[:40]:
        print("  ", p)


if __name__ == "__main__":
    main()
