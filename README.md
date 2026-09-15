# Hyung Suk Kim — ORCID-linked researcher profile

A static GitHub Pages site designed as the personal scholarly-record companion to MAXAM Labo.

## What it does

- Dark, responsive academic profile.
- Publications rendered from `data/publications.json`.
- Peer-review activity rendered from `data/peer_reviews.json` when present in the public ORCID record.
- Search and year filtering in the browser.
- Selected papers controlled by `data/featured.json`.
- Daily GitHub Action reads the public ORCID record and updates the publication and peer-review JSON.
- ORCID client secret never appears in browser-side code.

## Deploy

Copy the contents of this folder into the root of the `hyung-suk-kim.github.io` repository and push to `main`.

GitHub Pages should use **Deploy from a branch** → `main` → `/ (root)`.

## Enable ORCID auto-sync

ORCID's Public API requires Public API credentials for the `/read-public` token flow.

1. Sign in to ORCID and register a Public API client in ORCID Developer Tools.
2. In the GitHub repository go to **Settings → Secrets and variables → Actions**.
3. Create these repository secrets:
   - `ORCID_CLIENT_ID`
   - `ORCID_CLIENT_SECRET`
4. Open **Actions → Sync ORCID record → Run workflow** once.
5. Thereafter it runs once daily at 11:17 KST.

The workflow writes only public ORCID work data and public ORCID peer-review data to the JSON files and commits changes when the record differs.

## Choose selected papers

Edit `data/featured.json` and list up to four DOI strings. The public page marks matching ORCID works as selected automatically after the next sync.

## Peer review data

`data/peer_reviews.json` contains only public peer-review records imported from ORCID. The site intentionally does not maintain a separate manual reviewer-service list.

## Customize profile text

Edit `index.html`. No framework or build step is required.

## Important

Do not place `ORCID_CLIENT_SECRET` in HTML, JavaScript, JSON, or any committed file. Keep it only in GitHub Actions secrets.
