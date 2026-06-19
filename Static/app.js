const analyzeBtn = document.getElementById("analyzeBtn");
const fileInput = document.getElementById("fileInput");
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
    const file = fileInput.files[0];

    if (!file) {
        setText(uploadStatus, "Please select a board image.");
        return;
    }

    setText(uploadStatus, "Analyzing board...");

    previewImage.src = URL.createObjectURL(file);
    previewImage.style.display = "block";

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const result = await response.json();
        const data = result.ai_result || result;

        setText(
            predictionBox,
            `
            <strong>Grade:</strong> ${data.grade || data.ai_grade || "UNKNOWN"}<br>
            <strong>Confidence:</strong> ${data.confidence || "N/A"}<br>
            <strong>Score:</strong> ${data.score || 0}<br>
            <strong>Pay Dirt Ready:</strong> ${data.pay_dirt_ready ? "YES" : "NO"}<br>
            <strong>Recommendation:</strong> ${data.recommendation || "Manual review required."}
            `
        );

        renderSignals(data.signals || {});
        addHistory(`${data.grade || data.ai_grade || "UNKNOWN"} | Score ${data.score || 0}`);

        setText(uploadStatus, "Board analyzed successfully.");

    catch (error) {
    setText(uploadStatus, error.message);
    }
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
