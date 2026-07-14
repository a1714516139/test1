# API 接口文档

Base URL: `/api/v1`

所有响应使用统一信封格式：

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": { "request_id": "...", "latency_ms": 123 }
}
```

---

## 1. 健康检查

```
GET /api/v1/health
```

**响应 200:**
```json
{
  "success": true,
  "data": { "status": "healthy", "version": "1.0.0" }
}
```

---

## 2. 上传并解析简历

```
POST /api/v1/resume/upload
Content-Type: multipart/form-data
```

**参数:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | PDF 简历文件（最大 10 MB） |

**响应 200:**
```json
{
  "success": true,
  "data": {
    "resume_id": "a1b2c3d4e5f6g7h8",
    "filename": "john_resume.pdf",
    "page_count": 2,
    "raw_text_length": 3420,
    "cleaned_text": "John Doe\nSoftware Engineer\n..."
  }
}
```

**错误:**
- `400` — 非 PDF 文件或文件损坏
- `413` — 文件过大

---

## 3. 提取关键信息

```
POST /api/v1/resume/extract
Content-Type: application/json
```

**请求体:**
```json
{
  "resume_id": "a1b2c3d4e5f6g7h8",
  "resume_text": "John Doe\nSoftware Engineer\n..."
}
```

**响应 200:**
```json
{
  "success": true,
  "data": {
    "resume_id": "a1b2c3d4e5f6g7h8",
    "extracted": {
      "name": "张三",
      "phone": "13800000000",
      "email": "zhangsan@example.com",
      "address": "北京市朝阳区",
      "job_intent": "高级Python开发工程师",
      "expected_salary": "25k-35k/月",
      "work_years": 5,
      "education": [
        {
          "degree": "本科",
          "major": "计算机科学与技术",
          "school": "北京大学",
          "year": 2018
        }
      ],
      "skills": ["Python", "FastAPI", "Docker", "AWS", "PostgreSQL"],
      "project_experience": [
        {
          "name": "电商平台",
          "role": "后端负责人",
          "description": "主导设计和开发了...",
          "duration_months": 18
        }
      ],
      "languages": ["中文(母语)", "英语(流利)"],
      "certifications": ["AWS Solutions Architect"]
    }
  }
}
```

---

## 4. 提取 JD 关键词

```
POST /api/v1/jd/extract-keywords
Content-Type: application/json
```

**请求体:**
```json
{
  "jd_text": "我们正在寻找一位具有5年以上经验的Python高级开发工程师，熟悉Docker、Kubernetes..."
}
```

**响应 200:**
```json
{
  "success": true,
  "data": {
    "keywords": [
      { "term": "python", "weight": 0.9, "category": "skill" },
      { "term": "docker", "weight": 0.9, "category": "skill" },
      { "term": "kubernetes", "weight": 0.9, "category": "skill" },
      { "term": "5", "weight": 0.8, "category": "experience" }
    ]
  }
}
```

---

## 5. 简历评分匹配

```
POST /api/v1/resume/score
Content-Type: application/json
```

**请求体:**
```json
{
  "resume_id": "a1b2c3d4e5f6g7h8",
  "resume_text": "John Doe\nSoftware Engineer...",
  "jd_text": "我们正在寻找一位具有5年以上经验的Python高级开发工程师...",
  "mode": "basic"
}
```

`mode`:
- `"basic"` — 关键词重叠 + 规则评分 (快，无需 LLM)
- `"ai"` — LLM 精确评分 (慢，质量高)

**响应 200:**
```json
{
  "success": true,
  "data": {
    "resume_id": "a1b2c3d4e5f6g7h8",
    "overall_score": 78.5,
    "breakdown": {
      "skill_match": {
        "score": 85.0,
        "details": "Matched 12/15 required skills"
      },
      "experience_match": {
        "score": 70.0,
        "details": "5 years vs 5+ required"
      },
      "education_match": {
        "score": 80.0,
        "details": "Bachelor matches requirement"
      },
      "keyword_overlap": {
        "score": 82.0,
        "matched": ["python", "fastapi", "docker"],
        "missing": ["kubernetes"]
      }
    },
    "matched_keywords": ["Python", "FastAPI", "Docker", "AWS"],
    "missing_keywords": ["Kubernetes", "Terraform"],
    "ai_analysis": null
  }
}
```

---

## 6. 一键分析 (组合接口)

```
POST /api/v1/resume/analyze
Content-Type: multipart/form-data
```

**参数:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | PDF 文件 |
| jd_text | string | 否 | 岗位需求描述 |
| mode | string | 否 | 评分模式: `basic` / `ai` |

此接口内部串联调用 upload → extract → score。

---

## 7. 查询缓存结果

```
GET /api/v1/resume/{resume_id}
```

**响应 200:** 返回缓存的解析结果

**错误:**
- `404` — 缓存中未找到该简历
