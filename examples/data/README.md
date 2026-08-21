# Example data: time-calibrated LACA tree (Moody et al. 2025)

## Provenance

- **Original source**: Moody, E.R.R., Williams, T.A., Álvarez-Carretero, S.,
  Szöllősi, G.J., Pisani, D., Lenton, T.M., Donoghue, P.C.J. (2025). The
  emergence of metabolisms through Earth history and implications for
  biospheric evolution. *Phil. Trans. R. Soc. B* 380: 20240097.
  <https://doi.org/10.1098/rstb.2024.0097> (open access).
- The tree is a published time-calibrated phylogeny with 700 tips
  (350 archaeal + 350 bacterial) and 699 BEAST-style node-age annotations
  of the form `[&95%={lo, hi}]`.

## Derivative modifications (this copy only)

- Tip labels were renamed into GTDB embedded format A so that the tree can
  exercise FigTreeKit's taxonomy-aware workflow. The tree topology, node
  ages, and all annotations are unchanged.
- `FigTree_withLACA_CLK_95CI.tsv` is the accompanying taxonomy metadata
  table.

## License / reuse

The original article is open access. This derivative file is redistributed
here with full attribution to the original publication; please retain this
provenance notice in any further redistribution.
