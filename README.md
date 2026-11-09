# Pickmaster 2000

Free, static college football against-the-spread dashboard published at https://pickmaster2000.github.io/.

## What works

- Loads the latest published Yahoo public pick-distribution game slate, including public spread and pick percentages.
- Offers preliminary, conservative statistical projections built from earlier completed ESPN scoreboards and the posted Yahoo spread.
- Lets the user override a projected margin, save projections on this device, and copy a pick sheet.
- Uses scheduled GitHub Actions and Python's standard library; no paid API or subscription required.
- Verifies Python syntax and browser JavaScript syntax before automated data updates.

## Limitations

- Projections are **experimental and not validated by a genuine pregame backtest; they are NOT reliable probabilities of covering**. An apparent modeled edge does not establish a profitable strategy.
- No verified injury, weather, or multi-AI feed is integrated; the model never pretends to know those inputs.
- The Yahoo public slate/lines may differ from the locked lines or games in the user's private group.
- Yahoo may alter its HTML or limit scripted access. When the fetch fails, the last verified snapshot remains in place.
- Some team names and short histories cannot be resolved reliably, so those matchups receive no model pick.
- Saved overrides stay in the browser/device only; the site does not place bets or submit Yahoo picks.

## Model comparison and forward testing

- `scripts/challenger.py` fits separately regularized offensive and defensive strength as an **isolated challenger**, without changing the published picks.
- `scripts/compare_challenger.py` compares both models and trivial favorites/underdogs baselines on exactly the same matched historical games, storing `data/challenger_comparison.json`.
- Initial historical comparison: incumbent 72-86-5 (45.6%), offense/defense challenger 71-87-5 (44.9%), all underdogs 84-74-5 (53.2%). Those retrospective spreads may have changed after the game; none is a demonstrated betting edge.
- `scripts/freeze_pregame.py` records each game once before kickoff under `data/pregame/` and does not overwrite previous records. `scripts/prospective.py` scores only frozen pregame picks after final results. Its findings, stored in `data/prospective.json`, should guide future decisions as the sample grows.
- Injury, quarterback, weather, efficiency, or travel metrics must not be inferred from unrelated information; integrations should be independently verified and tested before altering production picks.

## Maintenance

GitHub Actions workflow `.github/workflows/update.yml` runs on a schedule or manually from the repository's Actions tab, and also after site/script edits on the main branch. It validates Python and frontend JavaScript, refreshes available Yahoo public snapshots, runs `scripts/build_predictions.py`, and commits changed JSON files under `data/`.

If Yahoo retrieval fails, inspect the [Actions page](https://github.com/pickmaster2000/pickmaster2000.github.io/actions). The site's Refresh button reloads *published* files; it cannot directly start a GitHub Action. GitHub Pages publication and data retrieval are separate workflows.
