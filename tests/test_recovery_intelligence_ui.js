"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync("index.html", "utf8");
const script = html.split("<script>")[1].split("</script>")[0];
const elements = new Map();
class Element {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.textContent = "";
    this.style = {};
  }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren() { this.children = []; this.textContent = ""; }
}
const panel = new Element();
elements.set("recoveryBox", panel);
const document = {
  getElementById(id) { return elements.get(id) || null; },
  createElement(tag) { return new Element(tag); }
};
const window = { addEventListener() {} };
const context = vm.createContext({ window, document, console });
vm.runInContext(script, context);
const render = context.renderRecoveryIntelligence;
assert.equal(typeof render, "function");

const scan = {
  status: "success",
  grade: "MANUAL REVIEW",
  recovery_lab: {
    labs: [{ label: "Circuit Board Lab" }, { label: "<unsafe> Lab" }],
    risk: { level: "controlled_process" },
    economics: { status: "needs_values" }
  },
  price: 1111111,
  image_url: "data:image/jpeg;base64,PRIVATE"
};
render(scan, "board");
const labels = panel.children.map(x => x.textContent);
assert.ok(labels.some(x => x.includes("MANUAL REVIEW")));
assert.ok(labels.some(x => x.includes("unpriced")));
assert.ok(labels.some(x => x.includes("professional/refinery")));
assert.ok(panel.children.some(x => x.tagName === "A" && x.textContent.includes("manual economics")));
assert.ok(!JSON.stringify(panel.children).includes("1111111"));
assert.ok(!JSON.stringify(panel.children).includes("PRIVATE"));
const list = panel.children.find(x => x.tagName === "UL");
assert.equal(list.children.length, 2);
assert.equal(list.children[1].textContent, "<unsafe> Lab");
assert.ok(!("innerHTML" in list.children[1]), "lab labels must use textContent, not injected HTML");

render(scan, "pcb_review");
assert.ok(!panel.children.some(x => x.tagName === "A"), "unconfirmed PCB must not get economics link");
assert.ok(panel.children[0].textContent.includes("withheld"));
render(null, "loading");
assert.equal(panel.children.length, 1, "new scan removes stale recovery report");
console.log("Recovery Intelligence: inspection cues only, manual value entry, withheld review and stale reset passed");
