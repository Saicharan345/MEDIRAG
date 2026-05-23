document.addEventListener("DOMContentLoaded", () => {
    const chatMessages = document.getElementById("chat-messages");
    const userInput = document.getElementById("user-input");
    const sendBtn = document.getElementById("send-btn");
    const reingestBtn = document.getElementById("reingest-btn");
    const sysStatus = document.getElementById("sys-status");
    const dbCount = document.getElementById("db-count");
    const providerName = document.getElementById("provider-name");
    const domainList = document.getElementById("domain-list");
    const languageSelect = document.getElementById("language-select");
    const chatHistory = document.getElementById("chat-history");
    const prescriptionHistory = document.getElementById("prescription-history");
    const labHistory = document.getElementById("lab-history");
    const newChatBtn = document.getElementById("new-chat-btn");
    const chatTitle = document.getElementById("chat-title");
    const chatMeta = document.getElementById("chat-meta");
    const fileInput = document.getElementById("prescription-file");
    const fileName = document.getElementById("file-name");
    const analyzeBtn = document.getElementById("analyze-btn");
    const prescriptionResults = document.getElementById("prescription-results");
    const labInput = document.getElementById("lab-report-input");
    const interpretLabBtn = document.getElementById("interpret-lab-btn");
    const labReportFileInput = document.getElementById("lab-report-file");
    const labFileName = document.getElementById("lab-file-name");
    const analyzeLabFileBtn = document.getElementById("analyze-lab-file-btn");
    const labResults = document.getElementById("lab-results");
    const sourceModal = document.getElementById("source-modal");
    const modalTitle = document.getElementById("modal-title");
    const modalMeta = document.getElementById("modal-meta");
    const modalContent = document.getElementById("modal-content");
    const closeModalBtn = document.getElementById("close-modal-btn");

    let currentDomain = "";
    let currentSessionId = null;
    let currentLanguage = languageSelect.value || "English";
    let selectedPrescriptionFile = null;
    let selectedLabFile = null;

    init();

    async function init() {
        bindTabs();
        bindEvents();
        renderEmptyChat();
        await Promise.all([loadHealth(), loadDomains(), loadAllHistory()]);

        const sessions = await fetchJson("/api/chats");
        if (Array.isArray(sessions) && sessions.length > 0) {
            await openChatSession(sessions[0].id);
        }
    }

    function bindTabs() {
        document.querySelectorAll(".tab-btn").forEach((button) => {
            button.addEventListener("click", () => openTab(button.dataset.tab));
        });
    }

    function bindEvents() {
        sendBtn.addEventListener("click", handleQuery);
        userInput.addEventListener("keypress", (event) => {
            if (event.key === "Enter") {
                handleQuery();
            }
        });
        newChatBtn.addEventListener("click", startNewChat);
        reingestBtn.addEventListener("click", rebuildIndex);
        fileInput.addEventListener("change", () => {
            selectedPrescriptionFile = fileInput.files[0] || null;
            fileName.textContent = selectedPrescriptionFile ? selectedPrescriptionFile.name : "No file selected";
        });
        analyzeBtn.addEventListener("click", handlePrescriptionUpload);
        interpretLabBtn.addEventListener("click", handleLabInterpretation);
        labReportFileInput.addEventListener("change", () => {
            selectedLabFile = labReportFileInput.files[0] || null;
            labFileName.textContent = selectedLabFile ? selectedLabFile.name : "No file selected";
        });
        analyzeLabFileBtn.addEventListener("click", handleLabFileUpload);
        languageSelect.addEventListener("change", () => {
            currentLanguage = languageSelect.value;
        });
        closeModalBtn.addEventListener("click", closeModal);
        sourceModal.addEventListener("click", (event) => {
            if (event.target.dataset.closeModal === "true") {
                closeModal();
            }
        });
    }

    async function loadHealth() {
        const data = await fetchJson("/api/health");
        if (!data) {
            sysStatus.textContent = "Offline";
            sysStatus.className = "status-value offline";
            providerName.textContent = "unreachable";
            return;
        }

        sysStatus.textContent = data.status === "healthy" ? "Online" : "Attention";
        sysStatus.className = `status-value ${data.status === "healthy" ? "online" : "offline"}`;
        dbCount.textContent = `${data.vector_db_count} chunks`;
        providerName.textContent = data.provider || "unknown";
    }

    async function loadDomains() {
        const domains = await fetchJson("/api/domains");
        if (!Array.isArray(domains)) {
            domainList.innerHTML = `<p class="history-empty">Unable to load domains.</p>`;
            return;
        }

        domainList.innerHTML = domains.map((domain) => `
            <button class="filter-btn" data-domain="${escapeAttribute(domain)}">${escapeHtml(domain)}</button>
        `).join("");

        document.querySelectorAll(".filter-btn").forEach((button) => {
            button.addEventListener("click", () => {
                document.querySelectorAll(".filter-btn").forEach((item) => item.classList.remove("active"));
                button.classList.add("active");
                currentDomain = button.dataset.domain || "";
            });
        });
    }

    async function loadAllHistory() {
        const [sessions, prescriptions, labReports] = await Promise.all([
            fetchJson("/api/chats"),
            fetchJson("/api/prescriptions"),
            fetchJson("/api/lab-reports"),
        ]);

        renderChatHistory(Array.isArray(sessions) ? sessions : []);
        renderPrescriptionHistory(Array.isArray(prescriptions) ? prescriptions : []);
        renderLabHistory(Array.isArray(labReports) ? labReports : []);
    }

    function renderChatHistory(items) {
        if (!items.length) {
            chatHistory.innerHTML = `<p class="history-empty">No saved chats yet.</p>`;
            return;
        }

        chatHistory.innerHTML = items.map((item) => `
            <div class="history-item chat-history-item ${item.id === currentSessionId ? "active" : ""}">
                <button class="history-main" type="button" data-chat-id="${escapeAttribute(item.id)}">
                    <strong>${escapeHtml(item.title)}</strong>
                    <span>${escapeHtml(formatTimestamp(item.updated_at))} | ${item.message_count} msgs</span>
                </button>
                <button class="history-delete-btn" type="button" aria-label="Delete chat" data-delete-chat-id="${escapeAttribute(item.id)}">Delete chat</button>
            </div>
        `).join("");

        chatHistory.querySelectorAll("[data-chat-id]").forEach((button) => {
            button.addEventListener("click", () => openChatSession(button.dataset.chatId));
        });
        chatHistory.querySelectorAll("[data-delete-chat-id]").forEach((button) => {
            button.addEventListener("click", () => deleteChatSession(button.dataset.deleteChatId));
        });
    }

    function renderPrescriptionHistory(items) {
        if (!items.length) {
            prescriptionHistory.innerHTML = `<p class="history-empty">No saved prescriptions yet.</p>`;
            return;
        }

        prescriptionHistory.innerHTML = items.map((item) => `
            <div class="history-item saved-record-item">
                <button class="history-main" type="button" data-prescription-id="${escapeAttribute(item.id)}">
                    <strong>${escapeHtml(item.title)}</strong>
                    <span>${escapeHtml(formatTimestamp(item.created_at))} | ${escapeHtml(item.language || "English")}</span>
                </button>
                <button class="history-delete-btn" type="button" aria-label="Delete prescription" data-delete-prescription-id="${escapeAttribute(item.id)}">Delete prescription</button>
            </div>
        `).join("");

        prescriptionHistory.querySelectorAll("[data-prescription-id]").forEach((button) => {
            button.addEventListener("click", () => openPrescriptionRecord(button.dataset.prescriptionId));
        });
        prescriptionHistory.querySelectorAll("[data-delete-prescription-id]").forEach((button) => {
            button.addEventListener("click", () => deletePrescriptionRecord(button.dataset.deletePrescriptionId));
        });
    }

    function renderLabHistory(items) {
        if (!items.length) {
            labHistory.innerHTML = `<p class="history-empty">No saved lab reports yet.</p>`;
            return;
        }

        labHistory.innerHTML = items.map((item) => `
            <div class="history-item saved-record-item">
                <button class="history-main" type="button" data-lab-id="${escapeAttribute(item.id)}">
                    <strong>${escapeHtml(item.title)}</strong>
                    <span>${escapeHtml(formatTimestamp(item.created_at))} | ${escapeHtml(item.language || "English")}</span>
                </button>
                <button class="history-delete-btn" type="button" aria-label="Delete lab report" data-delete-lab-id="${escapeAttribute(item.id)}">Delete lab report</button>
            </div>
        `).join("");

        labHistory.querySelectorAll("[data-lab-id]").forEach((button) => {
            button.addEventListener("click", () => openLabRecord(button.dataset.labId));
        });
        labHistory.querySelectorAll("[data-delete-lab-id]").forEach((button) => {
            button.addEventListener("click", () => deleteLabRecord(button.dataset.deleteLabId));
        });
    }

    async function openChatSession(sessionId) {
        const session = await fetchJson(`/api/chats/${sessionId}`);
        if (!session) {
            return;
        }

        currentSessionId = session.id;
        chatTitle.textContent = session.title;
        if (chatMeta) {
            chatMeta.textContent = "";
        }
        renderChatMessages(session.messages || []);
        await loadAllHistory();
        openTab("chat-tab");
    }

    async function deleteChatSession(sessionId) {
        if (!sessionId || !window.confirm("Delete this saved chat?")) {
            return;
        }

        const deletedCurrent = sessionId === currentSessionId;
        const data = await fetchJson(`/api/chats/${sessionId}`, { method: "DELETE" });
        if (!data) {
            return;
        }

        if (deletedCurrent) {
            currentSessionId = null;
            renderEmptyChat();
        }

        await loadAllHistory();

        if (deletedCurrent) {
            const sessions = await fetchJson("/api/chats");
            if (Array.isArray(sessions) && sessions.length > 0) {
                await openChatSession(sessions[0].id);
            }
        }
    }

    async function deletePrescriptionRecord(recordId) {
        if (!recordId || !window.confirm("Delete this saved prescription?")) {
            return;
        }

        const data = await fetchJson(`/api/prescriptions/${recordId}`, { method: "DELETE" });
        if (!data) {
            return;
        }

        await loadAllHistory();
    }

    async function deleteLabRecord(recordId) {
        if (!recordId || !window.confirm("Delete this saved lab report?")) {
            return;
        }

        const data = await fetchJson(`/api/lab-reports/${recordId}`, { method: "DELETE" });
        if (!data) {
            return;
        }

        await loadAllHistory();
    }

    function renderChatMessages(messages) {
        chatMessages.innerHTML = "";
        if (!messages.length) {
            renderEmptyChat();
            return;
        }

        messages.forEach((message) => {
            appendMessage(message.role === "assistant" ? "ai" : "user", message.content, {
                citations: message.citations || [],
                confidence: message.confidence || 0,
                disclaimer: message.disclaimer || "",
                guardrailStatus: message.guardrail_status || "grounded",
            });
        });
    }

    function renderEmptyChat() {
        chatMessages.innerHTML = `
            <div class="message system">
                <div class="msg-content">
                    <h3>Start a new chat.</h3>
                    <ul>
                        <li>Ask medical or medication questions and reopen them later from the saved history list.</li>
                        <li>Upload prescriptions and lab reports without losing the previous records.</li>
                        <li>Choose Hindi, Telugu, or another supported language for translated responses.</li>
                    </ul>
                </div>
            </div>
        `;
        chatTitle.textContent = "New Chat";
        if (chatMeta) {
            chatMeta.textContent = "";
        }
    }

    function appendMessage(role, content, extra = {}) {
        const templateId = role === "user" ? "msg-template-user" : "msg-template-ai";
        const template = document.getElementById(templateId);
        const clone = template.content.cloneNode(true);
        const contentDiv = clone.querySelector(".msg-content");

        if (role === "ai") {
            contentDiv.innerHTML = marked.parse(content || "");
            clone.querySelector(".conf-val").textContent = `${((extra.confidence || 0) * 100).toFixed(0)}%`;
            clone.querySelector(".guardrail-pill").textContent = extra.guardrailStatus || "grounded";
            const sourcesGrid = clone.querySelector(".sources-grid");
            (extra.citations || []).forEach((citation) => {
                const card = document.createElement("button");
                card.type = "button";
                card.className = "source-card";
                card.innerHTML = `
                    <strong>${escapeHtml(citation.title)}</strong>
                    <span>${escapeHtml(citation.source)}</span>
                    <span>${escapeHtml(citation.domain)} | ${escapeHtml(citation.category)}</span>
                    <span>${citation.last_updated ? `Updated ${escapeHtml(citation.last_updated)}` : "Source loaded locally"}</span>
                `;
                card.addEventListener("click", () => openSourceModal(citation));
                sourcesGrid.appendChild(card);
            });
        } else {
            contentDiv.textContent = content || "";
        }

        chatMessages.appendChild(clone);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showTyping() {
        const indicator = document.createElement("div");
        indicator.id = "typing-indicator";
        indicator.className = "typing-indicator";
        indicator.innerHTML = "<span></span><span></span><span></span>";
        chatMessages.appendChild(indicator);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function hideTyping() {
        const indicator = document.getElementById("typing-indicator");
        if (indicator) {
            indicator.remove();
        }
    }

    async function handleQuery() {
        const question = userInput.value.trim();
        if (!question) {
            return;
        }

        if (!currentSessionId) {
            chatMessages.innerHTML = "";
        }

        appendMessage("user", question);
        userInput.value = "";
        showTyping();

        const data = await fetchJson("/api/query", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question,
                domain: currentDomain || null,
                language: currentLanguage,
                session_id: currentSessionId,
            }),
        });

        hideTyping();
        if (!data) {
            appendMessage("ai", "I hit an error while processing that request.");
            return;
        }

        currentSessionId = data.session_id || currentSessionId;
        chatTitle.textContent = data.session_title || chatTitle.textContent;
        if (chatMeta) {
            chatMeta.textContent = "";
        }
        appendMessage("ai", data.answer || "No response received.", {
            citations: data.citations || [],
            confidence: data.confidence || 0,
            disclaimer: data.disclaimer || "",
            guardrailStatus: data.guardrail_status || data.message || "grounded",
        });
        await loadAllHistory();
    }

    function startNewChat() {
        currentSessionId = null;
        renderEmptyChat();
        userInput.focus();
        loadAllHistory();
        openTab("chat-tab");
    }

    async function rebuildIndex() {
        reingestBtn.disabled = true;
        reingestBtn.textContent = "Rebuilding...";
        await fetchJson("/api/ingest");
        reingestBtn.disabled = false;
        reingestBtn.textContent = "Rebuild Local Index";
        await Promise.all([loadHealth(), loadDomains()]);
    }

    async function handlePrescriptionUpload() {
        if (!selectedPrescriptionFile) {
            renderPrescriptionError("Choose an image file before starting analysis.");
            return;
        }

        analyzeBtn.disabled = true;
        analyzeBtn.textContent = "Analyzing...";
        prescriptionResults.innerHTML = loadingCard("Reading the image and matching likely medicines...");

        const formData = new FormData();
        formData.append("file", selectedPrescriptionFile);
        formData.append("language", currentLanguage);

        const data = await fetchJson("/api/prescription/analyze", {
            method: "POST",
            body: formData,
        });

        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "Analyze Image";

        if (!data) {
            renderPrescriptionError("Unable to analyze the image.");
            return;
        }

        renderPrescriptionResult(data);
        await loadAllHistory();
        openTab("image-tab");
    }

    async function handleLabInterpretation() {
        const reportText = labInput.value.trim();
        if (!reportText) {
            renderLabError("Paste a lab report before starting interpretation.");
            return;
        }

        interpretLabBtn.disabled = true;
        interpretLabBtn.textContent = "Interpreting...";
        labResults.innerHTML = loadingCard("Interpreting the pasted lab report...");

        const data = await fetchJson("/api/lab-report/interpret", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                report_text: reportText,
                language: currentLanguage,
            }),
        });

        interpretLabBtn.disabled = false;
        interpretLabBtn.textContent = "Interpret Lab Report";

        if (!data) {
            renderLabError("Unable to interpret the lab report.");
            return;
        }

        renderLabResult(data);
        await loadAllHistory();
        openTab("lab-tab");
    }

    async function handleLabFileUpload() {
        if (!selectedLabFile) {
            renderLabError("Choose a lab report image or PDF before starting interpretation.");
            return;
        }

        analyzeLabFileBtn.disabled = true;
        analyzeLabFileBtn.textContent = "Interpreting...";
        labResults.innerHTML = loadingCard("Reading the uploaded lab report...");

        const formData = new FormData();
        formData.append("file", selectedLabFile);
        formData.append("language", currentLanguage);

        const data = await fetchJson("/api/lab-report/analyze-file", {
            method: "POST",
            body: formData,
        });

        analyzeLabFileBtn.disabled = false;
        analyzeLabFileBtn.textContent = "Interpret Uploaded File";

        if (!data) {
            renderLabError("Unable to interpret the uploaded lab report file.");
            return;
        }

        renderLabResult(data);
        await loadAllHistory();
        openTab("lab-tab");
    }

    async function openPrescriptionRecord(recordId) {
        const data = await fetchJson(`/api/prescriptions/${recordId}`);
        if (!data) {
            return;
        }

        renderPrescriptionResult(data);
        openTab("image-tab");
    }

    async function openLabRecord(recordId) {
        const data = await fetchJson(`/api/lab-reports/${recordId}`);
        if (!data) {
            return;
        }

        renderLabResult(data);
        openTab("lab-tab");
    }

    function renderPrescriptionResult(data) {
        const warnings = (data.warnings || []).map((warning) => `<li>${escapeHtml(warning)}</li>`).join("");
        const medicines = (data.medicines || []).map((medicine) => `
            <article class="medicine-card">
                <div class="medicine-head">
                    <h3>${escapeHtml(medicine.normalized_name || medicine.name)}</h3>
                    <span class="confidence-badge">${((medicine.confidence || 0) * 100).toFixed(0)}%</span>
                </div>
                <p class="medicine-meta">${escapeHtml(medicine.strength || "Strength not clearly visible")}${medicine.dosage_instructions ? ` | ${escapeHtml(medicine.dosage_instructions)}` : ""}</p>
                <p><strong>Why it may be used:</strong> ${escapeHtml(medicine.common_use || "No verified use found.")}</p>
                <p>${escapeHtml(medicine.explanation || "")}</p>
                <p class="medicine-source">Source: ${escapeHtml(medicine.source || "Local drug reference")}${medicine.rxnorm_rxcui ? ` | RxNorm RXCUI ${escapeHtml(medicine.rxnorm_rxcui)}` : ""}</p>
                ${medicine.notes ? `<p class="medicine-note">Vision note: ${escapeHtml(medicine.notes)}</p>` : ""}
            </article>
        `).join("");

        prescriptionResults.innerHTML = `
            <div class="result-stack">
                <div class="result-summary">
                    <p class="eyebrow">${escapeHtml(data.title || "Prescription Analysis")}</p>
                    <h3>${escapeHtml(data.summary || "Prescription analyzed.")}</h3>
                    <p>${data.extracted_text ? `Extracted text: ${escapeHtml(data.extracted_text)}` : "No reliable full-text transcription was returned."}</p>
                </div>
                ${warnings ? `<div class="warning-box"><strong>Warnings</strong><ul>${warnings}</ul></div>` : ""}
                <div class="medicine-list">
                    ${medicines || `<div class="empty-state"><p>No medicines could be extracted confidently.</p></div>`}
                </div>
            </div>
        `;
    }

    function renderLabResult(data) {
        const warnings = (data.warnings || []).map((warning) => `<li>${escapeHtml(warning)}</li>`).join("");
        const markers = (data.detected_markers || []).map((marker) => `<span class="marker-pill">${escapeHtml(marker)}</span>`).join("");

        labResults.innerHTML = `
            <div class="result-stack">
                <div class="result-summary">
                    <p class="eyebrow">${escapeHtml(data.title || "Lab Report Interpretation")}</p>
                    <h3>${escapeHtml(data.summary || "Lab report interpreted.")}</h3>
                    ${data.file_name ? `<p class="medicine-source">File: ${escapeHtml(data.file_name)}</p>` : ""}
                    <div class="marker-row">${markers}</div>
                </div>
                ${data.extracted_text ? `<details class="text-preview"><summary>Extracted text preview</summary><pre>${escapeHtml(data.extracted_text)}</pre></details>` : ""}
                <div class="message ai inline-message">
                    <div class="msg-content">${marked.parse(data.interpretation || "")}</div>
                </div>
                ${warnings ? `<div class="warning-box"><strong>Warnings</strong><ul>${warnings}</ul></div>` : ""}
            </div>
        `;
    }

    function renderPrescriptionError(message) {
        prescriptionResults.innerHTML = `
            <div class="warning-box">
                <strong>Unable to analyze image</strong>
                <p>${escapeHtml(message)}</p>
            </div>
        `;
    }

    function renderLabError(message) {
        labResults.innerHTML = `
            <div class="warning-box">
                <strong>Unable to interpret lab report</strong>
                <p>${escapeHtml(message)}</p>
            </div>
        `;
    }

    function loadingCard(message) {
        return `
            <div class="loading-state">
                <div class="spinner"></div>
                <p>${escapeHtml(message)}</p>
            </div>
        `;
    }

    function openSourceModal(citation) {
        modalTitle.textContent = citation.title || "Source";
        modalMeta.textContent = [
            citation.source,
            citation.domain,
            citation.category,
            citation.last_updated ? `Updated ${citation.last_updated}` : null,
            citation.score != null ? `Retrieval score ${Number(citation.score).toFixed(2)}` : null,
        ].filter(Boolean).join(" | ");
        modalContent.textContent = citation.content || "";
        sourceModal.classList.remove("hidden");
    }

    function closeModal() {
        sourceModal.classList.add("hidden");
    }

    function openTab(tabId) {
        document.querySelectorAll(".tab-btn").forEach((button) => {
            button.classList.toggle("active", button.dataset.tab === tabId);
        });
        document.querySelectorAll(".tab-panel").forEach((panel) => {
            panel.classList.toggle("active", panel.id === tabId);
        });
    }

    async function fetchJson(url, options = {}) {
        try {
            const response = await fetch(url, options);
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || "Request failed.");
            }
            return data;
        } catch (error) {
            console.error(error);
            return null;
        }
    }

    function formatTimestamp(value) {
        if (!value) {
            return "";
        }
        try {
            return new Date(value).toLocaleString();
        } catch {
            return value;
        }
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function escapeAttribute(value) {
        return escapeHtml(value).replace(/`/g, "");
    }
});
