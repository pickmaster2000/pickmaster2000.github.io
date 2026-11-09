# Pickmaster 2000

Free, static college football against-the-spread dashboard published at https://pickmaster2000.github.io/.

## What works

- Loads the latest published Yahoo public pick-distribution game slate, including public spread and pick percentages.
- Offers preliminary, conservative statistical projections built from earlier completed ESPN scoreboards and the posted Yahoo spread.
- Lets the user override a projected margin, save projections on this device, and copy a pick sheet.
- Uses scheduled GitHub Actions and Python's standard library; no paid API or subscription required.
- Verifies Python syntax and browser JavaScript syntax before automated data updates.

## Limitations

- Projections are **experimental, not backtested, and are NOT reliable probabilities of covering**. An apparent modeled edge does not establish a profitable strategy.
- No verified injury, weather, or multi-AI feed is integrated; the model never pretends to know those inputs.
- The Yahoo public slate/lines may differ from the locked lines or games in the user's private group.
- Yahoo may alter its HTML or limit scripted access. When the fetch fails, the last verified snapshot remains in place.
- Some team names and short histories cannot be resolved reliably, so those matchups receive no model pick.
- Saved overrides stay in the browser/device only; the site does not place bets or submit Yahoo picks.

## Maintenance

GitHub Actions workflow `.github/workflows/update.yml` runs on a schedule or manually from the repository's Actions tab, and also after site/script edits on the main branch. It validates Python and frontend JavaScript, refreshes available Yahoo public snapshots, runs `scripts/build_predictions.py`, and commits changed JSON files under `data/`.

If Yahoo retrieval fails, inspect the [Actions page](https://github.com/pickmaster2000/pickmaster2000.github.io/actions). The site's Refresh button reloads *published* files; it cannot directly start a GitHub Action. GitHub Pages publication and data retrieval are separate workflows.
