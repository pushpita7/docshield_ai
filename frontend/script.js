
const API_URL = "http://127.0.0.1:8000";

const form = document.getElementById("uploadForm");
const fileInput = document.getElementById("document");
const fileLabel = document.getElementById("fileLabel");
const analyzeBtn = document.getElementById("analyzeBtn");
const message = document.getElementById("message");
const results = document.getElementById("results");
const resultContent = document.getElementById("resultContent");

fileInput.addEventListener("change", () => {
    fileLabel.textContent =
        fileInput.files[0]?.name || "Choose a document to analyze";
});

function addResult(label, value) {
    const item = document.createElement("div");
    item.className = "result-item";

    const heading = document.createElement("strong");
    heading.textContent = label;

    const paragraph = document.createElement("p");
    paragraph.textContent =
        typeof value === "object" && value !== null
            ? JSON.stringify(value, null, 2)
            : String(value ?? "Not available");

    item.append(heading, paragraph);
    resultContent.appendChild(item);
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const file = fileInput.files[0];

    if (!file) {
        message.textContent = "Please choose a document first.";
        return;
    }

    const allowed = [".pdf", ".png", ".jpg", ".jpeg"];
    const extension = file.name
        .slice(file.name.lastIndexOf("."))
        .toLowerCase();

    if (!allowed.includes(extension)) {
        message.textContent = "Please select a supported document.";
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        message.textContent = "The maximum file size is 10 MB.";
        return;
    }

    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "Analyzing...";
    message.textContent = "Uploading document for preliminary screening...";
    results.hidden = true;
    resultContent.replaceChildren();

    try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(`${API_URL}/analyze`, {
            method: "POST",
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Document analysis failed.");
        }

        addResult("Status", "Preliminary screening completed");
        addResult("Filename", data.filename);
        addResult("File type", data.file_type);
        addResult("File size (bytes)", data.file_size_bytes);
        addResult("SHA-256 fingerprint", data.sha256);

        if (data.page_count !== undefined) {
            addResult("Pages", data.page_count);
            addResult("Extracted text characters", data.text_characters);
            addResult("Metadata", data.metadata);
        }

        if (data.image_dimensions) {
            addResult("Image dimensions", data.image_dimensions);
        }

        addResult("Observations", data.observations);
        addResult("Important notice", data.notice);

        results.hidden = false;
        message.textContent = "Analysis completed successfully.";
    } catch (error) {
        message.textContent =
            `Error: ${error.message}. Check that the backend is running.`;
    } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "Analyze document";
    }
});