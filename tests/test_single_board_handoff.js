"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("single_board_handoff.js", "utf8");
const window = {};
vm.runInNewContext(source, { window, URL, encodeURIComponent, JSON, Object });
const handoff = window.BoardSenseSingleViewHandoff;
assert.ok(handoff && typeof handoff.makeUrl === "function");

const sample = {
  status: "success",
  object_gate: { mode: "board", label: "PCB" },
  board_type: "Dense Logic / Controller Board",
  confidence: 78,
  grade: "HIGH", pay_dirt_ready: true, price: 9999,
  image_url: "data:image/jpeg;base64,PRIVATE",
  board_blueprint: { image_url: "data:image/jpeg;base64,PRIVATE" },
  free_usage: { visitor_id: "should-not-leak" },
  recovery_lab: { labs: [{ label: "Circuit Board Lab" }, { label: "Gold Finger Lab" }] }
};
const url = handoff.makeUrl(sample);
const parsed = new URL(url);
assert.equal(parsed.hostname, "gfalvo1968-create.github.io");
assert.equal(parsed.pathname, "/scrap_radar_family/scrap_radar.html");
assert.equal(parsed.searchParams.get("source"), "spike");
const packet = JSON.parse(decodeURIComponent(parsed.hash.slice("#bs-single-v1=".length)));
assert.equal(packet.version, 1);
assert.equal(packet.kind, "board_sense_single_view");
assert.equal(packet.manualReview, true);
assert.equal(packet.confidence, 78);
assert.equal(packet.boardType, "Dense Logic / Controller Board");
assert.equal(packet.signals.length, 2);
const encoded = JSON.stringify(packet);
for (const secret of ["PRIVATE", "should-not-leak", "9999", "image_url", "visitor_id", "pay_dirt_ready", "HIGH"]) {
  assert.ok(!encoded.includes(secret), "Packet leaked private or unverified detail: " + secret);
}
assert.ok(url.length < 2200, "Link exceeds receiver's size limit");

assert.equal(handoff.makeUrl({ ...sample, object_gate: { mode: "pcb_review" } }), null);
assert.equal(handoff.makeUrl({ ...sample, status: "failure" }), null);
assert.equal(handoff.makeUrl({ ...sample, confidence: 1000 }), null);
assert.equal(handoff.makeUrl({ ...sample, board_type: "" }), null);

console.log("Board Sense single-photo sender: guarded PCB, preview-only fields, no image, visitor or economics, bounded URL passed");
