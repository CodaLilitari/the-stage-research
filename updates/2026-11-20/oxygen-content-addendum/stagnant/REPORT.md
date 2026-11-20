# What a measured tissue oxygen profile can resolve

Radisic and colleagues measured oxygen concentration across statically cultured cardiac tissue. The conference report labels the stagnant centerline series as the mean and standard error for four constructs. A separate externally flowed series uses three constructs observed at four radial positions. The centerline result below uses the investigators’ recorded concentrations. The fitted solid curve drawn on the same plot was excluded from digitization. [Authors’ Figure 4 and parameter table](https://skoge.folk.ntnu.no/prost/proceedings/aiche-2005/non-topical/Non%20topical/papers/306e.pdf) · [Related journal study](https://doi.org/10.1002/bit.20722)

We recovered 19 stagnant mean concentrations at 100 µm intervals from 0 to 1800 µm, using the centers of their error-bar caps. The two endpoint readings were **176.00 and 22.01 µmol/L**. The paper separately lists **175.6 and 22.4 µmol/L**. The ±1.5-source-pixel reading allowance corresponds to ±2.94 µmol/L. The reported standard errors refer to between-construct sampling and are recorded separately.

## Oxygen demand conditional on diffusion

In a stationary one-dimensional diffusion model with constant diffusivity, the curvature of the concentration is the local oxygen demand divided by diffusivity. Among nonnegative demand distributions consistent with the plotted means and reading allowance, the integrated curvature from **200 to 1600 µm** ranges from **0.00747 to 0.14712 (µmol/L)/µm**. Adding each point’s reported standard error to its reading allowance widens this to **0–0.43156**. The expanded bands are a sensitivity calculation. Correlations among depths are unavailable.

For a stationary, nonnegative sink and the authors’ reference tissue diffusivity of **2.0 × 10⁻⁵ cm²/s**, these intervals correspond to an inferred oxygen flux difference of **14.95–294.25 nmol m⁻² s⁻¹** under the reading allowance, or **0–863.12** with one standard error added pointwise. The diffusivity was a literature input to the authors’ model. Its value was not measured in these constructs. Changing that value proportionally changes the dimensional estimates.

The calculation bounds the integral without determining where the demand peaks. A single smooth constant-curvature profile fits within 0.161 times the one-SE-plus-reading bands. Replacing its uniform demand over one 100 µm interval by a symmetric concentrated demand over 10 µm, or even 1 µm, preserves the mass and first moment in that interval. Every recorded concentration in the grid remains exactly the same, while the possible local maximum increases tenfold or a hundredfold. A second construction preserves continuity with neighboring intervals using 5 µm boundary collars and a symmetric triangular peak. The peak widths are then 19 and 1.9 µm for the same two factors. Arbitrarily narrower peaks remain possible.

To compute the bound, write concentration as an affine function plus the integral of a nonnegative curvature distribution against the integrated-gradient kernel. Within each sampling interval, values at the measured nodes depend only on that interval’s total curvature and first moment. The code distributes that curvature to the two ends of its own cell while preserving both moments, then linear programming minimizes or maximizes the contribution from the selected cells. For continuous sources, the reported limits are infima and suprema. A source concentrated near either end can approach its point-mass representation. The measured bands admit a strictly feasible convex profile, so this approximation can preserve all the bands. Primal and dual optima agree to numerical tolerance.

## How tightly does the profile identify a first-order model?

Fitting a first-order sink to the 19 displayed stagnant means, with both mean boundary values fixed, gives an inverse length of **0.0007114 µm⁻¹** and **1.92 µmol/L** in-sample RMSE. A straight line through the same boundaries gives **12.58 µmol/L**. Under the reading allowance the necessary outer limits for this inverse length are 0.0006662–0.0007924 µm⁻¹. The replay supplies common boundary witnesses for every value in the interval 0.0006681–0.0007381 µm⁻¹. Allowing one published SE at each depth also admits a straight line with an adjusted pair of surface concentrations. The data identify the ratio of a first-order uptake coefficient to diffusivity only under the model assumptions. Multiplying both by the same positive factor preserves the entire concentration curve.

## Reproduction

With Python, NumPy 2, SciPy, Pillow and Poppler installed, download the conference PDF and run these commands in a copy of the supplement. Windows also supports Poppler installed in the default WSL distribution.

```sh
python prepare.py 306e.pdf
python convex_supply.py
python first_order.py
```

The first command verifies the source PDF SHA-256, checks the recorded error-cap positions against ink in the native raster and writes the measured concentration series to a local CSV. The other two commands write the identified intervals, numerical optimality checks and example solutions to JSON. The authors’ original artwork is available from the source cited above.
