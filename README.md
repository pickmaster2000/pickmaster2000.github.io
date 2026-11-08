# Pickmaster 2000

Static GitHub Pages dashboard with a GitHub Actions job that **attempts** to retrieve Yahoo's public college football Pick Distribution. No paid services or API keys.

## Install in your existing repository

Upload `index.html`, `scripts/fetch_yahoo.py`, `.github/workflows/update.yml`, and the `data` folder into the matching paths on the `main` branch. **Do not upload the ZIP itself as the site.** For easiest installation, extract the ZIP on your computer and use GitHub's upload interface (which may not preserve empty directories), or create the nested files using GitHub's Add file > Create new file and paste contents.

Then open repository **Actions > Update Yahoo public data > Run workflow**. The job runs on a schedule as well. If the fetch fails or Yahoo changes markup, no invented data is saved. Check Actions logs. Github Actions permissions may require Settings > Actions > General > Workflow permissions > Read and write permissions.

## Limitations

- Public Yahoo page may block automated retrieval. This has **not been verified from GitHub Actions**.
- Public Yahoo distribution may not match your group's slate or official locked Thursday spreads.
- Public pick percentages are NOT an ATS prediction model. Enter an independently sourced projected margin to calculate an illustrative probability (assumed 14-point margin uncertainty). Do not treat as calibrated.
- This version does not retrieve injuries/weather/team analytics or sync picks between devices.
- Refresh button fetches the latest stored snapshot; GitHub workflow retrieves fresh data independently. To force a new retrieval use Actions > Run workflow.
