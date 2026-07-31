const analyzeBtn = document.getElementById("analyzeBtn");
const fileInput = document.getElementById("boardImage");
const uploadStatus = document.getElementById("uploadStatus");
const predictionBox = document.getElementById("predictionBox");
const signalBox = document.getElementById("signalBox");
const historyBox = document.getElementById("historyBox");
const previewImage = document.getElementById("previewImage");
const saveSourceBtn = document.getElementById("saveSourceBtn");
const irmStatus = document.getElementById("irmStatus");

function setText(element, text) {
    if (element) {
        element.innerHTML = text;
    }
}

function addHistory(text) {
    if (!historyBox) return;

    const item = document.createElement("div");
    item.className = "history-item";
    item.innerHTML = text;

    historyBox.prepend(item);
}

function renderSignals(signals) {
    if (!signalBox) return;

    let html = "";

    for (const key in signals) {
        const value = signals[key];
        let color = "red";

        if (value === true || value === "green") {
            color = "lime";
        } else if (value === "orange") {
            color = "orange";
        }

        html += `
            <div style="margin-bottom:10px;">
                <span style="color:${color};">●</span>
                ${key}: ${value}
            </div>
        `;
    }

    signalBox.innerHTML = html;
}

async function analyzeBoard() {
    console.log("Analyze button clicked");
    alert("Analyze button clicked");

    const file = fileInput.files[0];

    if (!file) {
        uploadStatus.innerHTML = "Please select a board image.";
        return;
    }

    uploadStatus.innerHTML = "Analyzing board...";

    previewImage.src = URL.createObjectURL(file);
    previewImage.style.display = "block";

    const formData = new FormData();

    formData.append("file", file);
    devLog("Packaging image...");
    devLog("Sending request to Harbor AI...");

    try {

        const response = await fetch("https://boardsense.scrapradarfamily.com/analyze", {

            method: "POST",

            body: formData

        });

        const data = await response.json();
        devLog("Response received");
        devLog("Grade: " + data.ai_grade);
        devLog("Confidence: " + data.confidence + "%");
        devLog("Estimated Value: $" + data.value_estimate);

        $("predictionBox").innerHTML =
            "<b>Grade:</b> " + data.ai_grade +
            "<br><b>Confidence:</b> " + data.confidence +
            "<br><b>Action:</b> " + data.action +
            "<br><b>Estimated Value:</b> $" + data.value_estimate;

        $("uploadStatus").innerHTML =
            "Analysis complete.";

        if (typeof renderSignals === "function") {

            renderSignals(data.signals);

        }

    }

    catch (err) {

        $("predictionBox").innerHTML =
            "Upload failed.<br><br>" + err;

        $("uploadStatus").innerHTML =
            "Upload failed.";

    }

async function saveSource() {
    setText(irmStatus, "Saving source...");

    const payload = {
        name: document.getElementById("sourceName").value,
        phone: document.getElementById("sourcePhone").value,
        material: document.getElementById("sourceMaterial").value,
        notes: document.getElementById("sourceNotes").value
    };

    try {
        const response = await fetch("/irm/save-source", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        setText(irmStatus, result.message || "Source saved.");

    } catch (error) {
        setText(irmStatus, "Source save failed.");
    }
}

if (analyzeBtn) {
    analyzeBtn.addEventListener("click", analyzeBoard);
}

if (saveSourceBtn) {
    saveSourceBtn.addEventListener("click", saveSource);
}
