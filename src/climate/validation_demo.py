import ee
from data_fetcher import ArasenseDataFetcher
from aras_eval import ArasDiagram

# ─────────────────────────────────────────────────────────────────
#  BUGS FIXED in validation_demo.py
#
#  BUG 1 — ArasDiagram called with wrong data structure
#    Original:
#        ArasDiagram(reference_data=data['reference'],
#                    model_data=[data['model']], ...)
#    data_fetcher returns a dict where data[model_name] is a DataFrame
#    with columns ['reference','model'], NOT a separate data['model'] key.
#    Fix: extract the correct columns from the per-model DataFrame.
#
#  BUG 2 — Wrong metric keys used when printing results
#    Original code prints results['correlation'] and results['e_total']
#    but ArasDiagram stores these as results['r'] and results['e_pct'].
#    Also prints alpha/beta with wrong labels (labels are swapped).
#    Fix: use the correct key names and correct labels from the paper:
#         x-axis = β-1 (bias),  y-axis = α-1 (variability).
#
#  BUG 3 — No model found guard
#    If GEE returns no CMIP6 data (quota, auth, empty range) the loop
#    over model results would crash with an IndexError.
#    Fix: check that at least one model was fetched before proceeding.
# ─────────────────────────────────────────────────────────────────


def run_validation():
    PROJECT_ID = 'valid-shine-488311-d6'
    fetcher    = ArasenseDataFetcher(PROJECT_ID)

    # 1. Define ROI (Rome area — 100 km radius)
    roi = ee.Geometry.Point([12.4964, 41.9028]).buffer(100000)

    # 2. Fetch data (temperature, 2014)
    print("Step 1: Fetching real data from GEE...")
    data = fetcher.get_climate_data(
        roi, '2014-01-01', '2014-12-31', 'temperature'
    )

    # FIX BUG 3: guard against empty fetch
    model_names = [k for k in data.keys() if k != 'reference']
    if not model_names:
        print("No CMIP6 model data was retrieved. "
              "Check your GEE credentials and quota.")
        return

    # 3. Build inputs for ArasDiagram
    #    FIX BUG 1: each data[model_name] is a DataFrame with
    #               columns ['reference', 'model'] — extract correctly.
    print("\nStep 2: Calculating Aras Metrics...")

    reference_series = data['reference']   # top-level ERA5 series
    model_series_list = []
    valid_names       = []

    for m_name in model_names:
        df = data[m_name]                  # DataFrame: ['reference','model']
        if df.empty:
            print(f"  Skipping {m_name} — empty after alignment.")
            continue
        model_series_list.append(df['model'].values)
        valid_names.append(m_name)

    if not model_series_list:
        print("All model series were empty after alignment. Exiting.")
        return

    # Use the reference column from the first aligned DataFrame
    # (guaranteed to match in time with the model columns)
    aligned_ref = data[valid_names[0]]['reference'].values

    aras = ArasDiagram(
        reference_data = aligned_ref,
        model_data     = model_series_list,
        model_names    = valid_names,
    )

    # 4. Print results
    #    FIX BUG 2: correct key names (r, e_pct) and correct labels
    print("\n--- Arasense Evaluation Results ---")
    for res in aras.results:
        print(f"\nModel : {res['name']}")
        print(f"  β - 1 (Bias ratio - 1)       : {res['beta']:+.4f}")
        print(f"  α - 1 (Variability ratio - 1): {res['alpha']:+.4f}")
        print(f"  Pearson r                    : {res['r']:.4f}")
        print(f"  KGE                          : {res['kge']:.4f}")
        print(f"  Total Error E (%)            : {res['e_pct']:.2f} %")
    print("-----------------------------------")

    # 5. Plot and save
    fig = aras.plot(
        title      = "Aras' Diagram — ERA5 vs CMIP6 Historical (Rome, 2014)",
        bg_color   = 'white',
        text_color = 'black',
    )
    out_path = "aras_diagram_italy.png"
    fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\nDiagram saved → {out_path}")


if __name__ == "__main__":
    run_validation()
