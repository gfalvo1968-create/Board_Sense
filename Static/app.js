const fileInput = document.getElementById("fileInput");
const analyzeBtn = document.getElementById("analyzeBtn");
const previewImage = document.getElementById("previewImage");
const uploadStatus = document.getElementById("uploadStatus");
const predictionBox = document.getElementById("predictionBox");
const signalBox = document.getElementById("signalBox");
const historyBox = document.getElementById("historyBox");

function setText(el, text) {
    if (el) {
        el.innerHTML = text;
    }
}

function lightEmoji(color) {
    if (color === "green") return "🟢";
    if (color === "orange") return "🟠";
    return "🔴";
}

function renderSignals(signals) {
    if (!signals) {
        setText(signalBox, "No signal scan yet");
        return;
    }

    let html = "";

    for (const [name, color] of Object.entries(signals)) {
        html += `
            <div class="signal-row">
                <strong>${name.replaceAll("_", " ")}</strong>
                <span>${lightEmoji(color)} ${color.toUpperCase()}</span>
            </div>
        `;
    }

    setText(signalBox, html);
}

function renderPrediction(data) {
    setText(predictionBox, `
        <strong>Grade:</strong> ${data.ai_grade}<br>
        <strong>Confidence:</strong> ${data.confidence}<br>
        <strong>Score:</strong> ${data.score}<br>
        <strong>Recommendation:</strong> ${data.recommendation}<br>
        <strong>Pay_Dirt Ready:</strong> ${data.pay_dirt_ready ? "YES" : "NO"}
    `);
}

function addHistory(data) {
    if (!historyBox) return;

    const entry = `
        <div class="history-entry">
            <strong>${data.filename}</strong><br>
            Grade: ${data.ai_grade}<br>
            Score: ${data.score}
        </div>
    `;

    if (historyBox.innerHTML.includes("No scans yet")) {
        historyBox.innerHTML = "";
    }

    historyBox.innerHTML = entry + historyBox.innerHTML;
}

async function analyzeBoard() {
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        setText(uploadStatus, "Choose a board image first.");
        return;
    }

    const file = fileInput.files[0];

    setText(uploadStatus, "Sending board to AI engine...");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });

        const raw = await response.text();

let data;
try {
    data = JSON.parse(raw);
} catch (e) {
    throw new Error(raw);
}

        if (!response.ok) {
            setText(uploadStatus, "Upload failed: " + (data.detail || "Unknown error"));
            return;
        }

        setText(uploadStatus, "Board analyzed successfully.");

        renderPrediction(data);
        renderSignals(data.signals);
        addHistory(data);

        if (data.jackpot) {
            setText(uploadStatus, "💥 JACKPOT — send this one to Pay_Dirt.");
            document.body.classList.add("jackpot-mode");
            setTimeout(() => {
                document.body.classList.remove("jackpot-mode");
            }, 2500);
        }

    } catch (err) {
        setText(uploadStatus, "Upload error: " + err);
    }
}

if (fileInput) {
    fileInput.addEventListener("change", function () {
        const file = fileInput.files[0];

        if (!file) return;

        setText(uploadStatus, "Selected: " + file.name);

        if (previewImage) {
            previewImage.src = URL.createObjectURL(file);
            previewImage.style.display = "block";
        }
    });
}

if (analyzeBtn) {
    analyzeBtn.addEventListener("click", analyzeBoard);
}

   if (fileInput) {
    fileInput.addEventListener("change", function () {
        const file = fileInput.files[0];

        if (!file) {
            setText(uploadStatus, "Waiting for board image...");
            return;
        }

        setText(uploadStatus, "Selected: " + file.name);

        if (previewImage) {
            previewImage.src = URL.createObjectURL(file);
            previewImage.style.display = "block";
        }
   
    async function saveSource() {

    const payload = {
        name: document.getElementById("sourceName").value,
        phone: document.getElementById("sourcePhone").value,
        material: document.getElementById("sourceMaterial").value,
        notes: document.getElementById("sourceNotes").value
    };

    const response = await fetch("/irm/save-source", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    });

    const result = await response.json();

    document.getElementById("irmStatus").innerHTML =
        result.message;
}
    
    });
}
    
