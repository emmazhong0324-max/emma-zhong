import csv, html, io, json, re, subprocess, tempfile, zipfile, zlib
from pathlib import Path
from docx import Document
from pypdf import PdfReader
from xml.etree import ElementTree

MAX_FILE = 15 * 1024 * 1024

def _clean(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.replace("\x00", "")).strip()

def _libreoffice_text(name: str, data: bytes) -> str:
    suffix=Path(name).suffix.lower() or ".doc"
    with tempfile.TemporaryDirectory() as temp_dir:
        source=Path(temp_dir)/f"source{suffix}"
        source.write_bytes(data)
        try:
            subprocess.run(
                [
                    "libreoffice", "--headless", "--convert-to", "txt:Text",
                    "--outdir", temp_dir, str(source),
                ],
                capture_output=True,
                check=True,
                timeout=60,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ""
        converted=Path(temp_dir)/"source.txt"
        if not converted.exists():
            return ""
        return _clean(converted.read_text(encoding="utf-8-sig", errors="replace"))

def _word_xml_text(xml_bytes: bytes) -> str:
    """Extract paragraphs in document order, including text inside table cells."""
    if not xml_bytes:
        return ""
    try:
        root=ElementTree.fromstring(xml_bytes)
        namespace="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs=[]
        for paragraph in root.iter(f"{namespace}p"):
            text="".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
            if text.strip():
                paragraphs.append(text)
        return _clean("\n".join(paragraphs))
    except ElementTree.ParseError:
        raw=xml_bytes.decode("utf-8",errors="ignore")
        raw=re.sub(r"</w:p>", "\n", raw)
        pieces=re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>",raw,flags=re.S)
        return _clean(html.unescape("\n".join(re.sub(r"<[^>]+>","",piece) for piece in pieces)))

def _salvage_docx(data: bytes) -> str:
    """Extract document.xml without CRC validation when the payload is still readable."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info=archive.getinfo("word/document.xml")
        header=data[info.header_offset:info.header_offset+30]
        if len(header) != 30 or header[:4] != b"PK\x03\x04":
            return ""
        name_length=int.from_bytes(header[26:28],"little")
        extra_length=int.from_bytes(header[28:30],"little")
        start=info.header_offset+30+name_length+extra_length
        compressed=data[start:start+info.compress_size]
        if info.compress_type == zipfile.ZIP_STORED:
            xml_bytes=compressed
        elif info.compress_type == zipfile.ZIP_DEFLATED:
            try:
                xml_bytes=zlib.decompress(compressed,-15)
            except zlib.error:
                decompressor=zlib.decompressobj(-15)
                recovered=[]
                for offset in range(0,len(compressed),4096):
                    try:
                        recovered.append(decompressor.decompress(compressed[offset:offset+4096]))
                    except zlib.error:
                        break
                xml_bytes=b"".join(recovered)
        else:
            return ""
        return _word_xml_text(xml_bytes)
    except (KeyError, OSError, ValueError, zipfile.BadZipFile):
        return ""

def parse_single(name: str, data: bytes) -> str:
    if len(data) > MAX_FILE:
        raise ValueError("单个文件不能超过 15MB")
    ext = Path(name).suffix.lower()
    if ext in {".txt", ".md"}:
        return _clean(data.decode("utf-8", errors="replace"))
    if ext == ".pdf":
        return _clean("\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages))
    if ext == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                text=_word_xml_text(archive.read("word/document.xml"))
            if text:
                return text
        except Exception:
            salvaged=_salvage_docx(data)
            if salvaged:
                return salvaged
            recovered=_libreoffice_text(name,data)
            if recovered:
                return recovered
            raise ValueError("该 DOCX 文件内部结构或校验值已损坏，请用 Word/WPS 打开后“另存为”新的 DOCX 再上传")
        try:
            doc = Document(io.BytesIO(data))
            return _clean("\n".join(p.text for p in doc.paragraphs))
        except Exception:
            raise ValueError("该 DOCX 文件不含可读取的正文内容")
    if ext == ".doc":
        with tempfile.TemporaryDirectory() as temp_dir:
            source=Path(temp_dir)/"source.doc"
            source.write_bytes(data)
            try:
                result = subprocess.run(
                    ["antiword", str(source)],
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
                text=_clean(result.stdout.decode("utf-8", errors="replace"))
                if text:
                    return text
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
            text=_libreoffice_text(name,data)
            if text:
                return text
        raise ValueError("无法解析该 DOC 文件，请确认它是有效的 Word 97-2003 文档；也可另存为 DOCX 后重试")
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
