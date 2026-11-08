# Audited family KEM tables

Hardware CPU-cycle measurements are displayed as kcycles (cycles / 1000). All intervals are bootstrap 95% intervals.
Size and model metadata are archived values with source attribution. Timing
tables report local measurements.

## Primary family parameters and attributed diagnostics

| Scheme | M/u/K<br>(bits) | CT<br>(bytes) | PK<br>(bytes) | CT+PK<br>(bytes) | C diag. | Q diag. | b ≈ |
|---|---:|---:|---:|---:|---:|---:|---:|
| **S512-q251** | 256/256/256 | 543 | 511 | 1054 | 140.05 | 134.56 | 166.15 |
| **S1024-q347** | 256/512/256 | 1113 | 1081 | 2194 | 270.07 | 251.59 | 163.38 |
| **D512-q157** | 128/128/256 | 483 | 467 | 950 | 144.39 | 138.45 | 133.38 |
| **D1024-q251** | 256/256/256 | 1053 | 1021 | 2074 | 278.68 | 259.33 | 166.86 |

M/u/K are external message / internal residue / shared-key output lengths in bits.
C/Q are historical GSA/MATZOV diagnostics from profile screening. The
[paper reproducibility package](../../experiments/paper_reproduction/README.md)
reports the recovery calculations for Tables III and VI. The exponent b is
the approximate value of -log2(B).
These columns are not a full KEM security claim or a NIST certificate. No compression denominator is assigned.

## Primary profiles and matched peers: local KEM performance

| Scheme | REF KeyGen<br>(kcycles) | REF Encaps<br>(kcycles) | REF Decaps<br>(kcycles) | AVX2 KeyGen<br>(kcycles) | AVX2 Encaps<br>(kcycles) | AVX2 Decaps<br>(kcycles) |
|---|---:|---:|---:|---:|---:|---:|
| BAT-512 | 19,668.915<br>[14,325.761, 24,553.788] | 47.020<br>[46.978, 47.112] | 300.402<br>[300.285, 300.454] | 17,832.227<br>[16,642.649, 21,404.566] | 10.061<br>[10.050, 10.070] | 56.612<br>[56.586, 56.660] |
| END-512 [1] | 9,216.122<br>[8,418.315, 10,016.721] | 28.908<br>[28.796, 28.988] | 328.230<br>[328.078, 328.425] |  |  |  |
| **S512-q251** | 2,222.412<br>[2,220.931, 2,229.777] | 300.676<br>[300.543, 300.744] | 460.114<br>[459.999, 460.254] | 1,843.785<br>[1,841.390, 1,845.584] | 184.417<br>[184.247, 184.541] | 232.698<br>[232.421, 232.929] |
| **D512-q157** | 2,260.666<br>[2,257.419, 2,264.095] | 268.340<br>[268.166, 268.436] | 427.895<br>[427.696, 428.057] | 1,878.953<br>[1,875.310, 1,882.568] | 152.781<br>[152.730, 152.863] | 201.447<br>[201.392, 201.552] |
| BAT-1024 | 106,227.522<br>[77,951.843, 135,044.927] | 93.911<br>[93.849, 93.950] | 621.914<br>[621.791, 622.012] | 97,193.241<br>[83,738.468, 104,319.250] | 21.241<br>[21.225, 21.269] | 116.493<br>[116.439, 116.555] |
| END-1024 [2,3] |  |  |  |  |  |  |
| **S1024-q347** | 4,917.572<br>[4,913.513, 4,920.746] | 741.887<br>[741.716, 741.972] | 1,065.250<br>[1,065.098, 1,065.653] | 3,861.338<br>[3,859.300, 3,865.328] | 484.334<br>[484.092, 484.443] | 560.771<br>[560.662, 560.828] |
| **D1024-q251** | 4,648.099<br>[4,642.902, 4,657.134] | 696.215<br>[696.013, 696.385] | 1,023.468<br>[1,023.243, 1,023.748] | 3,568.026<br>[3,566.258, 3,571.190] | 441.248<br>[441.100, 441.425] | 521.723<br>[521.609, 521.894] |

REF: first KeyGen/Encaps/Decaps block. AVX2: second block.

Median of accepted batch means; brackets give the prespecified bootstrap 95% interval.
1 kcycle = 1000 raw hardware CPU cycles. Counter-read overhead is retained, not subtracted.
Blank performance cells are correctness exclusions, never zero costs. Batch counts are retained in CSV.
[1] END-512 / AVX2: Shared-key preflight failed through the preserved-source adapter; no timing is ranked
[2] END-1024 / REF: Shared-key preflight failed through the preserved-source adapter; no timing is ranked
[3] END-1024 / AVX2: Shared-key preflight failed through the preserved-source adapter; no timing is ranked

## Extended table: all 16 selected family profiles

| Scheme | M/u/K<br>(bits) | CT<br>(bytes) | PK<br>(bytes) | CT+PK<br>(bytes) | C diag. | Q diag. | b ≈ |
|---|---:|---:|---:|---:|---:|---:|---:|
| **S512-q251** | 256/256/256 | 543 | 511 | 1054 | 140.05 | 134.56 | 166.15 |
| **S1024-q347** | 256/512/256 | 1113 | 1081 | 2194 | 270.07 | 251.59 | 163.38 |
| **D512-q157** | 128/128/256 | 483 | 467 | 950 | 144.39 | 138.45 | 133.38 |
| **D1024-q251** | 256/256/256 | 1053 | 1021 | 2074 | 278.68 | 259.33 | 166.86 |
| S512-q251 C139.5 | 256/256/256 | 543 | 511 | 1054 | 139.54 | 134.10 | 169.66 |
| S512-q251 den128 | 256/256/256 | 543 | 511 | 1054 | 140.07 | 134.58 | 166.02 |
| S1024-q349 | 256/512/256 | 1114 | 1082 | 2196 | 270.02 | 251.55 | 164.87 |
| S1024-q347 den256 | 256/512/256 | 1113 | 1081 | 2194 | 270.02 | 251.54 | 163.66 |
| S1024-q347 den512 | 256/512/256 | 1113 | 1081 | 2194 | 270.02 | 251.54 | 163.70 |
| D1024-q269 | 256/256/256 | 1066 | 1034 | 2100 | 276.76 | 257.61 | 177.89 |
| S512-q269 BAT M128 | 128/256/256 | 533 | 517 | 1050 | 144.01 | 138.13 | 149.20 |
| S1024-q373 BAT | 256/512/256 | 1126 | 1094 | 2220 | 272.02 | 253.35 | 170.66 |
| S1024-q379 DFR256 | 256/512/256 | 1129 | 1097 | 2226 | 246.28 | 230.19 | 262.55 |
| S1024-q347 DFR256 | 256/512/256 | 1113 | 1081 | 2194 | 192.29 | 181.59 | 271.09 |
| S1024-q541 DFR256 | 256/512/256 | 1195 | 1163 | 2358 | 269.91 | 251.46 | 257.15 |
| S1024-q347 C198.7 | 256/512/256 | 1113 | 1081 | 2194 | 199.07 | 187.70 | 269.42 |

M/u/K are external message / internal residue / shared-key output lengths in bits.
C/Q are supplied structural GSA/MATZOV diagnostics; b is approximate -log2(B), not a rounded strict inequality.
These columns are not a full KEM security claim or a NIST certificate. No compression denominator is assigned.

## Extended table: REF and AVX2 results for all 16 family profiles

| Scheme | REF KeyGen<br>(kcycles) | REF Encaps<br>(kcycles) | REF Decaps<br>(kcycles) | AVX2 KeyGen<br>(kcycles) | AVX2 Encaps<br>(kcycles) | AVX2 Decaps<br>(kcycles) |
|---|---:|---:|---:|---:|---:|---:|
| **S512-q251** | 2,222.412<br>[2,220.931, 2,229.777] | 300.676<br>[300.543, 300.744] | 460.114<br>[459.999, 460.254] | 1,843.785<br>[1,841.390, 1,845.584] | 184.417<br>[184.247, 184.541] | 232.698<br>[232.421, 232.929] |
| **S1024-q347** | 4,917.572<br>[4,913.513, 4,920.746] | 741.887<br>[741.716, 741.972] | 1,065.250<br>[1,065.098, 1,065.653] | 3,861.338<br>[3,859.300, 3,865.328] | 484.334<br>[484.092, 484.443] | 560.771<br>[560.662, 560.828] |
| **D512-q157** | 2,260.666<br>[2,257.419, 2,264.095] | 268.340<br>[268.166, 268.436] | 427.895<br>[427.696, 428.057] | 1,878.953<br>[1,875.310, 1,882.568] | 152.781<br>[152.730, 152.863] | 201.447<br>[201.392, 201.552] |
| **D1024-q251** | 4,648.099<br>[4,642.902, 4,657.134] | 696.215<br>[696.013, 696.385] | 1,023.468<br>[1,023.243, 1,023.748] | 3,568.026<br>[3,566.258, 3,571.190] | 441.248<br>[441.100, 441.425] | 521.723<br>[521.609, 521.894] |
| S512-q251 C139.5 | 2,236.392<br>[2,233.559, 2,243.607] | 301.327<br>[301.190, 301.438] | 460.782<br>[460.659, 460.920] | 1,861.702<br>[1,860.086, 1,863.212] | 185.047<br>[184.948, 185.145] | 233.390<br>[233.192, 233.586] |
| S512-q251 den128 | 2,376.427<br>[2,368.728, 2,381.015] | 301.203<br>[301.107, 301.365] | 460.672<br>[460.586, 460.774] | 1,999.910<br>[1,998.309, 2,001.831] | 184.970<br>[184.859, 185.058] | 233.068<br>[232.623, 233.408] |
| S1024-q349 | 4,684.743<br>[4,665.080, 4,689.082] | 741.120<br>[740.893, 741.353] | 1,066.891<br>[1,066.677, 1,067.222] | 3,630.365<br>[3,619.905, 3,642.269] | 484.459<br>[484.334, 484.727] | 561.251<br>[561.134, 561.343] |
| S1024-q347 den256 | 4,651.786<br>[4,648.410, 4,661.042] | 740.809<br>[740.582, 741.114] | 1,064.078<br>[1,063.772, 1,064.346] | 3,607.075<br>[3,601.068, 3,615.913] | 483.371<br>[483.171, 483.534] | 559.571<br>[559.503, 559.665] |
| S1024-q347 den512 | 4,605.953<br>[4,600.470, 4,617.949] | 740.819<br>[740.669, 740.984] | 1,064.010<br>[1,063.683, 1,064.297] | 3,550.507<br>[3,547.322, 3,552.988] | 483.127<br>[483.020, 483.238] | 559.642<br>[559.533, 559.781] |
| D1024-q269 | 4,668.494<br>[4,650.249, 4,675.803] | 704.758<br>[704.488, 704.905] | 1,036.300<br>[1,036.079, 1,036.507] | 3,567.649<br>[3,564.010, 3,569.429] | 446.210<br>[446.124, 446.348] | 526.776<br>[526.689, 526.865] |
| S512-q269 BAT M128 | 2,380.732<br>[2,377.540, 2,383.324] | 301.245<br>[301.186, 301.340] | 459.749<br>[459.620, 459.888] | 2,003.691<br>[1,997.234, 2,007.713] | 185.544<br>[185.476, 185.618] | 234.055<br>[234.007, 234.147] |
| S1024-q373 BAT | 4,913.830<br>[4,910.288, 4,915.833] | 747.292<br>[747.052, 747.478] | 1,074.104<br>[1,073.967, 1,074.487] | 4,034.410<br>[4,030.482, 4,039.471] | 486.595<br>[486.502, 486.737] | 563.431<br>[563.225, 563.538] |
| S1024-q379 DFR256 | 4,894.446<br>[4,778.300, 4,903.992] | 743.559<br>[743.485, 743.820] | 1,065.767<br>[1,065.592, 1,066.022] | 3,704.537<br>[3,685.873, 3,707.675] | 487.717<br>[487.664, 487.782] | 564.199<br>[564.079, 564.300] |
| S1024-q347 DFR256 | 4,608.497<br>[4,601.757, 4,614.139] | 740.842<br>[740.669, 741.063] | 1,063.851<br>[1,063.598, 1,064.146] | 3,552.851<br>[3,549.360, 3,557.075] | 483.012<br>[482.929, 483.210] | 559.485<br>[559.383, 559.590] |
| S1024-q541 DFR256 | 5,523.443<br>[5,509.782, 5,575.542] | 824.696<br>[824.582, 824.806] | 1,148.908<br>[1,148.421, 1,149.220] | 4,406.209<br>[4,403.880, 4,412.590] | 561.937<br>[561.794, 562.100] | 635.021<br>[634.926, 635.195] |
| S1024-q347 C198.7 | 4,601.489<br>[4,597.831, 4,608.790] | 740.877<br>[740.693, 741.162] | 1,064.020<br>[1,063.604, 1,064.347] | 3,552.322<br>[3,549.014, 3,556.473] | 483.263<br>[483.028, 483.373] | 559.655<br>[559.551, 559.723] |

REF: first KeyGen/Encaps/Decaps block. AVX2: second block.

Median of accepted batch means; brackets give the prespecified bootstrap 95% interval.
1 kcycle = 1000 raw hardware CPU cycles. Counter-read overhead is retained, not subtracted.
Blank performance cells are correctness exclusions, never zero costs. Batch counts are retained in CSV.

## Matched peer API wire sizes

| Scheme | M/u/K<br>(bits) | API CT<br>(bytes) | API PK<br>(bytes) | API total<br>(bytes) | Source CT<br>(bytes) | Source PK<br>(bytes) |
|---|---:|---:|---:|---:|---:|---:|
| END-512 | 256/—/256 | 384 | 514 | 898 | 384 | 514 |
| BAT-512 | 128/—/— | 473 | 521 | 994 | 472 | 520 |
| END-1024 | 512/—/256 | 832 | 1027 | 1859 | 832 | 1027 |
| BAT-1024 | 256/—/— | 1006 | 1230 | 2236 | 1005 | 1229 |

API sizes come from the matched build descriptors; source sizes retain the archive convention.
BAT API keys and ciphertexts include one-byte headers beyond the header-free source metadata.
— means the source does not specify that length; message length does not imply shared-key length.

## Published comparator metadata (separate evidence models)

| Scheme | M/u/K<br>(bits) | Source CT<br>(bytes) | Source PK<br>(bytes) | C reported | Q reported | DFR exp.<br>(reported) |
|---|---:|---:|---:|---:|---:|---:|
| DAWN-alpha-512 | 128/128/— | 436 | 615 | 139.50 | 133.50 | 133.00 |
| DAWN-alpha-512-prime | 256/256/256 | 514 | 615 | 140.00 | — | 166.00 |
| DAWN-alpha-1024 | 256/256/— | 973 | 1229 | 269.90 | 250.80 | 163.00 |
| BAT-512 | 128/—/— | 472 | 520 | 140.30 | 124.70 | 146.70 |
| BAT-1024 | 256/—/— | 1005 | 1229 | 283.20 | 250.60 | 166.70 |
| END-512 | 256/—/256 | 384 | 514 | 152.70 | — | 130.00 |
| END-1024 | 512/—/256 | 832 | 1027 | 287.10 | — | 157.00 |
| DAWN-beta-512 | 128/128/— | 450 | 514 | 134.30 | 134.10 | 130.00 |
| DAWN-beta-1024 | 256/256/— | 1027 | 1027 | 266.50 | 251.20 | 138.00 |

This table records source sizes and model/DFR statements.
For END-512, exponent 130 describes the base average-error estimate.
The manuscript comparison uses the bound after the worst-message transformation.
Published C/Q and DFR statements use heterogeneous models and must not be ranked as a common security scale.
Exact attribution, relations, qualifications and URLs are retained in metadata JSON/CSV and Markdown.

## Published evidence attribution

- DAWN-alpha-512: DAWN Table 7, estimator 5ba00f5, MATZOV; minimum over NTRU and RLWE DFR: Heuristic: section4.3 explicitly assumes output coefficient independence; no uniform-key certificate. Source: https://eprint.iacr.org/2025/1520.
- DAWN-alpha-512-prime: Table 1 rounded classical value; no separate Table 7 row. DFR: Heuristic: section4.3 explicitly assumes output coefficient independence; no uniform-key certificate. Source: https://eprint.iacr.org/2025/1520.
- DAWN-alpha-1024: DAWN Table 7, estimator 5ba00f5, MATZOV; minimum over NTRU and RLWE DFR: Heuristic: section4.3 explicitly assumes output coefficient independence; no uniform-key certificate. Source: https://eprint.iacr.org/2025/1520.
- BAT-512: Published BAT Table 5 minima; one-tour d*2^(0.292 beta) / d*2^(0.257 beta), not DAWN MATZOV. DFR: Numerical DFR calculation averaged over100 keys, with trapdoor/noise heuristic; not a100-trial empirical rare-failure estimate. Source: https://d-nb.info/1275147933/34.
- BAT-1024: Published BAT Table 5 minima; one-tour d*2^(0.292 beta) / d*2^(0.257 beta), not DAWN MATZOV. DFR: Numerical DFR calculation averaged over100 keys, with trapdoor/noise heuristic; not a100-trial empirical rare-failure estimate. Source: https://d-nb.info/1275147933/34.
- END-512: Author notebook cached classical outputs, standard estimator revision 3e48ef421ec256afddb3e7d2249a77eab6e9ba12; not independently rerun and not paper Table 4 verification. DFR: Heuristic: coefficient-independence, FCL exclusion and trapdoor/verification models; exact correctness reduction does not certify its input numerical DFR. Source: https://eprint.iacr.org/2026/1715.
- END-1024: Author notebook cached classical outputs, standard estimator revision 3e48ef421ec256afddb3e7d2249a77eab6e9ba12; not independently rerun and not paper Table 4 verification. DFR: Heuristic: coefficient-independence, FCL exclusion and trapdoor/verification models; exact correctness reduction does not certify its input numerical DFR. Source: https://eprint.iacr.org/2026/1715.
- DAWN-beta-512: DAWN Table7 estimator5ba00f5 MATZOV; minNTRU/RLWE. DFR: Heuristic: section4.3 coefficient-independence assumption. Source: https://eprint.iacr.org/2025/1520.
- DAWN-beta-1024: DAWN Table7 estimator5ba00f5 MATZOV; minNTRU/RLWE. DFR: Heuristic: section4.3 coefficient-independence assumption. Source: https://eprint.iacr.org/2025/1520.

CPU 4; SMT siblings [5] offline; Turbo disabled; performance governor; scaling frequency bounds 3 GHz.

KeyGen medians are conditional on accepted batches; interruption rejection can favor shorter realizations.
Accepted/rejected counts and full-precision intervals are in CSV. Functional/taint/sanitizer/timing admission is not a production-security proof.

Portable raw data: [single_double.json.gz](../raw/single_double.json.gz).
Experiment environment and reproduction: [benchmark guide](../../benchmarks/README.md).
