# Known issues — research update 2026-11-02

Open at publication. Each item was executed and observed; none is a static guess.

1. **2-D delamination model convergence order.** The fix-003 convergence module fails two checks. The observed
   refinement order is 0.879 for the mid-plane centre temperature and 1.099 for the heater node, against a claimed
   second-order scheme. The differences between successive refinements are about 1e-3 K and 1e-4 K. The study's
   qualitative conclusions are unlikely to depend on errors of that size, but that claim is not yet established.
   A diagnosis was requested in wave 13.
2. **Metamorphic suite.** In the promised tier, `test_sanitize_is_a_strict_json_projection` fails for candidates 2
   and 3, because NaN maps to `None` and the type check expects a float. This looks like a test-expectation defect,
   not yet decided. The informational tier (`THERMAL_TEST_INFORMATIONAL=1`) records 14 failures and 1 error on
   relations the contract does not promise. They have not been classified.
3. **SITE0 revised_v1 at extreme scales.** Two failures and one error remain at inputs of order 1e±300: a
   test-helper division underflows, and two late-time equilibria return the initial value. No domain of validity is
   stated yet. Separately, Coda's frozen suites do not detect the audit's mutant (24 tests run, no failures), while
   the audit module detects it. Whether the mutant binds into the code the frozen suites exercise still needs a
   binding proof.
4. **Gateway non-conformances.** The conformance module carries 4 expected failures. They record behaviours of the
   real code that differ from the model checker's clarified invariants (CONFORMANCE_NOTE.md). Examples are an
   in-memory dispatch mark (decision C1-b) and a bare `OSError` after an ambiguous replacement (N-1). Closure was
   requested in wave 13.
5. **Layered oracle F2 default.** The default is corrected to the contract's 2e-2 m² K/W. Pre-fix results are kept
   for evidence (`results/oracle_results_fix003_before_F2_fix.json`). The oracle's sensitivity-range tests still use
   2e-3 deliberately.
6. **Harness layout sensitivity.** Several audits need a specific directory layout or environment variables
   (`SITE0_ORIGINAL_PATH`, `SITE0_FROZEN_TESTS_DIR`, `WEXACT0_SOURCE_DIR`, `THERMAL_CONTRACT_PATH`,
   `AB_MPB1B_DIR`, `AB_MPB1A_MODEL`, `AB_MPB1B_EXPECT_PATCHED`, `THERMAL_TRANSIENT_DIR`). During the run, three
   apparent failures were layout errors, each caught by re-running in the documented layout.
   `tools/reproduce_check.py` encodes the working invocations.
7. **Repository root verifier.** Since the 18 October update, the root `verify_release.py` reports every file under
   `updates/` as unmanifested, because each update carries its own manifest and verifier. Verify this folder with its
   own `verify_release.py`. The root files are Coda's and are unchanged here.
8. **Copies, not packages.** Some dependency files appear several times (for example `rc_transient.py`,
   `thermal_reference.py` and `first_leaf.py`). Each executed working tree is kept self-contained so it runs as it
   was run. The provenance map identifies each copy's source.
9. **Model-vs-model only.** No result here was compared with measurement. Parameter values are contract
   assumptions. The comparators at 40, 45 and 60 °C are arbitrary study thresholds, not safety limits.
10. **Closed lines.** Seven request lines were refused or exhausted their output budget and are closed (see
    INCLUDE_EXCLUDE.md). Their questions remain unanswered by this run.
