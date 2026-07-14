/**
 * API Client — fetch wrappers for all backend endpoints.
 *
 * Change API_BASE to match your deployed backend URL.
 */
const API_BASE = "http://127.0.0.1:8000/api/v1";

// =========================================================================
// Internal helpers
// =========================================================================

/**
 * Generic JSON request with timeout.
 */
async function _request(method, path, body = null, isFormData = false) {
    const opts = { method };

    if (isFormData) {
        opts.body = body; // FormData
    } else if (body) {
        opts.headers = { "Content-Type": "application/json" };
        opts.body = JSON.stringify(body);
    }

    const controller = new AbortController();
    opts.signal = controller.signal;
    const timer = setTimeout(() => controller.abort(), 120_000); // 2 min timeout

    let resp;
    try {
        resp = await fetch(`${API_BASE}${path}`, opts);
    } catch (e) {
        if (e.name === "AbortError") {
            throw new Error("请求超时 (120s)，请稍后重试");
        }
        throw new Error(`网络错误: ${e.message}`);
    } finally {
        clearTimeout(timer);
    }

    const json = await resp.json();

    if (!resp.ok || !json.success) {
        const msg = json.error || json.detail || `HTTP ${resp.status}`;
        throw new Error(msg);
    }

    return json;
}

// =========================================================================
// Public API
// =========================================================================

/** Upload a PDF resume for parsing. Returns { resume_id, cleaned_text, ... }. */
async function apiUploadResume(file) {
    const fd = new FormData();
    fd.append("file", file);
    return _request("POST", "/resume/upload", fd, true);
}

/** Extract structured info from resume text. */
async function apiExtractInfo(resumeId, resumeText) {
    return _request("POST", "/resume/extract", {
        resume_id: resumeId,
        resume_text: resumeText,
    });
}

/** Extract keywords from a job description. */
async function apiExtractJDKeywords(jdText) {
    return _request("POST", "/jd/extract-keywords", {
        jd_text: jdText,
    });
}

/** Score a resume against a JD. mode: "basic" or "ai". */
async function apiScoreResume(resumeId, resumeText, jdText, mode = "basic") {
    return _request("POST", "/resume/score", {
        resume_id: resumeId,
        resume_text: resumeText,
        jd_text: jdText,
        mode: mode,
    });
}

/** Composite: upload + extract + score in one call. */
async function apiAnalyzeResume(file, jdText = "", mode = "basic") {
    const fd = new FormData();
    fd.append("file", file);
    if (jdText) fd.append("jd_text", jdText);
    fd.append("mode", mode);
    return _request("POST", "/resume/analyze", fd, true);
}
