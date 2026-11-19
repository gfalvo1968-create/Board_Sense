# Board Sense guarded public preview release candidate (Nov 16, 2026)

**Status:** REVIEW / NO AUTOMATIC PROMOTION. **Target:** November 19 public *free preview only* if acceptance gates pass.

## Scope

This branch starts from tested SPIKE guarded recognition work but removes staging-only HTML experiment controls, staging transport tracing, and public timing logs. It retains non-final dark PCB-review classification, checked object-gate rules, stronger multi-photo physical identity quarantine, exact duplicate-upload detection and diagnostic-only landmark correspondence, and unit regressions.

**Explicit limitation:** two to six uploaded photos currently cannot independently establish that they show the same physical board. Compatible silhouettes or operator attestation are *not* sufficient identity evidence. All such unverified multi-photo cases must withhold combined feature score, buyer grade, recovery economics and Scrap Radar transfer. This preserves safety but limits the product: the free preview should not be advertised as offering automatic, verified multi-photo pricing. Each photo can retain *separate* inspection findings.

**Single-photo:** known candidate PCB scans can present observational identification and provisional recovery information with an uncertainty disclosure. Neither image appearance nor score can establish measured metal grams, a buyer's accepted scrap grade, or a payout.

**Dark/low-detail PCB:** the object gate may report `pcb_review` with classification and economics withheld rather than incorrectly declaring a confirmed non-board. This is not an automatic board-grade approval.

**Duplicate upload:** file-identical photos cannot count as independent views even when the checkbox is checked; altered duplicates require additional protections.

## Before promotion

1. CI full Python regressions (including negative controls, dark PCB and case identity) and GitHub Pages/Jekyll workflow pass for exact candidate commit.
2. Staging deploy exact candidate commit (not a different staging branch), test healthy cold start and actual device upload.
3. Real photos: dark PCB back `IMG_5864.jpeg` → `pcb_review`; component/front `IMG_5865.jpeg` yields truthful separate findings. Combined case stays blocked from buyer grade/economics.
4. Adversarial different physical boards checked/unchecked and duplicate uploads checked/unchecked all block combined grade/economics; irrelevant non-PCB images stay rejected.
5. Verify one suitable standalone PCB report and legitimate Board Sense → Scrap Radar handoff with owner entered *actual* weight, buyer acceptance/category and costs; never invent precious-metal yields or promise returns.
6. Check actual quota accounting, retries, invalid upload treatment, privacy and retention, terminal errors, mobile reliability, domain and rollback.
7. Check public frontend compatibility: draft Family UI PR #28 conveys object reject versus identity uncertainty without claiming a PCB is a non-board.
8. Owner signs off release scope: **free preview** only if checks pass. Paid checkout/entitlement verification is separately required and not covered by this release.

## Rollback

Tag/document exact prior main commit and current production Railway deploy before any promotion; be prepared to redeploy known-working release. Avoid simultaneous frontend/backend changes without a coordinated verification window.

**No production promotion was authorized by this note alone.**
