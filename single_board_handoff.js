/* Board Sense single-photo handoff sender v1 (not activated in the public UI).
 * Only share bounded, provisional identification and lab-inspection cues.
 * No uploaded image, buyer grade, dollar amount, assay, weight, user ID or secret.
 */
(function (root) {
  "use strict";
  const DESTINATION = "https://gfalvo1968-create.github.io/scrap_radar_family/scrap_radar.html";
  function clean(value, limit) {
    if (typeof value !== "string") return "";
    return value.replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, limit);
  }
  function build(scan) {
    const gate = scan && scan.object_gate || {};
    if (!scan || scan.status !== "success" || gate.mode !== "board") return null;
    const boardType = clean(scan.board_type, 120);
    const confidence = Number(scan.confidence);
    if (!boardType || !Number.isFinite(confidence) || confidence < 0 || confidence > 100) return null;
    const labs = scan.recovery_lab && scan.recovery_lab.labs;
    const signals = Array.isArray(labs)
      ? labs.slice(0, 4).map(x => clean(x && x.label, 90)).filter(Boolean) : [];
    return {
      version: 1,
      kind: "board_sense_single_view",
      manualReview: true,
      boardType: boardType,
      confidence: Math.round(confidence),
      signals: signals
    };
  }
  function makeUrl(scan) {
    const packet = build(scan);
    if (!packet) return null;
    const url = new URL(DESTINATION);
    url.searchParams.set("source", "spike");
    url.hash = "bs-single-v1=" + encodeURIComponent(JSON.stringify(packet));
    return url.href;
  }
  root.BoardSenseSingleViewHandoff = Object.freeze({ build: build, makeUrl: makeUrl });
})(window);
