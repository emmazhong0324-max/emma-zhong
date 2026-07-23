import asyncio
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .agent import JudgeAgent
from .parser import split_records

app=FastAPI(title="业务判断智能体",version="1.0.0")
static=Path(__file__).parent.parent/"static"
app.mount("/static",StaticFiles(directory=static),name="static")

def safe_model_error(exc: Exception) -> str:
    """Return a useful UI message without exposing provider details or secrets."""
    message=str(exc).lower()
    if any(token in message for token in ("invalid_api_key", "incorrect api key", "authentication", "401")):
        return "模型服务认证失败，请联系管理员检查服务器端 API Key 配置。"
    if any(token in message for token in ("insufficient_quota", "rate_limit", "429")):
        return "模型服务额度不足或请求过于频繁，请稍后重试。"
    return "智能评审暂时失败，请稍后重试。"

@app.get("/")
def home(): return FileResponse(static/"index.html")

@app.get("/health")
def health(): return {"status":"ok"}

@app.post("/api/judge")
async def judge(dataset_type: str=Form(...), intent: str=Form(...), files: list[UploadFile]=File(...)):
    if dataset_type not in {"计划任务书","立项申请书"}: raise HTTPException(400,"无效的数据集类型")
    if not intent.strip(): raise HTTPException(400,"intent 不能为空")
    records=[]
    try:
        for f in files: records.extend(split_records(f.filename or "upload.txt",await f.read()))
    except Exception as e: raise HTTPException(400,str(e))
    if len(records)>100: raise HTTPException(400,"单次最多100条")
    agent=JudgeAgent(); sem=asyncio.Semaphore(4)
    async def run(x):
        async with sem: return await agent.judge(x[0],dataset_type,intent,x[1])
    results=await asyncio.gather(*(run(x) for x in records),return_exceptions=True)
    out=[]
    for (sid,_),r in zip(records,results):
        out.append(r.model_dump() if not isinstance(r,Exception) else {"id":sid,"error":safe_model_error(r)})
    return {"count":len(out),"results":out}
