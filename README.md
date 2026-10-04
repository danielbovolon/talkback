# Talkback

The daily brief for people who work with sound: studio, post, live, sound design and field recording.
Every morning: 16–24 verified news stories, a lesson and a 9-question audio quiz (pass with 9/9).

It's a static site: one `index.html`, a few images, and JSON files in `data/`. No build step, no server, no accounts.

## Deploy on GitHub Pages (once)

1. Create a new **public** repository on GitHub, e.g. `talkback`, without a README.
2. Upload everything in this folder (or push it with git, see below), keeping the folder structure, including the hidden `.github` folder and `.nojekyll`.
3. In the repo go to **Settings → Pages**. Under **Build and deployment → Source**, choose **GitHub Actions**.
4. Open the **Actions** tab. The "Deploy to GitHub Pages" workflow runs on every push. When it's green, your site is live at
   `https://<your-username>.github.io/talkback/`

With git from a terminal:

```bash
cd talkback-site
git init -b main
git add .
git commit -m "Talkback first release"
git remote add origin https://github.com/<your-username>/talkback.git
git push -u origin main
```

### Custom domain (optional)

Buy a domain (e.g. `talkback.audio`), then in **Settings → Pages → Custom domain** enter it and follow GitHub's DNS instructions. Tick **Enforce HTTPS** once it's available.

## Daily updates

New content is just new JSON files:

- `data/briefs/day-YYYY-MM-DD.json` (plus `week-YYYY-Www.json`, `month-YYYY-MM.json`, `year-YYYY.json`)
- `data/learn/YYYY-MM-DD.json` (lesson + quiz)

Commit them to `main`. The workflow validates every file, rebuilds `data/index.json` and redeploys. If a file is malformed the deploy fails and the live site keeps the previous version.

To preview locally:

```bash
python3 scripts/build_index.py
python3 -m http.server 8000
# open http://localhost:8000
```

(Opening `index.html` directly from disk won't load the data; browsers block that. Use the local server.)

## What's where

| Path | What it is |
| --- | --- |
| `index.html` | The whole app: layout, styles and code |
| `assets/` | Logo, app icons, favicon, social preview image |
| `manifest.webmanifest` | Lets people add Talkback to their home screen as an app |
| `data/` | Briefs, lessons and the generated `index.json` |
| `scripts/build_index.py` | Validates data and rebuilds the index |
| `.github/workflows/pages.yml` | Automatic deploy to GitHub Pages |

## Personalising

- **About text** is in the `<footer class="about">` block near the top of `index.html`. Add your name, Instagram handle or website there.
- **Social preview** (the image Instagram and WhatsApp show for links) is `assets/og-image.png`.

## Privacy

There's no tracking and no sign-in. Pins, the last-opened tab and quiz stats are stored only in each visitor's browser.
