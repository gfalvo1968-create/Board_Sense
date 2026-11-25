"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync("index.html", "utf8");
const script = html.split("<script>")[1].split("</script>")[0];
assert.equal((html.match(/id="boardImage"/g) || []).length, 1);
assert.equal((html.match(/id="analyzeBtn"/g) || []).length, 1);
assert.ok(!html.includes('id="multiBoardPanel"'), "No special public bulk-board station");
assert.ok(!html.includes('Analyze Boards Separately'), "Never advertise batch scanning");
assert.ok(html.includes('<details id="testerAccess" hidden'), "Private testing is tucked away");

class Element {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.textContent = "";
    this.style = {};
    this.value = "";
    this.files = [];
    this.hidden = false;
    this.disabled = false;
  }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren() { this.children = []; this.textContent = ""; }
  removeAttribute(name) { delete this[name]; }
}
const elements = new Map();
for (const id of [
  "boardImage", "analyzeBtn", "uploadStatus", "predictionBox",
  "blueprintPreview", "blueprintStatus", "recoveryBox",
  "testerAccess", "singleScanTesterKey"
]) elements.set(id, new Element());
elements.get("boardImage").files = [{ name: "accidental-two-boards.jpg" }];
const calls = [];
let authorized = true;
const api = async (url, options = {}) => {
  calls.push({ url, options });
  if (url === "/multi-board-capabilities") {
    return { ok: true, status: 200, json: async () => ({ tester_preview_enabled: true }) };
  }
  if (url === "/analyze-multi" && !authorized) {
    return { ok: false, status: 403, json: async () => ({ detail: "Authorized tester access required." }) };
  }
  if (url === "/analyze-multi") {
    return { ok: true, status: 200, json: async () => ({
      status: "separate_reports", board_count: 2,
      combined_grade: null,
      reports: [
        { board_index: 1, board_type: "Power-control", confidence: 75, provisional_grade: "LOW" },
        { board_index: 2, board_type: "Logic board", confidence: 84, provisional_grade: "MEDIUM" }
      ]
    }) };
  }
  if (url === "/analyze") {
    return { ok: true, status: 200, json: async () => ({
      status: "success", board_type: "General PCB", confidence: 60,
      grade: "MANUAL REVIEW", object_gate: { mode: "board", label: "PCB" }
    }) };
  }
  throw new Error("unexpected endpoint " + url);
};
class FormData {
  append(name, value) { this[name] = value; }
}
const document = {
  getElementById(id) { return elements.get(id) || null; },
  createElement(tag) { return new Element(tag); }
};
const context = vm.createContext({
  document, window: { addEventListener() {} }, FormData, fetch: api, console
});
vm.runInContext(script, context);

async function run() {
  await context.initializePrivateScanTester();
  assert.equal(elements.get("testerAccess").hidden, false);
  assert.equal(elements.get("testerAccess").style.display, "block");

  elements.get("singleScanTesterKey").value = "staging-test-key";
  await context.uploadImage();
  assert.equal(calls.at(-1).url, "/analyze-multi", "Normal button must auto-detect in private staging");
  assert.equal(calls.at(-1).options.headers["x-board-sense-tester-key"], "staging-test-key");
  const cards = elements.get("predictionBox").children;
  assert.equal(cards.length, 2);
  assert.ok(cards[0].children[0].textContent.includes("Board 1"));
  assert.ok(cards[1].children[0].textContent.includes("Board 2"));
  assert.ok(cards[0].children[1].textContent.includes("LOW"));
  assert.ok(cards[1].children[1].textContent.includes("MEDIUM"));
  assert.ok(!elements.get("recoveryBox").textContent.includes("combined grade"));

  elements.get("singleScanTesterKey").value = "";
  await context.uploadImage();
  assert.equal(calls.at(-1).url, "/analyze", "Ordinary public scan stays quota-limited");
  assert.ok(elements.get("predictionBox").textContent.includes("Provisional grade: MANUAL REVIEW"));

  authorized = false;
  elements.get("singleScanTesterKey").value = "wrong-key";
  const startCalls = calls.length;
  await context.uploadImage();
  assert.equal(calls.length, startCalls + 1, "403 must NOT fall back to public scan");
  assert.equal(calls.at(-1).url, "/analyze-multi");
  assert.ok(elements.get("predictionBox").textContent.includes("tester key not accepted"));
  assert.equal(elements.get("singleScanTesterKey").value, "wrong-key", "Keep key available for correction");
  console.log("Single normal button, safe multi-board cards, quota path, private key errors verified");
}
run().catch((error) => { console.error(error); process.exitCode = 1; });
