"""Verbatim transcription of Coda's (Codex Lily) EXECUTED reference values used as independent
test targets.  Nothing here is computed; every number is copied from the quoted sources.
Sources: validation/thermal/reference_results.json
         (sha256 e97cf35c8accb051096fdca20ec89a0a157015b863e94cb01020a8fdb5af3a56),
         validation/thermal_transient/REPORT.md
         (sha256 86f9b6107dc2e62b9e497454924c3463230bc96ba9495ab0bdc2baa24d6b25a6).
Celsius values; eps = 0 (no radiation); h = 8 W/(m2 K); R_rej = 2 K/W unless blocked."""

STEADY_ROWS = [
    dict(stack="H1", body_power=1, rear_blocked=False, H=26.90248230028146, S=26.891868221020427,
         surface=26.85948562324088, front=0.14875884985927018, rear=0.9512411501407299,
         front_exact="239951/1613020"),
    dict(stack="H1", body_power=5, rear_blocked=False, H=33.83119986113005, S=33.70398462379287,
         surface=33.55500086793716, front=0.6844000694349729, rear=4.415599930565027,
         front_exact="1103951/1613020"),
    dict(stack="H1", body_power=10, rear_blocked=False, H=42.492096812190795, S=42.21913012725842,
         surface=41.92439492380752, front=1.3539515939046014, rear=8.7460484060954,
         front_exact="2183951/1613020"),
    dict(stack="H1", body_power=5, rear_blocked=True, H=90.94862037037036, S=89.86019444444445,
         surface=88.75, front=5.1, rear=0.0, front_exact="51/10"),
    dict(stack="H2", body_power=1, rear_blocked=False, H=26.907261860110584, S=26.88858113572823,
         surface=26.829613374308842, front=0.14636906994470728, rear=0.9536309300552928,
         front_exact="241951/1653020"),
    dict(stack="H2", body_power=5, rear_blocked=False, H=33.86190245732054, S=33.6326495680521,
         surface=33.36310964174662, front=0.6690487713397297, rear=4.430951228660271,
         front_exact="1105951/1653020"),
    dict(stack="H2", body_power=10, rear_blocked=False, H=42.55520320383298, S=42.062735108456934,
         surface=41.52997997604385, front=1.3223983980835077, rear=8.777601601916492,
         front_exact="2185951/1653020"),
    dict(stack="H2", body_power=5, rear_blocked=True, H=92.81899074074074, S=90.80463888888889,
         surface=88.75, front=5.1, rear=0.0, front_exact="51/10"),
    dict(stack="H3", body_power=1, rear_blocked=False, H=26.916159074909697, S=26.883744465399086,
         surface=26.774005781814406, front=0.1419204625451524, rear=0.9580795374548476,
         front_exact="245951/1733020"),
    dict(stack="H3", body_power=5, rear_blocked=False, H=33.91905575238601, S=33.501140687023764,
         surface=33.00590154758745, front=0.6404721238069959, rear=4.459527876193004,
         front_exact="1109951/1733020"),
    dict(stack="H3", body_power=10, rear_blocked=False, H=42.6726765992314, S=41.772885964054616,
         surface=40.79577125480375, front=1.2636617003843003, rear=8.836338299615699,
         front_exact="2189951/1733020"),
    dict(stack="H3", body_power=5, rear_blocked=True, H=96.55973148148148, S=92.69352777777777,
         surface=88.75, front=5.1, rear=0.0, front_exact="51/10"),
]

# One-node analytic fixture and backward-Euler errors (reference_results.json).
ONE_NODE = dict(initial_C=20, bath_C=20, power_W=3, resistance_K_W=2, capacity_J_K=10, time_s=20,
                exact_C=23.792723352971347,
                backward_euler_abs_error_K={1.0: 0.05406025020934635, 0.5: 0.027307095158171535,
                                            0.25: 0.013724073533140313})

# Coupled equal-capacity two-node eigenmode check (REPORT.md): max errors at t = 1 s for dt .1/.05/.025.
TWO_NODE_MODE_ERRORS_K = (0.020207465088315557, 0.01016162613712357, 0.005091732219151546)

# REPORT.md fault-suite table, sensor-on cases (Celsius, 6 decimals as printed).
# ASSUMPTION (Red): the REPORT does not state the scenario timestep; dt = 1 s is assumed because
# peak times are reported at 1-second resolution.  A mismatch would show as a ~1e-2 K discrepancy.
TRANSIENT_REPORT = {
    ("H1", "intact"):    dict(peak_H_C=33.831193, peak_H_time_s=900.0, peak_surface_C=33.554994, H_3600_C=25.170303),
    ("H1", "rear_loss"): dict(peak_H_C=61.143480, peak_H_time_s=900.0, peak_surface_C=59.747155, H_3600_C=26.374204),
    ("H2", "intact"):    dict(peak_H_C=33.861287, peak_H_time_s=900.0, peak_surface_C=33.362444, H_3600_C=25.168602),
    ("H2", "rear_loss"): dict(peak_H_C=55.545063, peak_H_time_s=900.0, peak_surface_C=53.153638, H_3600_C=26.798252),
    ("H3", "intact"):    dict(peak_H_C=33.884652, peak_H_time_s=900.0, peak_surface_C=32.963939, H_3600_C=25.165436),
    ("H3", "rear_loss"): dict(peak_H_C=50.169875, peak_H_time_s=900.0, peak_surface_C=45.881263, H_3600_C=28.187988),
}
TRANSIENT_REPORT_DT_ASSUMED_S = 1.0


def fault_segments(loss, sensor_W=0.1):
    """Coda's fault schedule: 5 W body to 900 s then 0; sensor throughout; rear loss at 600 s.
    Three segments are used for both cases so that intact/loss traces share one time grid."""
    second = dict(duration=300, p=5, j=sensor_W)
    if loss:
        second["gr"] = 0.0
    return [dict(duration=600, p=5, j=sensor_W), second, dict(duration=2700, p=0, j=sensor_W)]
