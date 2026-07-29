// =========================================
// Board Sense Harbor Edition v0.7
// =========================================

"use strict";

function log(message) {

    const consoleBox = document.getElementById("dev-console");

    if (!consoleBox) return;

    const time = new Date().toLocaleTimeString();

    consoleBox.innerHTML += "<br>[" + time + "] " + message;

    consoleBox.scrollTop = consoleBox.scrollHeight;
}
function initialize() {

    log("Loading interface...");

    const analyzeBtn = document.getElementById("analyzeBtn");

    if (analyzeBtn) {

        analyzeBtn.addEventListener("click", analyzeBoard);

        log("Analyze button ready");

    }

}

function analyzeBoard() {

    log("Analyze button pressed");

}

document.addEventListener("DOMContentLoaded", function () {

    log("⚓ Harbor Edition initialized");
    log("System ready");

    initialize();

});
