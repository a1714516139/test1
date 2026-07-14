/**
 * AI Resume Analyzer — Single Page App
 * Upload PDF → auto-parse → auto-extract → display in 3 cards
 */
(function () {
    "use strict";

    // =====================================================================
    // State
    // =====================================================================
    let currentResumeId = null;
    let currentCleanedText = null;

    // =====================================================================
    // DOM refs
    // =====================================================================
    const uploadZone = document.getElementById("upload-zone");
    const fileInput = document.getElementById("file-input");
    const fileBar = document.getElementById("file-bar");
    const fileName = document.getElementById("file-name");
    const btnReset = document.getElementById("btn-reset");
    const progressBar = document.getElementById("progress-bar");
    const progressText = document.getElementById("progress-text");
    const resultGrid = document.getElementById("result-grid");
    const errorBox = document.getElementById("error-box");
    const errorText = document.getElementById("error-text");

    // =====================================================================
    // File selection
    // =====================================================================
    uploadZone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) startUpload(fileInput.files[0]);
    });

    // Drag & drop
    uploadZone.addEventListener("dragover", e => {
        e.preventDefault();
        uploadZone.classList.add("drag-over");
    });
    uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("drag-over"));
    uploadZone.addEventListener("drop", e => {
        e.preventDefault();
        uploadZone.classList.remove("drag-over");
        if (e.dataTransfer.files.length > 0) startUpload(e.dataTransfer.files[0]);
    });

    btnReset.addEventListener("click", reset);

    // =====================================================================
    // Upload + Parse + Extract
    // =====================================================================
    async function startUpload(file) {
        // Validate
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            showError("只接受 PDF 格式的文件");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showError("文件过大，最大支持 10 MB");
            return;
        }

        // Show file bar
        fileBar.style.display = "flex";
        fileName.textContent = file.name;

        // Show progress
        progressBar.style.display = "block";
        resultGrid.style.display = "none";
        errorBox.style.display = "none";

        try {
            // Step 1: Upload & parse PDF
            progressText.textContent = "正在上传并解析 PDF...";
            const uploadResp = await apiUploadResume(file);
            const uploadData = uploadResp.data;
            currentResumeId = uploadData.resume_id;
            currentCleanedText = uploadData.cleaned_text;

            // Step 2: Auto-extract info
            progressText.textContent = "AI 正在提取关键信息...";
            const extractResp = await apiExtractInfo(currentResumeId, currentCleanedText);
            const extracted = extractResp.data.extracted;

            // Step 3: Render
            renderResults(extracted);

            progressBar.style.display = "none";
            uploadZone.style.display = "none";
            resultGrid.style.display = "grid";
            resultGrid.scrollIntoView({ behavior: "smooth", block: "start" });

        } catch (e) {
            progressBar.style.display = "none";
            showError("解析失败: " + e.message);
        }
    }

    // =====================================================================
    // Render extracted info into 3 cards
    // =====================================================================
    function renderResults(ex) {
        // --- Card 1: 基本信息 ---
        const fieldsBasic = document.getElementById("fields-basic");
        fieldsBasic.innerHTML = "";
        fieldsBasic.appendChild(fieldItem("姓名", ex.name));
        fieldsBasic.appendChild(fieldItem("电话", ex.phone));
        fieldsBasic.appendChild(fieldItem("邮箱", ex.email));
        fieldsBasic.appendChild(fieldItem("地址", ex.address));

        // --- Card 2: 求职信息 ---
        const fieldsJob = document.getElementById("fields-job");
        fieldsJob.innerHTML = "";
        fieldsJob.appendChild(fieldItem("求职意向", ex.job_intent));
        fieldsJob.appendChild(fieldItem("期望薪资", ex.expected_salary));

        // --- Card 3: 背景信息 ---
        const fieldsBg = document.getElementById("fields-bg");
        fieldsBg.innerHTML = "";
        fieldsBg.appendChild(fieldItem("工作年限", ex.work_years != null ? ex.work_years + " 年" : null));

        // 学历背景
        fieldsBg.appendChild(renderEducation(ex.education));

        // 项目经历
        fieldsBg.appendChild(renderProjects(ex.project_experience));

        // 技能 (bonus)
        if (ex.skills && ex.skills.length > 0) {
            fieldsBg.appendChild(renderSkills(ex.skills));
        }
    }

    // =====================================================================
    // Field helpers
    // =====================================================================
    function fieldItem(label, value) {
        const div = document.createElement("div");
        div.className = "field-item";
        const hasVal = value !== null && value !== undefined && value !== "";
        div.innerHTML = `
            <div class="field-label">${label}</div>
            <div class="field-value${hasVal ? "" : " empty"}">${hasVal ? esc(String(value)) : "未识别"}</div>
        `;
        return div;
    }

    function renderEducation(eduList) {
        const div = document.createElement("div");
        div.className = "field-item";
        div.innerHTML = '<div class="field-label">学历背景</div>';

        if (!eduList || eduList.length === 0) {
            div.innerHTML += '<div class="field-value empty">未识别</div>';
        } else {
            const listDiv = document.createElement("div");
            listDiv.className = "sub-list";
            eduList.forEach(e => {
                const parts = [e.degree, e.major, e.school, e.year ? "(" + e.year + ")" : ""].filter(Boolean);
                const item = document.createElement("div");
                item.className = "sub-item";
                item.textContent = parts.join(" · ");
                listDiv.appendChild(item);
            });
            div.appendChild(listDiv);
        }
        return div;
    }

    function renderProjects(projList) {
        const div = document.createElement("div");
        div.className = "field-item";
        div.innerHTML = '<div class="field-label">项目经历</div>';

        if (!projList || projList.length === 0) {
            div.innerHTML += '<div class="field-value empty">未识别</div>';
        } else {
            const listDiv = document.createElement("div");
            listDiv.className = "sub-list";
            projList.forEach(p => {
                const parts = [];
                if (p.name) parts.push(p.name);
                if (p.role) parts.push("(" + p.role + ")");
                if (p.duration_months) parts.push(p.duration_months + "个月");
                const item = document.createElement("div");
                item.className = "sub-item";
                item.innerHTML = "<strong>" + esc(parts.join(" ")) + "</strong>";
                if (p.description) {
                    item.innerHTML += "<br><span style='font-size:0.8rem;color:#64748b;'>" + esc(p.description) + "</span>";
                }
                listDiv.appendChild(item);
            });
            div.appendChild(listDiv);
        }
        return div;
    }

    function renderSkills(skills) {
        const div = document.createElement("div");
        div.className = "field-item";
        div.innerHTML = '<div class="field-label">技能</div>';
        const tagsDiv = document.createElement("div");
        tagsDiv.className = "sub-list";
        skills.forEach(s => {
            const tag = document.createElement("span");
            tag.className = "sub-tag";
            tag.textContent = s;
            tagsDiv.appendChild(tag);
        });
        div.appendChild(tagsDiv);
        return div;
    }

    // =====================================================================
    // Error / Reset
    // =====================================================================
    function showError(msg) {
        errorBox.style.display = "flex";
        errorText.textContent = msg;
    }

    function reset() {
        currentResumeId = null;
        currentCleanedText = null;
        fileInput.value = "";
        fileBar.style.display = "none";
        progressBar.style.display = "none";
        resultGrid.style.display = "none";
        errorBox.style.display = "none";
        uploadZone.style.display = "block";
    }

    function esc(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }
})();
