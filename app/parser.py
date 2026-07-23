import csv, io, json, re, subprocess, tempfile
from pathlib import Path
from docx import Document
from pypdf import PdfReader

MAX_FILE = 15 * 1024 * 1024

def _clean(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.replace("\x00", "")).strip()

def parse_single(name: str, data: bytes) -> str:
    if len(data) > MAX_FILE:
        raise ValueError("单个文件不能超过 15MB")
    ext = Path(name).suffix.lower()
    if ext in {".txt", ".md"}:
        return _clean(data.decode("utf-8", errors="replace"))
    if ext == ".pdf":
        return _clean("\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages))
    if ext == ".docx":
        doc = Document(io.BytesIO(data))
        return _clean("\n".join(p.text for p in doc.paragraphs))
    if ext == ".doc":
        with tempfile.NamedTemporaryFile(suffix=".doc") as source:
            source.write(data)
            source.flush()
            try:
                result = subprocess.run(
                    ["antiword", source.name],
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
            except FileNotFoundError as exc:
                raise ValueError("服务器尚未安装 DOC 解析组件") from exc
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ValueError("无法解析该 DOC 文件，请确认文件未损坏") from exc
        return _clean(result.stdout.decode("utf-8", errors="replace"))
    raise ValueError(f"不支持的文件类型: {ext or '未知'}")

def split_records(name: str, data: bytes) -> list[tuple[str, str]]:
    ext = Path(name).suffix.lower()
    if ext == ".jsonl":
        rows=[]
        for i, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
            if not line.strip(): continue
            obj=json.loads(line); rows.append((str(obj.get("id", f"sample_{i:03d}")), str(obj.get("text") or obj.get("content") or obj)))
        return rows
    if ext == ".json":
        obj=json.loads(data.decode("utf-8-sig")); items=obj if isinstance(obj,list) else obj.get("data",[obj])
        return [(str(x.get("id",f"sample_{i:03d}")), str(x.get("text") or x.get("content") or x)) for i,x in enumerate(items,1)]
    if ext == ".csv":
        rows=csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        return [(str(r.get("id") or f"sample_{i:03d}"), str(r.get("text") or r.get("content") or r)) for i,r in enumerate(rows,1)]
    return [(Path(name).stem, parse_single(name,data))]
