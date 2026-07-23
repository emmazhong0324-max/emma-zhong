import hashlib, json, os, re
from openai import AsyncOpenAI
from .schemas import EvidencePack, Judgment, RuleCandidate, RuleHit

SYSTEM = """你是业务评审智能体。只依据文档证据判断，不得为了输出'通过'而脑补。规则名称必须是对当前 intent 的可复用语义规则，而不是复述样本文字。区分'未提及'和'明确不满足'；除非属于必备/否决项，证据缺失不能自动判不通过。引用证据要短且可在原文定位。输出严格 JSON。"""

def extract_list(payload, key: str) -> list:
    """Accept either a bare JSON array or an object containing that array."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        value=payload.get(key, [])
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [value]
    return []

class JudgeAgent:
    def __init__(self):
        self.model=os.getenv("OPENAI_MODEL","gpt-4.1-mini")
        self.client=AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY","missing"), base_url=os.getenv("OPENAI_BASE_URL") or None)

    async def _json(self, prompt: str) -> dict:
        r=await self.client.chat.completions.create(model=self.model, temperature=0, response_format={"type":"json_object"}, messages=[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}])
        return json.loads(r.choices[0].message.content)

    async def judge(self, sid: str, dtype: str, intent: str, text: str) -> Judgment:
        if not os.getenv("OPENAI_API_KEY"):
            return self._fallback(sid,dtype,intent,text)
        excerpt=text[:50000]
        facts=EvidencePack.model_validate(await self._json(f"抽取与判断意图相关的事实、缺失和矛盾。不得下结论。\n类型:{dtype}\n意图:{intent}\n文档:\n{excerpt}\n输出 facts,missing,contradictions 字符串数组。"))
        rules_raw=await self._json(f"基于业务常识和以下事实提出3-7条判定规则。规则ID为 R-01 起；区分加分规则和 blocking 否决规则。\n类型:{dtype}\n意图:{intent}\n证据包:{facts.model_dump_json()}\n输出 rules 数组，每项含 rule_id,rule_name,criterion,required_evidence,blocking。")
        rules=[RuleCandidate.model_validate(x) for x in extract_list(rules_raw,"rules")]
        result=await self._json(f"执行独立裁决。仅命中有明确原文证据的规则。类别不平衡不能改变单条事实判断。若 blocking 规则明确触发则不通过；否则综合核心规则。\n样本ID:{sid}\n类型:{dtype}\n意图:{intent}\n证据包:{facts.model_dump_json()}\n候选规则:{json.dumps([r.model_dump() for r in rules],ensure_ascii=False)}\n输出 id,dataset_type,intent,label,matched_rules(reason字段结构: rule_id,rule_name,evidence,polarity,confidence),reason,confidence,needs_review。")
        result.update(id=sid,dataset_type=dtype,intent=intent)
        return Judgment.model_validate(result)

    def _fallback(self,sid,dtype,intent,text):
        positive=["创新","首创","突破","专利","可行","验收","完成","达到","明确","量化"]
        negative=["缺失","未完成","不可行","不符合","无创新","照搬","逾期","造假","重大风险"]
        ps=sum(text.count(x) for x in positive); ns=sum(text.count(x) for x in negative)
        label="通过" if ps>ns+1 else "不通过"
        key=(positive if label=="通过" else negative)
        hits=[]
        for word in key:
            m=re.search(rf"[^。\n]{{0,35}}{re.escape(word)}[^。\n]{{0,35}}",text)
            if m: hits.append(RuleHit(rule_id=f"R-{len(hits)+1:02d}",rule_name=f"文档明确体现{word}",evidence=m.group(0),polarity="支持" if label=="通过" else "反对",confidence=.45))
            if len(hits)>=3: break
        return Judgment(id=sid,dataset_type=dtype,intent=intent,label=label,matched_rules=hits,reason="当前为无 API Key 的演示性规则裁决，请配置模型后用于正式评测。",confidence=.35,needs_review=True)
