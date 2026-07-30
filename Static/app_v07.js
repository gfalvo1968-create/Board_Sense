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

async function uploadImage(file) {

    log("Preparing upload...");
    log("Waiting for Harbor AI...");

    const uploadStatus = document.getElementById("uploadStatus");

    if (uploadStatus) {
        uploadStatus.textContent = "Uploading board...";
    }

    const formData = new FormData();
    formData.append("file", file);

    // Backend connection comes next.

}

log("Board image selected.");

uploadImage(image.files[0]);

}

document.addEventListener("DOMContentLoaded", function () {

    log("⚓ Harbor Edition initialized");
    log("System ready");

    initialize();

});
