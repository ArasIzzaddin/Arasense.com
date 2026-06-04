import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle
from matplotlib.lines import Line2D

# ─────────────────────────────────────────────────────────────────
#  BUG SUMMARY (Izzaddin et al. 2024 paper as reference)
#
#  BUG 1 — alpha / beta SWAPPED (CRITICAL)
#    Paper:  alpha = σ_m / σ_o   (variability ratio)  → y-axis
#            beta  = μ_m / μ_o   (bias ratio)          → x-axis
#    Code:   alpha = (μ_m/μ_o) - 1   ← this is beta
#            beta  = (σ_m/σ_o) - 1   ← this is alpha
#    Fix:    swap the formulas.
#
#  BUG 2 — AXES LABELS SWAPPED (consequence of Bug 1)
#    Code:   x-label = "Bias ratio - 1 (α)"       ← wrong
#            y-label = "Variability ratio - 1 (β)" ← wrong
#    Fix:    x-axis = β-1 (bias),  y-axis = α-1 (variability)
#
#  BUG 3 — SEGMENT DRAWN IN WRONG DIRECTION (CRITICAL)
#    Paper:  segment goes FROM E_αβ TOWARD total error E
#            i.e. segment starts at (β-1, α-1) and extends outward
#    Code:   segment drawn from (x2,y2) TO (alpha,beta) — reversed
#    Fix:    compute E_total point correctly and draw from E_αβ to E.
#
#  BUG 4 — SEGMENT ENDPOINT (x2, y2) COMPUTED INCORRECTLY
#    Paper:  E_total point lies at distance mkge from origin,
#            in the direction of E_αβ from the origin.
#            x_E = (β-1) * mkge / el
#            y_E = (α-1) * mkge / el
#    Code:   x2 = alpha + mmkge*(alpha/el)  ← wrong formula
#    Fix:    compute E_total as the point at distance mkge
#            from origin along the (β-1, α-1) direction.
#
#  BUG 5 — PERCENTAGE ERROR CIRCLES WRONG SCALE
#    Paper:  circles at 10%, 25%, 50% → radii = 0.10, 0.25, 0.50
#    Code:   circles at 0.1, 0.2, 0.3, 0.4, 0.5 (missing 0.25)
#    Fix:    use exactly [0.10, 0.25, 0.50] per the paper.
# ─────────────────────────────────────────────────────────────────


class ArasDiagram:
    """
    Correct implementation of the Aras Diagram (Izzaddin et al., 2024).

    Axes:
        x-axis : β - 1  = (μ_model / μ_obs) - 1   (normalized bias ratio)
        y-axis : α - 1  = (σ_model / σ_obs) - 1   (variability ratio)

    For each model the diagram shows:
        • Circle at (β-1, α-1)  — E_αβ : bias+variability error
          filled  = positive correlation
          hollow  = negative correlation
        • Segment from E_αβ to E_total
          length  = correlation error contribution  |ρ-1|
          slope   = tan(φ) = (α-1)/(β-1)
        • Concentric circles at 10 %, 25 %, 50 % total error
    """

    # Denominators below these magnitudes make the bias/variability ratios
    # unstable; see the guards in __init__.
    MEAN_EPS = 1e-6
    STD_EPS  = 1e-9

    def __init__(self, reference_data, model_data, model_names=None):
        self.ref   = np.array(reference_data)
        self.models = [np.array(m) for m in model_data]
        self.model_names = (model_names if model_names
                            else [f"Model {i+1}" for i in range(len(model_data))])

        self.ref_mean = np.mean(self.ref)
        self.ref_std  = np.std(self.ref, ddof=0)   # population std, consistent with KGE

        # ── divide-by-zero guards ────────────────────────────────────
        # The bias ratio  β = μ_model / μ_obs  and variability ratio
        # α = σ_model / σ_obs  are both ratios. They are undefined when the
        # reference (observed) denominator is ≈ 0:
        #   • μ_obs ≈ 0  → zero-centred variables: temperature in °C, anomalies.
        #                  Temperature MUST be supplied in Kelvin (μ_obs ≈ 273–300),
        #                  never Celsius, so the bias ratio stays well-conditioned.
        #   • σ_obs ≈ 0  → a flat/constant reference series, no variability to match.
        # We fail loudly with an actionable message instead of emitting ±inf / NaN.
        if abs(self.ref_mean) < self.MEAN_EPS:
            raise ValueError(
                "Aras diagram bias ratio β = mean(model) / mean(obs) is undefined "
                f"because the reference mean ≈ 0 (mean(obs) = {self.ref_mean:.3e}). "
                "Supply temperature in Kelvin rather than Celsius, or use a variable "
                "that is not zero-centred. For anomaly fields, switch to a "
                "standardized-difference bias term instead of the ratio."
            )
        if self.ref_std < self.STD_EPS:
            raise ValueError(
                "Aras diagram variability ratio α = std(model) / std(obs) is undefined "
                f"because the reference series is (near) constant (std(obs) = {self.ref_std:.3e})."
            )

        self.results = []
        self._calculate_metrics()

    # ── metrics ───────────────────────────────────────────────────
    def _calculate_metrics(self):
        for name, m_data in zip(self.model_names, self.models):
            m_mean = np.mean(m_data)
            m_std  = np.std(m_data, ddof=0)
            r      = np.corrcoef(self.ref, m_data)[0, 1]

            # FIX BUG 1: correct definitions from the paper
            alpha = m_std  / self.ref_std  - 1   # variability ratio - 1  → y-axis
            beta  = m_mean / self.ref_mean - 1   # bias ratio - 1         → x-axis

            # KGE components (Eq. 10–11 in paper)
            E_ab    = alpha**2 + beta**2          # bias+variability error
            E_r     = (r - 1)**2                  # correlation error component
            E_total = E_ab + E_r                  # total error = (1-KGE)²

            kge  = 1 - np.sqrt(E_total)
            mkge = np.sqrt(E_total)               # = |1 - KGE|, distance from origin

            el   = np.sqrt(E_ab)                  # distance of E_αβ from origin

            # FIX BUG 3 & 4: E_total point lies at distance mkge from origin
            # in the SAME direction as E_αβ (paper Fig. 1)
            if el > 1e-12:
                # unit vector toward E_αβ
                ux = beta  / el
                uy = alpha / el
                # total-error endpoint
                x_E = ux * mkge
                y_E = uy * mkge
            else:
                # E_αβ at origin → segment goes along positive x by convention
                x_E = mkge
                y_E = 0.0

            self.results.append({
                'name'    : name,
                'alpha'   : alpha,        # variability ratio - 1
                'beta'    : beta,         # bias ratio - 1
                'r'       : r,
                'kge'     : kge,
                'E_ab'    : E_ab,
                'E_total' : E_total,
                'mkge'    : mkge,         # total error (distance from origin)
                'el'      : el,           # bias+var error (distance of E_αβ)
                'x_E'     : x_E,          # total-error point x
                'y_E'     : y_E,          # total-error point y
                'e_pct'   : mkge * 100,   # total percentage error
            })

    # ── main plot ─────────────────────────────────────────────────
    def plot(self, title="Aras' Diagram", figsize=(10, 10),
             bg_color='white', text_color='black',
             circle_colors=None):
        """
        Produce a publication-quality Aras diagram.

        Parameters
        ----------
        title        : str
        figsize      : tuple
        bg_color     : str  — 'white' for papers, 'black' for dark style
        text_color   : str
        circle_colors: list of 3 colors for 10/25/50% circles (optional)
        """
        dark = (bg_color in ('black', '#000000', '#111111'))
        if circle_colors is None:
            circle_colors = (['#2ecc71', '#f39c12', '#e74c3c'] if dark
                             else ['#27ae60', '#e67e22', '#c0392b'])

        fig, ax = plt.subplots(figsize=figsize,
                               facecolor=bg_color)
        ax.set_facecolor(bg_color)

        # ── axis limits ──────────────────────────────────────────
        vals = []
        for res in self.results:
            vals += [res['beta'], res['alpha'], res['x_E'], res['y_E']]
        lim = max(max(abs(v) for v in vals) * 1.25, 0.6)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)

        # ── concentric error circles (FIX BUG 5) ─────────────────
        for rad, clr, pct in zip([0.10, 0.25, 0.50],
                                  circle_colors,
                                  ['10 %', '25 %', '50 %']):
            ax.add_patch(Circle((0, 0), rad,
                                fill=False, linestyle='--',
                                edgecolor=clr, linewidth=1.2,
                                alpha=0.7, zorder=1))
            ax.text(rad * 0.72, rad * 0.72, pct,
                    color=clr, fontsize=9, alpha=0.85,
                    ha='center', va='center')

        # ── axes lines ───────────────────────────────────────────
        ax.axhline(0, color=text_color, lw=1.0, alpha=0.4)
        ax.axvline(0, color=text_color, lw=1.0, alpha=0.4)

        # ── origin marker ────────────────────────────────────────
        ax.scatter([0], [0], s=80, color='blue',
                   marker='+', linewidths=2, zorder=6,
                   label='Perfect model')

        # ── model points & segments ──────────────────────────────
        cmap   = plt.get_cmap('tab20')
        handles = [Line2D([0], [0], marker='+', color='blue',
                          linestyle='None', markersize=10,
                          label='Perfect model')]

        for i, res in enumerate(self.results):
            color = cmap(i % 20)
            bx, ay = res['beta'], res['alpha']   # E_αβ coords
            xE, yE = res['x_E'],  res['y_E']     # E_total coords

            # FIX BUG 3: segment from E_αβ → E_total (outward)
            ax.annotate('',
                        xy     =(xE, yE),
                        xytext =(bx, ay),
                        arrowprops=dict(arrowstyle='-',
                                        color=color,
                                        lw=1.8,
                                        alpha=0.85))

            # E_αβ circle: filled = positive r, hollow = negative r
            if res['r'] >= 0:
                ax.scatter(bx, ay, s=110, color=color,
                           edgecolors='white', linewidths=0.8,
                           zorder=5)
            else:
                ax.scatter(bx, ay, s=110, facecolors='none',
                           edgecolors=color, linewidths=2,
                           zorder=5)

            # E_total endpoint (small diamond)
            ax.scatter(xE, yE, s=50, color=color,
                       marker='D', zorder=5, alpha=0.9)

            # label at E_αβ
            ax.text(bx + lim * 0.02, ay + lim * 0.02,
                    res['name'],
                    color=color if dark else 'black',
                    fontsize=8.5, alpha=0.95, zorder=7)

            handles.append(
                Line2D([0], [0], marker='o', color=color,
                       linestyle='-', markersize=7,
                       label=f"{res['name']}  "
                             f"(KGE={res['kge']:.2f}, "
                             f"E={res['e_pct']:.1f}%)"))

        # ── quadrant annotations ─────────────────────────────────
        qa = dict(color=text_color, fontsize=8.5, alpha=0.35,
                  ha='center', va='center')
        ax.text( lim * 0.6,  lim * 0.88, 'overest. mean\noverest. variability',  **qa)
        ax.text(-lim * 0.6,  lim * 0.88, 'underest. mean\noverest. variability', **qa)
        ax.text( lim * 0.6, -lim * 0.88, 'overest. mean\nunderest. variability', **qa)
        ax.text(-lim * 0.6, -lim * 0.88, 'underest. mean\nunderest. variability',**qa)

        # ── labels & legend ──────────────────────────────────────
        ax.set_xlabel('β - 1  =  (μ_model / μ_obs) - 1   [Bias ratio]',
                      fontsize=12, color=text_color, fontweight='bold')
        ax.set_ylabel('α - 1  =  (σ_model / σ_obs) - 1   [Variability ratio]',
                      fontsize=12, color=text_color, fontweight='bold')
        ax.set_title(title, fontsize=14, color=text_color,
                     fontweight='bold', pad=14)
        ax.tick_params(colors=text_color)
        for spine in ax.spines.values():
            spine.set_edgecolor(text_color)

        leg = ax.legend(handles=handles, loc='lower right',
                        fontsize=8.5,
                        facecolor=bg_color,
                        edgecolor=text_color,
                        framealpha=0.8)
        for t in leg.get_texts():
            t.set_color(text_color)

        ax.grid(True, linestyle=':', alpha=0.18, color=text_color)
        plt.tight_layout()
        return fig

    # ── interactive Plotly plot (for website) ─────────────────────
    def plot_interactive(self, title="Aras' Diagram"):
        """
        Plotly version for interactive website rendering.

        BUGS FIXED vs original plot() method:
          1. E_total (diamond) point was never plotted — only E_αβ was shown,
             making each model appear as a single point.
          2. Wrong result keys used: 'x2'/'y2' → 'x_E'/'y_E', 
             'alpha'/'beta' axes were swapped (x=alpha, y=beta → x=beta, y=alpha).
          3. Segment drawn with wrong endpoint coordinates.
          4. No error circles drawn at all.
          5. No hover info on total error point.
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            raise ImportError("plotly is required for plot_interactive(). "
                              "Install with: pip install plotly")

        colors = [
            '#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
            '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
        ]

        fig = go.Figure()

        # ── axis limits ──────────────────────────────────────────
        vals = []
        for res in self.results:
            vals += [res['beta'], res['alpha'], res['x_E'], res['y_E']]
        lim = max(max(abs(v) for v in vals) * 1.3, 0.6)

        # ── concentric error circles ──────────────────────────────
        circle_styles = [
            (0.10, '#27ae60', '10%'),
            (0.25, '#e67e22', '25%'),
            (0.50, '#c0392b', '50%'),
        ]
        theta = [i * 2 * 3.14159 / 360 for i in range(361)]
        import math
        for rad, clr, label in circle_styles:
            fig.add_trace(go.Scatter(
                x=[rad * math.cos(t) for t in theta],
                y=[rad * math.sin(t) for t in theta],
                mode='lines',
                line=dict(color=clr, width=1, dash='dash'),
                showlegend=False,
                hoverinfo='skip',
            ))
            fig.add_annotation(
                x=rad * 0.72, y=rad * 0.72,
                text=label, showarrow=False,
                font=dict(size=10, color=clr),
            )

        # ── axes lines ────────────────────────────────────────────
        for xy in ['x', 'y']:
            fig.add_shape(type='line',
                x0=-lim if xy=='x' else 0, x1=lim if xy=='x' else 0,
                y0=0 if xy=='x' else -lim, y1=0 if xy=='x' else lim,
                line=dict(color='gray', width=1))

        # ── origin ────────────────────────────────────────────────
        fig.add_trace(go.Scatter(
            x=[0], y=[0], mode='markers',
            marker=dict(size=12, color='blue', symbol='cross'),
            name='Perfect model',
            hovertemplate='Perfect model<extra></extra>',
        ))

        # ── model traces ──────────────────────────────────────────
        for i, res in enumerate(self.results):
            color = colors[i % len(colors)]
            bx, ay = res['beta'],  res['alpha']   # E_αβ
            xE, yE = res['x_E'],   res['y_E']     # E_total

            # 1. Segment: E_αβ → E_total
            fig.add_trace(go.Scatter(
                x=[bx, xE], y=[ay, yE],
                mode='lines',
                line=dict(color=color, width=2),
                showlegend=False,
                hoverinfo='skip',
            ))

            # 2. E_αβ circle — filled (r≥0) or open (r<0)
            marker_symbol = 'circle' if res['r'] >= 0 else 'circle-open'
            fig.add_trace(go.Scatter(
                x=[bx], y=[ay],
                mode='markers+text',
                name=res['name'],
                text=[res['name']],
                textposition='top right',
                textfont=dict(size=10),
                marker=dict(
                    size=13,
                    color=color,
                    symbol=marker_symbol,
                    line=dict(color='white', width=1.5),
                ),
                hovertemplate=(
                    f"<b>{res['name']} — E_αβ</b><br>"
                    f"β-1 (bias): {bx:+.3f}<br>"
                    f"α-1 (variability): {ay:+.3f}<br>"
                    f"r: {res['r']:.3f}"
                    "<extra></extra>"
                ),
            ))

            # 3. E_total diamond — THIS WAS MISSING in original code
            fig.add_trace(go.Scatter(
                x=[xE], y=[yE],
                mode='markers',
                showlegend=False,
                marker=dict(
                    size=10,
                    color=color,
                    symbol='diamond',
                    opacity=0.95,
                    line=dict(color='white', width=1),
                ),
                hovertemplate=(
                    f"<b>{res['name']} — E total</b><br>"
                    f"KGE: {res['kge']:.3f}<br>"
                    f"E: {res['e_pct']:.1f}%<br>"
                    f"Correlation error: {abs(res['r']-1):.3f}"
                    "<extra></extra>"
                ),
            ))

        # ── quadrant labels ───────────────────────────────────────
        for tx, ty, label in [
            ( lim*0.6,  lim*0.85, 'overest. mean<br>overest. variability'),
            (-lim*0.6,  lim*0.85, 'underest. mean<br>overest. variability'),
            ( lim*0.6, -lim*0.85, 'overest. mean<br>underest. variability'),
            (-lim*0.6, -lim*0.85, 'underest. mean<br>underest. variability'),
        ]:
            fig.add_annotation(x=tx, y=ty, text=label, showarrow=False,
                               font=dict(size=9, color='gray'),
                               align='center')

        fig.update_layout(
            title=dict(text=title, font=dict(size=16), x=0.5),
            xaxis=dict(
                title='β - 1  =  (μ_model / μ_obs) - 1   [Bias ratio]',
                range=[-lim, lim], zeroline=False, showgrid=True,
                gridcolor='rgba(128,128,128,0.15)',
            ),
            yaxis=dict(
                title='α - 1  =  (σ_model / σ_obs) - 1   [Variability ratio]',
                range=[-lim, lim], zeroline=False, showgrid=True,
                gridcolor='rgba(128,128,128,0.15)',
                scaleanchor='x', scaleratio=1,   # keep aspect ratio square
            ),
            template='plotly_white',
            width=750, height=750,
            legend=dict(
                bgcolor='rgba(255,255,255,0.85)',
                bordercolor='lightgray',
                borderwidth=1,
                font=dict(size=10),
            ),
            margin=dict(l=70, r=40, t=60, b=70),
        )
        return fig

    # ── summary table ─────────────────────────────────────────────
    def summary(self):
        """Print a formatted summary table of all model metrics."""
        header = (f"{'Model':<18} {'β-1':>7} {'α-1':>7} "
                  f"{'r':>6} {'KGE':>7} {'E (%)':>8}  Note")
        print(header)
        print('─' * len(header))
        for res in sorted(self.results, key=lambda x: x['e_pct']):
            note = ('neg. corr.' if res['r'] < 0 else
                    'KGE ≥ 0.75' if res['kge'] >= 0.75 else '')
            print(f"{res['name']:<18} "
                  f"{res['beta']:>7.3f} "
                  f"{res['alpha']:>7.3f} "
                  f"{res['r']:>6.3f} "
                  f"{res['kge']:>7.3f} "
                  f"{res['e_pct']:>7.1f}%  {note}")


# ─────────────────────────────────────────────────────────────────
#  DEMO — reproduce a typical EURO-CORDEX-style evaluation
# ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    np.random.seed(42)
    n   = 50
    obs = np.random.normal(10, 2, n)          # reference observations

    # Simulate 6 models with varying bias, variability, correlation
    models = [
        obs * 1.05 + np.random.normal(0.3, 0.3, n),   # slight overest
        obs * 0.90 + np.random.normal(-0.5, 0.5, n),  # underest mean
        obs * 1.20 + np.random.normal(1.0, 0.8, n),   # large overest
        obs * 1.00 + np.random.normal(0.0, 0.1, n),   # near-perfect
        np.random.normal(10, 3, n),                    # uncorrelated
        obs * 0.80 + np.random.normal(-1.0, 0.4, n),  # underest both
    ]
    names = ['RCM-A', 'RCM-B', 'RCM-C', 'RCM-D (best)', 'RCM-E', 'RCM-F']

    diagram = ArasDiagram(obs, models, names)
    diagram.summary()

    fig = diagram.plot(title="Aras' Diagram — Demo (light)",
                       bg_color='white', text_color='black')
    fig.savefig('/mnt/user-data/outputs/aras_diagram_demo.png',
                dpi=150, bbox_inches='tight', facecolor='white')
    print("\nSaved → aras_diagram_demo.png")
