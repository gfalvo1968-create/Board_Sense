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
    const dashboardBtn = document.getElementById("dashboardBtn");

if (dashboardBtn) {
    dashboardBtn.addEventListener("click", function () {
        window.location.href = "index.html";
    });
    log("Dashboard button ready");
}

}
function analyzeBoard() {

    log("Analyze button pressed");

    const image = document.getElementById("boardImage");

    if (!image || image.files.length === 0) {

        log("No image selected.");

        document.getElementById("uploadStatus").textContent =
            "Please choose a board image.";

        return;

    }

    log("Board image selected.");

    uploadImage(image.files[0]);

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

    try {

    const response = await fetch("/analyze", {
        method: "POST",
        body: formData
    });

    if (!response.ok) {
        throw new Error("Server returned " + response.status);
    }

    const result = await response.json();

    log("Analysis complete.");
    log("Board: " + result.board);
    log("Score: " + result.score);

    if (result.jackpot) {
        log("💰 JACKPOT DETECTED!");
    }

    if (uploadStatus) {
        uploadStatus.textContent = "Analysis complete.";
    }

    const predictionBox = document.getElementById("predictionBox");

    if (predictionBox) {
        predictionBox.innerHTML =
            "<strong>Score:</strong> " + result.score +
            "<br><strong>Recovery:</strong> " +
       (result.recovery_message || "No recovery message.");
    }

} catch (err) {

    log("ERROR: " + err.message);

    if (uploadStatus) {
        uploadStatus.textContent = "Upload failed.";
    }

}

}

document.addEventListener("DOMContentLoaded", function () {

    log("⚓ Harbor Edition initialized");
    log("System ready");

    initialize();

});
