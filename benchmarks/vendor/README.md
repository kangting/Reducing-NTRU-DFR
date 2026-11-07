# Comparison source attribution

This directory contains only the C/header/assembly source dependencies used by
the paper comparison harness. No upstream binaries, repository internals or
unrelated ML-KEM experiments are included.

- **BAT:** Thomas Pornin, [author repository](https://github.com/pornin/BAT).
  The original MIT license is retained in `BAT/LICENSE`; source notices and
  the upstream README are preserved.
- **END:** [author repository](https://github.com/Icarid-Liu/Explore_NTRU_Decryption).
  The four END-512/1024 C/AVX2 source directories used in the comparison retain
  their embedded notices and upstream README. No new project-wide license is
  assigned to those sources.

The benchmark adapters supply entropy at the documented API boundary. END-512
AVX2 needs the previously documented declaration-only repairs, applied to an
ignored build copy by `paper/build.py`; the committed author files are unchanged.
Known shared-key-preflight failures remain explicit and have no timing rank.
Observed adapter failures do not identify their underlying cause.
