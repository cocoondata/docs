"""Write docs.json and the landing page for the converted Cocoon Data docs.

Usage: python build_config.py <mintlify-repo-root>
Reads nav.json produced by convert.py.
"""

import json
import os
import re
import sys

ROOT = os.path.abspath(sys.argv[1])
nav = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nav.json")))

ICONS = {
    "user": "user",
    "admin": "user-gear",
    "admin-org": "building",
    "admin-platform": "server",
    "api": "code",
    "restapi": "code",
    "windows": "windows",
    "ms-addins": "microsoft",
    "compatweb": "globe",
}

# Plain names for the landing page; group titles in the sidebar keep the original wording.
CARD_TITLES = {
    "user": ("SafeShare for Web user guide", "Sign in, upload, share, and manage secure content."),
    "windows": ("SafeShare for Windows user guide", "Use SafeShare from Windows File Explorer."),
    "ms-addins": ("Microsoft add-ins", "Protect and share content from Microsoft Office and Outlook."),
    "admin-org": ("Organisation administrator guide", "Manage users, groups, clearances, and settings for an organisation."),
    "admin-platform": ("SafeShare administrator guide", "Configure and operate the SafeShare platform."),
    "api": ("API reference", "Integrate with the SafeShare access and content services."),
}

latest = nav["versions"][0]

# The landing page belongs to the default version so it appears in its sidebar.
latest["groups"].insert(0, {"group": "Overview", "pages": ["index"]})

docs = {
    "$schema": "https://mintlify.com/docs.json",
    "theme": "mint",
    "name": "Cocoon Data Documentation",
    "colors": {"primary": "#2E0161", "light": "#B9A2E8", "dark": "#2E0161"},
    "favicon": "/favicon.png",
    "logo": {"light": "/logo/light.png", "dark": "/logo/dark.png", "href": "https://cocoondata.com"},
    "fonts": {"family": "Inter"},
    "navigation": {
        "versions": nav["versions"],
        "global": {
            "anchors": [
                {"anchor": "Cocoon Data", "href": "https://cocoondata.com", "icon": "globe"},
                {"anchor": "Support", "href": "https://cocoondata.com/support", "icon": "life-ring"},
            ]
        },
    },
    "navbar": {"links": [{"label": "Support", "href": "https://cocoondata.com/support"}]},
    "contextual": {"options": ["copy", "view", "chatgpt", "claude", "perplexity", "mcp", "cursor", "vscode"]},
    "footer": {"socials": {"website": "https://cocoondata.com"}},
    # Mintlify serves <folder>/index.mdx at the folder address: point redirects there, and drop folder-to-index loops.
    "redirects": [
        {"source": r["source"], "destination": re.sub(r"/index$", "", r["destination"]) or "/"}
        for r in nav["redirects"]
        if r["source"] != (re.sub(r"/index$", "", r["destination"]) or "/")
    ],
}
with open(os.path.join(ROOT, "docs.json"), "w") as fh:
    json.dump(docs, fh, indent=2)
    fh.write("\n")

cards = []
for group in latest["groups"][1:]:
    first = group["pages"][0]
    first = first if isinstance(first, str) else first["pages"][0]
    section = first.split("/")[-2]
    title, blurb = CARD_TITLES.get(section, (group["group"], "Version " + latest["version"]))
    cards.append(
        '  <Card title="%s" icon="%s" href="/%s">\n    %s\n  </Card>'
        % (title.replace('"', "&quot;"), ICONS.get(section, "book"), re.sub(r"/index$", "", first), blurb)
    )

landing = """---
title: "Cocoon Data documentation"
description: "Guides and API references for SafeShare by Cocoon Data."
mode: "wide"
---

Choose a guide below for the latest release (%s). Documentation for earlier releases is available from the version selector.

<CardGroup cols={2}>
%s
</CardGroup>

""" % (latest["version"], "\n".join(cards))
with open(os.path.join(ROOT, "index.mdx"), "w") as fh:
    fh.write(landing)
print("docs.json written:", len(nav["versions"]), "versions,", len(nav["redirects"]), "redirects;", len(cards), "landing cards")
