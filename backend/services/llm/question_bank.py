"""
직무 기본 질문 — AI 질문 생성이 실패하거나 사용할 수 있는 질문이 모자랄 때 채우는 질문 목록.

화면이 보내는 지원 정보(resume_text)의 '지원 회사: …', '지원 직무: …' 줄에서 회사·직무를 꺼내
질문 문장에 넣는다. 정보가 없으면 '지원하신', '우리 회사'로 바꿔도 자연스럽게 읽히도록 문장을 짰다.
(모델 없이 동작 — 항상 같은 품질)
"""
import re
from typing import Optional

# {job}: 지원 직무 (없으면 '지원하신'), {company}: 지원 회사 (없으면 '우리 회사')
_TEMPLATES = [
    "{job} 직무에서 가장 중요하다고 생각하는 역량은 무엇이며, 그 역량을 발휘했던 경험을 구체적으로 말씀해 주세요.",
    "{job} 직무와 관련된 프로젝트나 실무 경험 중 가장 어려웠던 문제와, 그 문제를 해결한 과정을 말씀해 주세요.",
    "{company}에 입사한다면 첫 1년 동안 어떤 목표를 세우고, 그 목표를 어떻게 달성하시겠습니까?",
    "팀으로 일하면서 의견 충돌이 있었을 때 어떻게 조율했는지 구체적인 사례를 들어 말씀해 주세요.",
    "{job} 분야에서 최근 관심 있게 본 기술이나 변화는 무엇이며, 그것이 업무에 어떤 영향을 줄 것이라고 생각하나요?",
    "실패했거나 기대만큼 결과가 나오지 않았던 경험과, 그 경험에서 배운 점을 말씀해 주세요.",
    "본인의 강점과 보완이 필요한 점을 하나씩 말씀하고, 보완을 위해 어떤 노력을 하고 있는지 설명해 주세요.",
    "{job} 업무를 하면서 마감이나 우선순위가 겹치는 상황이 생긴다면 어떻게 대처하시겠습니까?",
]


def _field(resume_text: str, label: str) -> Optional[str]:
    m = re.search(rf"^{label}\s*:\s*(.+)$", resume_text or "", re.MULTILINE)
    return m.group(1).strip()[:40] if m and m.group(1).strip() else None


def fallback_questions(resume_text: str, count: int, exclude: Optional[list] = None) -> list:
    """직무 기본 질문 count개 (exclude에 있는 질문은 건너뜀)."""
    job = _field(resume_text, "지원 직무")
    if job:
        job = re.sub(r"\s*직무$", "", job) or None   # '백엔드 직무' → '백엔드' ('직무 직무' 방지)
    company = _field(resume_text, "지원 회사")
    exclude = set(exclude or [])
    out = []
    for t in _TEMPLATES:
        q = t.format(job=job or "지원하신", company=company or "우리 회사")
        if q not in exclude:
            out.append(q)
        if len(out) >= count:
            break
    return out
