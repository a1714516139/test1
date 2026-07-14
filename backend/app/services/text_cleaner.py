"""Text cleaning and normalization for extracted resume text."""
import re
import unicodedata


def clean_text(raw_text: str) -> str:
    """Apply a pipeline of normalizations to raw PDF text.

    Steps:
    1. Normalize Unicode (NFC)
    2. Fix hyphenated line-breaks (common in PDF columns)
    3. Collapse excessive newlines into section breaks
    4. Strip control characters except newlines and tabs
    5. Normalize whitespace within lines
    6. Attempt to fix garbled encodings

    Args:
        raw_text: Raw text extracted from PDF.

    Returns:
        Cleaned, structured text ready for LLM or regex processing.
    """
    text = raw_text

    # 1. Unicode normalization (NFC composed form)
    text = unicodedata.normalize("NFC", text)

    # 2. Fix hyphenated line-breaks: "pro-\ngramming" → "programming"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # 3. Collapse 3+ newlines into double newlines (section breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 4. Strip control characters, but keep \n and \t
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # 5. Normalize whitespace within lines (preserve line structure)
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = re.sub(r"[ \t]+", " ", line)  # collapse multiple spaces/tabs
        line = line.strip()
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    # 6. Remove completely blank lines between section breaks
    text = re.sub(r"\n\n\n+", "\n\n", text)

    # 7. Attempt to fix common PDF garbled characters
    text = _fix_common_garbling(text)

    return text.strip()


def _fix_common_garbling(text: str) -> str:
    """Fix common character encoding issues seen in PDF extraction."""
    replacements = {
        "ﬁ": "fi",   # ﬁ ligature
        "ﬂ": "fl",   # ﬂ ligature
        "–": "-",    # en dash
        "—": "--",   # em dash
        "‘": "'",    # left single quote
        "’": "'",    # right single quote
        "“": '"',    # left double quote
        "”": '"',    # right double quote
        "…": "...",  # ellipsis
        " ": " ",    # non-breaking space
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def segment_sections(cleaned_text: str) -> dict:
    """Attempt to segment resume text into logical sections.

    Uses common section headers (Chinese + English) to split the text.

    Returns:
        Dict mapping section name to its text content.
    """
    section_markers = [
        ("personal_info", ["个人信息", "基本信息", "Personal Information", "CONTACT"]),
        ("job_intent", ["求职意向", "求职目标", "Career Objective", "Objective", "JOB INTENT"]),
        ("education", ["教育背景", "教育经历", "学历", "Education", "EDUCATION"]),
        ("work_experience", ["工作经历", "工作经验", "工作背景", "Work Experience", "EXPERIENCE"]),
        ("projects", ["项目经历", "项目经验", "Projects", "PROJECT EXPERIENCE"]),
        ("skills", ["技能", "专业技能", "技术栈", "Skills", "SKILLS"]),
        ("certifications", ["证书", "资格证书", "Certifications", "CERTIFICATIONS"]),
        ("languages", ["语言", "语言能力", "Languages", "LANGUAGES"]),
    ]

    sections = {}
    remaining = cleaned_text

    # Simple approach: find sections by header patterns
    for section_name, markers in section_markers:
        for marker in markers:
            pattern = re.compile(rf"(?:^|\n)\s*{re.escape(marker)}\s*(?:\n|$|:)", re.IGNORECASE)
            match = pattern.search(remaining)
            if match:
                start = match.end()
                sections[section_name] = remaining[start:].strip()
                break

    return sections
