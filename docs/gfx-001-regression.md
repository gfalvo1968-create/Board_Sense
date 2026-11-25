# GFX-001 — FX 5200 PCI graphics card, owner field test 2026-11-24
Observed production result: General PCB, 33% identity, LOW, observed-feature score 0, same-board 85%. Jury first candidate expansion card 42%. Gold-colored edge cue but strict geometry not confirmed. Board label reads GF FX5200 256MB DDR TV DVI PCI. Owner photo shows repeated segmented edge contacts and memory packages; front screenshot shows cooling assembly and display connectors.
Expected: broad graphics/expansion identity supported by physical geometry and, when available, legible label evidence; recovery grade independent of identity, no inferred metal mass or cash. If evidence is insufficient, manual review rather than final LOW. Do not hard-code model name or treat gold color alone as geometry.
## Source review
- routes/board_visual.py examines a narrow perimeter of the entire working image, not necessarily the PCB boundary. It evaluates spacing across all contacts together, so connector key gaps can inflate spacing variation.
- routes/analysis_image.py resizes but does not crop the board.
- routes/case_reasoner.py suppresses expansion votes if repeated edge geometry is unconfirmed.
- staging routes/recovery_grade_guard.py already has a zero-feature low-confidence General PCB manual-review guard. Verify deployed version before duplicating it.
## Regression gates
1. Test original front and rear files, separately and together; preserve same-board gate. Original rear available in conversation; front original not yet supplied to this conversation as a standalone image.
2. Synthetic regular and keyed contact rows at board edge, rotated and with background margin; negative controls random gold blobs, interior gold traces, gold-colored heat sinks and no board.
3. Inspect actual board boundary localization before relaxing image-perimeter constraint. Reject background contacts, no color-only promotion.
4. Verify IC detection with lighting variation, no double counting between views; identity evidence cannot invent recovery yield.
5. Confirm manual review propagates to UI, handoff and buyer-category worksheet. No production deployment until regression passes.
