# Doxygen to Mintlify migration

These scripts produced the initial content of this repository on 2026-10-23 from the legacy Doxygen site at `docs.cocoondata.com` (the copy on the old AWS server, which was newer than the Bitbucket repository).

```bash
python3 -m venv .venv && .venv/bin/pip install beautifulsoup4==4.12.3 markdownify==0.13.1
.venv/bin/python convert.py <legacy-site-root> <this-repo-root>
.venv/bin/python build_config.py <this-repo-root>
```

`convert.py` writes the MDX pages, deduplicated images, and `nav.json` (navigation and redirects); `build_config.py` writes `docs.json` and `index.mdx`.

They are kept for reference only. The content in this repository is now the source of truth; edit the MDX files directly.
