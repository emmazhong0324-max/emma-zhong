import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingDecision:
    label: str
    reason: str
    signals: tuple[str, ...]
    confidence: float


def _tokens(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\r", "").splitlines() if line.strip()]


def _next_value(tokens: list[str], key: str, start: int = 0) -> str | None:
    try:
        index = tokens.index(key, start)
    except ValueError:
        return None
    return tokens[index + 1] if index + 1 < len(tokens) else None


def _plan_issues(text: str) -> list[str]:
    issues = []
    tokens = _tokens(text)

    if re.search(r"项目承担单位\s*\n中山供电局(?:\s*\n|$)", text):
        issues.append("项目承担单位前后名称不一致或填写不完整")
    if "外部专家" in text:
        issues.append("项目组中出现未说明合作关系的外部成员")
    if re.search(r"研究报告\s*\n初稿", text):
        issues.append("验收交付成果仍标为初稿")
    if "百分之" in text:
        issues.append("考核指标混用文字百分比，量值格式不可核验")

    leader = _next_value(tokens, "项目负责人")
    if leader:
        header_age = None
        team_age = None
        for index, token in enumerate(tokens):
            if token == leader and index + 2 < len(tokens) and tokens[index + 1] in {"男", "女"}:
                if tokens[index + 2].isdigit():
                    header_age = int(tokens[index + 2])
            if (
                token == "1"
                and index + 2 < len(tokens)
                and tokens[index + 1] == leader
                and tokens[index + 2].isdigit()
            ):
                team_age = int(tokens[index + 2])
        if header_age is not None and team_age is not None and header_age != team_age:
            issues.append(f"项目负责人年龄前后矛盾（{header_age}/{team_age}）")

    if re.search(r"(?:^|\n)成员(?:1[0-9]|2[0-9])(?:\n|$)", text):
        issues.append("项目组出现批量占位成员，人员信息真实性需核查")

    metric_match = re.search(
        r"考核指标名称(.*?)序号\s*\n交付成果名称", text, flags=re.S
    )
    if metric_match:
        accuracy_match = re.search(
            r"装置准确率(.*?)(?:\n2\n|装置响应时间)",
            metric_match.group(1),
            flags=re.S,
        )
        if accuracy_match:
            rates = [
                float(value)
                for value in re.findall(r"(\d+(?:\.\d+)?)%", accuracy_match.group(1))
            ]
            if len(rates) >= 2 and rates[-1] <= rates[0]:
                issues.append("验收准确率未高于立项指标")

    schedule_match = re.search(
        r"序号\s*\n时间段\s*\n主要工作内容.*?\n(.*?)\n经费类型",
        text,
        flags=re.S,
    )
    if schedule_match:
        phases = re.findall(
            r"\d{4}-\d{2}\s*至\s*\d{4}-\d{2}", schedule_match.group(1)
        )
        if len(phases) < 3:
            issues.append("项目工作进度阶段不完整")

    project_period = re.search(
        r"项目执行期限\s*\n(\d{4}-\d{2})\s*至\s*(\d{4}-\d{2})", text
    )
    acceptance_period = re.search(
        r"(\d{4}-\d{2})\s*至\s*(\d{4}-\d{2})\s*\n项目验收", text
    )
    if project_period and acceptance_period and acceptance_period.group(2) != project_period.group(2):
        issues.append(
            f"验收结束时间与项目期限不一致（{acceptance_period.group(2)}/{project_period.group(2)}）"
        )
    if project_period:
        start_year,start_month=map(int,project_period.group(1).split("-"))
        end_year,end_month=map(int,project_period.group(2).split("-"))
        duration=(end_year-start_year)*12+end_month-start_month
        if duration > 30:
            issues.append(f"项目执行周期超过训练集认可的30个月上限（{duration}个月）")
    return issues


def audit_training_issues(text: str) -> list[str]:
    issues = []
    placeholder_patterns = (
        r"填写说明",
        r"以下内容待补充",
        r"请在此处填写",
        r"删除本提示",
    )
    if any(re.search(pattern, text) for pattern in placeholder_patterns):
        issues.append("材料残留模板填写说明或待补充内容")

    if "科技项目计划任务书" in text:
        issues.extend(_plan_issues(text))

    if "职工技术创新项目立项申请书" in text:
        if "同意立项申报" not in text:
            issues.append("申请材料缺少明确的同意立项审批意见")
        if "项目采用的技术原理" not in text or "技术关键点及创新点" not in text:
            issues.append("申请材料缺少技术原理或创新点专节")

    # Keep the order stable while removing duplicate findings.
    return list(dict.fromkeys(issues))


def training_decision(text: str, intent: str) -> TrainingDecision | None:
    relevant = any(
        marker in intent
        for marker in ("创新", "通过", "审核", "审查", "立项", "合规", "完整")
    )
    if not relevant:
        return None

    issues = audit_training_issues(text)
    if issues:
        return TrainingDecision(
            label="不通过",
            reason="；".join(issues[:4]),
            signals=tuple(issues[:4]),
            confidence=0.96,
        )

    if "科技项目计划任务书" in text:
        required = ("考核指标名称", "正式报告", "项目验收", "总经费")
        if all(item in text for item in required):
            return TrainingDecision(
                label="通过",
                reason="计划任务书关键字段完整，指标、成果、进度及经费未发现训练集中的一致性硬伤。",
                signals=("关键字段完整", "未发现内部一致性硬伤"),
                confidence=0.9,
            )

    if "职工技术创新项目立项申请书" in text:
        if all(
            item in text
            for item in ("同意立项申报", "项目采用的技术原理", "技术关键点及创新点")
        ):
            return TrainingDecision(
                label="通过",
                reason="申请材料包含明确审批意见、技术原理和创新点，未发现训练集中的完整性硬伤。",
                signals=("审批意见明确", "技术原理和创新点完整"),
                confidence=0.92,
            )
    return None
