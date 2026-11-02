# AB-MPB1B frozen acceptance

Prepared before implementation. Prose CC BY 4.0; runnable examples/interfaces Apache-2.0. All checks refer to PUMP_CONTRACT.md and unchanged admitted A.

1. At (R,D,P) = (20,12,3.2), expect Q = 0.4, deltaP = 8 and Phyd = 3.2, power-limited, absolute tolerance 2e-14.
2. At (80,12,3.2), expect Q = 0.15, deltaP = 12 and Phyd = 1.8, pressure-limited, same tolerance.
3. At (45,12,3.2), expect Q = 4/15 and both caps active, tolerance 2e-14.
4. Either or both zero caps yield exactly zero flow, pressure and hydraulic power for every tested R > 0. R = 0 remains invalid even with zero caps.
5. Reject negative, Boolean, nonnumeric and nonfinite R/caps. Reject a positive mathematical flow that cannot be represented as a finite positive float, not silently zero or infinity.
6. Compare 45 pump cases (R = 1,7,20,45,80; D = 0,1,12; P = 0,0.3,3.2) against an independent 80-step Decimal bisection of both feasibility inequalities; flow error <= 3e-14 * max(1, expected).
7. Increasing resistance cannot increase flow; increasing either cap cannot decrease flow. Check the declared grids and both pressure/power transitions.
8. Multiplying R and both caps by 10 preserves flow and multiplies actual pressure/power by 10, within 3e-14 absolute/relative.
9. With nonzero caps, actual pressure and power remain within their caps to 3e-14 relative and at least one cap binds. Both equal caps do not mean both actual quantities equal their caps.
10. All nine saved N = 3 A rows reduce at R = 20 to full-state agreement <= 2e-14 micromoles. This pins exact initial conditions and duration, not merely endpoint ordering.
11. For zero-cap flow, a two-fluid pure-circulation initial state with exchange/reaction/sink disabled remains unchanged. A nonzero-cap case changes it. No elapsed-time rescaling is allowed.
12. Pump flow must not depend on channel-cell count 1,3,16. The wrapper replaces Config.flow with the computed value even if the caller supplies a different nominal flow.
13. A three-channel/two-return pumped dynamic case preserves O and sites within 1e-11 micromoles, uniform total-site concentration within 1e-11 micromoles/mL, and minimum state >= -1e-14. Both SSP stages remain checked by A.
14. The three initial-condition controls retain total oxygen 2.4/4.4/2.4, site amounts 0/3/3 and declared occupancy/partition. No normalization is introduced.
15. Deliberate wrong-model witnesses: replacing min with max violates caps at R = 80; treating P/R as a flow misses the quadratic power relation at R = 20; multiplying physical R by the mesh count changes an otherwise invariant pump result. These witnesses are not alternative admitted models.
16. Preserve all 33 A manifest files and verify the exact kernel and saved results. A and B contribution/admission records remain separate.

Study guards: exactly 27 unique frozen rows; every row O/site residual < 1e-11 and minimum state >= -1e-14; achieved pump quantities feasible within 3e-14 relative; unchanged A/model/test/design hashes before and after. All comparisons and raw rows are retained even if no ranking reverses. No favorable ranking is an acceptance condition. A meaningful initial RED must precede pump implementation; preserve the zero-pump stub.
