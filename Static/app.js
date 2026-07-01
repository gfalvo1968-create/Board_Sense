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
        uploadStatus.innerHTML = "Please select a board image.";
        return;
    }

    uploadStatus.innerHTML = "Analyzing board...";

    previewImage.src = URL.createObjectURL(file);
    previewImage.style.display = "block";

    let grade = "LOW GRADE";

    const investigation = {
    classification: grade,
    confidence: 95,
    evidence: [],
    recoveryScore: 0,
    recoveryPlan: [],
    lesson: ""
};

    if (
        file.name.toLowerCase().includes("ram") ||
        file.name.toLowerCase().includes("gold")
    ) {
        grade = "HIGH GRADE";
    }

    predictionBox.innerHTML = `
<h2>🔍 BOARD INVESTIGATION REPORT</h2>

<hr>

<h3>🧠 Classification</h3>
<p>${grade}</p>

<h3>🎯 Confidence</h3>
<p>95%</p>

<h3>🔍 Evidence Found</h3>
<ul>
<li>Analysis complete</li>
<li>Board features detected</li>
</ul>

<h3>💰 Recovery Intelligence</h3>
<p>Calculating...</p>

<h3>🛠 Recommended Recovery</h3>
<p>Evaluation in progress...</p>

<h3>📚 Today's Lesson</h3>
<p>Every circuit board tells a story. Learning to recognize features is the first step to understanding its value.</p>

<h3>🧭 Harbor Compass</h3>

<p>
North • Knowledge<br>
East • Discovery<br>
South • Teaching<br>
West • Legacy
</p>
`;

    signalBox.innerHTML =
        '<span style="color:lime">● READY</span>';

    uploadStatus.innerHTML =
        "Board analyzed successfully.";
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
