# Diagnostic development record

R1 failed its independent Simpson quadrature conservation tolerance of 1e-8 at N256. The maximum error was 1.3450104918710792e-08. Eleven of twelve unit tests passed; one failed on the same numerical check. No biological model interpretation was changed.

R2 adds the N512 refinement level and retains the original 1e-8 acceptance tolerance. Full r1 inputs, code, test logs and outputs remain in history/r1. Both are deterministic numerical-verification runs, not independent empirical replications.
