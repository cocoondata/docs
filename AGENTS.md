# Documentation project instructions

## About this project

- Product documentation for SafeShare by Cocoon Data, built on [Mintlify](https://mintlify.com) and published at `docs.cocoondata.com`.
- Pages are MDX files with YAML frontmatter. Configuration lives in `docs.json`.
- Commits to `main` deploy the site.
- Preview locally with `mint dev`. Before committing, run `mint validate` and `mint broken-links`; both must pass.

## How the content was produced

- The content was migrated on 2026-10-23 from the legacy Doxygen site that ran on the old AWS server. The server copy was the source of truth; the older Bitbucket repository (`cocoondata/public-product-documentation`) is out of date.
- Each release is a Mintlify version: `CS1.2` (default, tagged Latest), `CS1.0`, `3.5`, `3.4`, `3.3`, `3.2`, `3.1`, `3.0`, `2.16`.
- Paths mirror the legacy site without the `.html` extension, for example `/3.4/user/signing-in`. German translations live under `<version>/de/<section>/`.
- `docs.json` holds one redirect per legacy page (`.html` addresses and `/latest/...` addresses), plus wildcard redirects for legacy folder aliases such as `restapi`. Do not remove them; external sites link to the old addresses.
- Images are stored once in `images/`, named `<content hash>-<original name>`, and shared across versions.

## Terminology

- Use the product names as they appear in each version's pages (for example "Safe Share" in 3.x and "SafeShare" in CS releases); do not rewrite historical content.
- "Organisation" uses Australian and British spelling throughout.

## Style preferences

- Use active voice and second person ("you").
- Keep sentences concise, one idea per sentence.
- Use sentence case for headings.
- Bold for UI elements: Click **Settings**.
- Code formatting for file names, commands, paths, and code references.

## Content boundaries

- Legacy release documentation is archival. Fix errors and broken links, but do not restructure or modernise old versions.
- New product documentation should go into a new version entry in `docs.json`.
