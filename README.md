# 业务判断智能体

面向“计划任务书 / 立项申请书”的可解释文档裁决系统。用户上传单份或批量文件、输入判断 intent，系统返回 `通过 / 不通过`、命中规则、原文证据、理由与置信度。

## 快速启动

```bash
cp .env.example .env
# 在 .env 中配置 OPENAI_API_KEY
docker build -t judgment-agent .
docker run --env-file .env -p 8000:8000 judgment-agent
```

打开 <http://localhost:8000>。健康检查：`GET /health`；接口文档：`/docs`。

也可直接运行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 输入格式

- 单文档：PDF、DOCX、TXT、Markdown。
- 批量数据：JSON、JSONL、CSV。每条需有 `id`，正文列优先读取 `text`，其次 `content`。
- 单文件不超过 15 MB，一次最多 100 条。

请求示例：

```bash
curl -X POST http://localhost:8000/api/judge \
  -F 'dataset_type=立项申请书' \
  -F 'intent=判断创新程度是否足够' \
  -F 'files=@samples/demo.txt'
```

## 配置

| 环境变量 | 必填 | 说明 |
|---|---:|---|
| `OPENAI_API_KEY` | 正式评测必填 | 模型 API 密钥 |
| `OPENAI_MODEL` | 否 | 默认 `gpt-4.1-mini` |
| `OPENAI_BASE_URL` | 否 | OpenAI 兼容服务地址 |
| `PORT` | 否 | 默认 `8000` |

未配置 API Key 时，系统启用低置信度的本地演示规则，并标记 `needs_review=true`；该模式不用于正式评分。

## 公网部署

仓库已包含 `Dockerfile` 和 `render.yaml`。将代码推送至 GitHub 后，在 Render 选择 Blueprint 部署，并在控制台设置 `OPENAI_API_KEY`。Railway、Fly.io 或任意支持 Docker 的云平台也可直接部署。提交前务必从非登录浏览器验证 URL、上传流程和 `/health`。

## 测试

```bash
pip install pytest httpx
pytest -q
```

## 安全与限制

上传内容只在当前请求中处理，不写磁盘；前端显示内容经过 HTML 转义。生产环境建议进一步加入鉴权、速率限制、病毒扫描、云端日志脱敏和对象存储生命周期策略。扫描版 PDF 需要额外接入 OCR。

详细架构、规则发现与泛化策略见 [design.md](design.md)。

