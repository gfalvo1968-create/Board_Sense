// =========================================
// Board Sense Harbor Edition v0.7
// Two-Sided Scan Workflow v0.1
// =========================================
"use strict";

const scanState = {
    phase: "A",
    sideA: null,
    sideB: null
};

function log(message) {
    const consoleBox = document.getElementById("dev-console");
    if (!consoleBox) return;
    const time = new Date().toLocaleTimeString();
    consoleBox.innerHTML += "<br>[" + time + "] " + message;
    consoleBox.scrollTop = consoleBox.scrollHeight;
}

function initialize() {
    log("Loading two-sided scan interface...");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const resetBtn = document.getElementById("resetScanBtn");
    if (analyzeBtn) analyzeBtn.addEventListener("click", analyzeCurrentSide);
    if (resetBtn) resetBtn.addEventListener("click", resetScan);
    log("Side A ready");
}

function analyzeCurrentSide() {
    if (scanState.phase === "A") {
        const input = document.getElementById("boardImageA");
        if (!input || !input.files.length) {
            setText("uploadStatus", "Please choose Side A first.");
            log("No Side A image selected.");
            return;
        }
        uploadSide(input.files[0], "A");
        return;
    }

    const input = document.getElementById("boardImageB");
    if (!input || !input.files.length) {
        setText("uploadStatus", "Flip the same board and choose Side B.");
        log("Waiting for Side B image.");
        return;
    }
    uploadSide(input.files[0], "B");
}

async function uploadSide(file, side) {
    const button = document.getElementById("analyzeBtn");
    if (button) button.disabled = true;
    setText("uploadStatus", "Analyzing Side " + side + "...");
    setText("side" + side + "Status", "Harbor AI is inspecting Side " + side + "...");
    log("Sending Side " + side + ": " + file.name);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("board_side", side);

    try {
        const response = await fetch("/analyze", { method: "POST", body: formData });
        if (!response.ok) throw new Error("Server returned " + response.status);
        const result = await response.json();
        scanState["side" + side] = result;
        setText("side" + side + "Status", "✓ Side " + side + " analyzed.");
        log("Side " + side + " complete. Grade: " + (result.grade || "UNKNOWN") + ", confidence: " + (result.confidence ?? 0) + "%");

        if (side === "A") {
            scanState.phase = "B";
            const controls = document.getElementById("sideBControls");
            if (controls) controls.style.display = "block";
            setText("scanInstruction", "✓ Side A captured. Now flip the SAME board for Side B.");
            setText("uploadStatus", "🔄 Flip the board and photograph Side B.");
            if (button) button.textContent = "Analyze Side B";
            renderSingleSide(result, "A");
        } else {
            scanState.phase = "COMPLETE";
            setText("scanInstruction", "✓ Both sides captured. Combined investigation ready.");
            setText("uploadStatus", "Two-sided scan complete.");
            if (button) button.textContent = "Both Sides Complete";
            renderCombinedReport(scanState.sideA, scanState.sideB);
        }
    } catch (err) {
        log("ERROR Side " + side + ": " + err.message);
        setText("side" + side + "Status", "Side " + side + " analysis failed.");
        setText("uploadStatus", "Upload failed. Please try Side " + side + " again.");
    } finally {
        if (button) button.disabled = scanState.phase === "COMPLETE";
    }
}

function renderSingleSide(result, side) {
    const box = document.getElementById("predictionBox");
    if (!box) return;
    box.innerHTML = "<strong>Side " + side + " preliminary result</strong>" +
        "<br><strong>Grade:</strong> " + safe(result.grade, "UNKNOWN") +
        "<br><strong>Confidence:</strong> " + number(result.confidence) + "%" +
        "<br><strong>Recovery Score:</strong> " + number(result.score) +
        "<br><br><em>Flip the board. Final report waits for Side B.</em>";
}

function renderCombinedReport(a, b) {
    const box = document.getElementById("predictionBox");
    if (!box) return;
    const aConf = number(a && a.confidence);
    const bConf = number(b && b.confidence);
    const aScore = number(a && a.score);
    const bScore = number(b && b.score);
    const best = aConf >= bConf ? a : b;
    const gradesAgree = a && b && safe(a.grade, "UNKNOWN") === safe(b.grade, "UNKNOWN");
    const combinedConfidence = gradesAgree ? Math.round((aConf + bConf) / 2) : Math.round(Math.max(aConf, bConf) * 0.82);
    const combinedScore = Math.max(aScore, bScore);

    box.innerHTML =
        "<strong>🔄 TWO-SIDED INVESTIGATION</strong>" +
        "<br><br><strong>Side A:</strong> " + safe(a && a.grade, "UNKNOWN") + " | " + aConf + "%" +
        "<br><strong>Side B:</strong> " + safe(b && b.grade, "UNKNOWN") + " | " + bConf + "%" +
        "<br><br><strong>Combined Grade:</strong> " + safe(best && best.grade, "UNKNOWN") +
        "<br><strong>Combined Confidence:</strong> " + combinedConfidence + "%" +
        "<br><strong>Recovery Score:</strong> " + combinedScore +
        "<br><strong>Side Agreement:</strong> " + (gradesAgree ? "✓ Both sides agree" : "⚠ Sides disagree; confidence reduced") +
        "<br><strong>Recommendation:</strong> " + safe(best && best.recommendation, "Manual review required.");

    log("Two-sided report complete. Agreement: " + gradesAgree);
}

function resetScan() {
    scanState.phase = "A";
    scanState.sideA = null;
    scanState.sideB = null;
    const a = document.getElementById("boardImageA");
    const b = document.getElementById("boardImageB");
    if (a) a.value = "";
    if (b) b.value = "";
    const controls = document.getElementById("sideBControls");
    if (controls) controls.style.display = "none";
    const button = document.getElementById("analyzeBtn");
    if (button) { button.disabled = false; button.textContent = "Analyze Side A"; }
    setText("scanInstruction", "Step 1: Photograph or choose Side A of the board.");
    setText("sideAStatus", "Waiting for Side A...");
    setText("sideBStatus", "Waiting for Side B...");
    setText("uploadStatus", "Waiting for Side A image...");
    const box = document.getElementById("predictionBox");
    if (box) box.innerHTML = "No analysis yet.";
    log("New two-sided board scan started.");
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}
function safe(value, fallback) { return value === undefined || value === null || value === "" ? fallback : value; }
function number(value) { const n = Number(value); return Number.isFinite(n) ? Math.round(n) : 0; }

document.addEventListener("DOMContentLoaded", function () {
    log("⚓ Harbor Edition v0.7 initialized");
    log("Two-sided scan workflow online");
    initialize();
});
