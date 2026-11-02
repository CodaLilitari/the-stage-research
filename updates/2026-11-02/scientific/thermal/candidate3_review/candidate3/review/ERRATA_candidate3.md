# Errata to REPORT_candidate3.md (review thermal-candidate3-review-001; Claude, Anthropic; static)

1. §5 shell comment and "Summary for Red": "8 FAIL + 3 ERROR" -> "7 FAIL + 4 ERROR". The §4
   per-test table was already 7 F + 4 E and matches Red's receipt test by test.
2. candidate3.diff hunk E header "@@ -258,6 +298,32 @@" overstates the body by one line (+25,
   not +26); net change is +103 lines (956 -> 1059, Red's receipt). Applied file is correct;
   regenerate the diff with `diff -u --strip-trailing-cr` (base file is CRLF).
3. §2 "all 108 cases have amp ~ 9..55 (max ~ 53 at C_R_rej_hi/E2 for H1)": omits the rear-blocked
   group, where amp = 2 R_SA/R_HS + 1 ~ 118 for H1 (and E4 ~ 132; thinner stacks larger). Red's
   passing assertion bounds the sample maximum below 563; run review/amp_scan.py for the value.
   Conclusion unchanged: max guard ratio < 1e-3.
4. §2 "margin >= 2.6x": against the stated first-order worst-case bounds the margin is ~1.7-1.9x
   (guard at amp = 0.0625 tol/u; rounding-induced False needs amp > ~0.10-0.12 tol/u).
5. §5 "expect 913bfd2c..." for the Linux results hash: that hash is of Coda's Windows (CRLF) file;
   on Linux expect a81199c6... raw and 913bfd2c... after LF->CRLF translation (review/results_identity.py).
