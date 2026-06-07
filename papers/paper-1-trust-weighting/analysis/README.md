# Paper 1 — analysis scripts

Scripts here import the Arasense platform and produce the paper's results/figures.

Run with the platform deps installed and the source on the path:

```bash
pip install -r ../../../requirements.txt
$env:PYTHONPATH = "$PWD\..\..\..\src"     # or: export PYTHONPATH=$(pwd)/../../../src
$env:ARASENSE_GCP_PROJECT = "valid-shine-488311-d6"
$env:GCP_SERVICE_ACCOUNT_JSON = (Get-Content path\to\key.json -Raw)
python <script>.py
```

Planned scripts (see ../outline.md, "what still needs building"):
- `e2_equal_weight_baseline.py` — weighted vs equal-weight projected change.
- `e3_climwip_compare.py`       — compare Aras weights to ClimWIP.
- `e4_perfect_model.py`         — perfect-model / leave-one-out validation.
- `figures.py`                  — render F1–F6 from saved results.

Heavy Earth Engine runs reuse the platform result cache; pre-warm with
`scripts/prewarm.py`. Keep raw outputs out of git (large); commit figures + the
small summary JSONs the paper cites.
