# Cocoon Data documentation

Product documentation for SafeShare by Cocoon Data, published with [Mintlify](https://mintlify.com) at `docs.cocoondata.com`.

## Local preview

```bash
npm i -g mint
mint dev
```

The preview runs at `http://localhost:3000`.

## Before you commit

```bash
mint validate
mint broken-links
```

Both must pass. Commits to `main` deploy automatically.

## Structure

- `docs.json`: navigation (one Mintlify version per product release), branding, and redirects from legacy addresses.
- `<version>/<section>/*.mdx`: pages, for example `CS1.2/user/signing-in.mdx`. German translations are under `<version>/de/`.
- `images/`: shared images, named by content hash.
- `assets/`: downloadable files linked from pages.

See `AGENTS.md` for history and editing conventions.
