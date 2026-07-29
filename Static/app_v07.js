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

document.addEventListener("DOMContentLoaded", function () {

    log("⚓ Harbor Edition initialized");

    log("System ready");

});
