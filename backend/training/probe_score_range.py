"""
점수 어댑터가 답변 품질을 30/70 두 값 이상으로 구분하는지 확인하는 프로브.
품질이 확연히 다른 답변(엉망 → 매우 우수)을 같은 질문에 넣고 점수 변화를 본다.
"""
import argparse
import json
import re

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL = "meta-llama/Llama-3.2-3B-Instruct"
# generate_teacher_scores.SCORING_SYSTEM_PROMPT와 동일 (학습 데이터의 시스템 프롬프트)
SYSTEM_PROMPT = (
    "당신은 10년 차 전문 인사담당자이자 AI 면접관입니다.\n"
    "지원자의 면접 질문과 답변을 분석하여 반드시 아래 JSON 형식으로만 응답하세요 (코드블록 금지).\n"
    "feedback의 각 항목은 1~2문장으로 간결하게 작성하세요.\n"
    '{"score":0~100,"feedback":"1. 잘한 점\\n2. 아쉬운 점 및 개선 방향\\n3. 모범 답변 방향성 제안",'
    '"tip":"다음 답변을 위한 실질적 개선 팁 한 문장"}'
)

PROBES = [
    ("지원 동기가 무엇인가요?", "엉망", "그냥요. 돈 벌려고요."),
    ("지원 동기가 무엇인가요?", "미흡", "회사가 유명하고 복지가 좋다고 들어서 지원했습니다."),
    ("지원 동기가 무엇인가요?", "보통",
     "귀사의 백엔드 개발 직무에 관심이 있어 지원했습니다. 대학에서 서버 개발 프로젝트를 해봤고, 그 경험을 살리고 싶습니다."),
    ("지원 동기가 무엇인가요?", "우수",
     "귀사의 결제 플랫폼이 하루 수백만 건의 트랜잭션을 처리한다는 점에 매력을 느꼈습니다. 저는 인턴십에서 "
     "주문 API의 응답 시간을 800ms에서 120ms로 줄이며 캐시 전략과 쿼리 최적화를 경험했고, 이런 대용량 트래픽 "
     "환경에서 안정성과 성능을 함께 책임지는 개발자로 성장하고 싶습니다. 특히 귀사가 최근 도입한 이벤트 기반 "
     "아키텍처에 기여하고, 장기적으로는 결제 도메인 전문가가 되는 것이 목표입니다."),
    ("가장 어려웠던 문제를 해결한 경험을 말해주세요.", "엉망", "잘 모르겠습니다."),
    ("가장 어려웠던 문제를 해결한 경험을 말해주세요.", "보통",
     "팀 프로젝트에서 서버가 자주 다운되는 문제가 있었는데, 로그를 확인해서 메모리 누수를 찾아 고쳤습니다."),
    ("가장 어려웠던 문제를 해결한 경험을 말해주세요.", "우수",
     "졸업 프로젝트에서 동시 접속자가 200명을 넘으면 서버가 다운되는 문제가 있었습니다(상황). 제 역할은 원인 "
     "분석과 해결이었습니다(과제). 부하 테스트 도구로 재현한 뒤 프로파일링을 해보니 DB 커넥션 풀이 고갈되는 "
     "것이 원인이었고, 커넥션 풀 크기 조정과 N+1 쿼리 제거, 읽기 전용 쿼리의 캐싱을 적용했습니다(행동). 그 결과 "
     "동시 접속 1,000명까지 안정적으로 처리했고, 평균 응답 시간도 40% 단축됐습니다(결과). 이 경험으로 추측보다 "
     "측정을 먼저 하는 습관을 갖게 됐습니다."),
    # v2에서 추가 — 사람 검토에서 문제가 된 유형
    ("Kafka 같은 메시지 큐를 사용해 본 경험이 있다면, 어떤 상황에서 왜 선택했는지 설명해주세요.", "모름",
     "사용한 경험이 없습니다."),
    ("자기소개서에 작성하신 경험에 대해 더 자세히 설명해 주세요.", "나열",
     "저는 백엔드 개발 5년 경력이 있으며 대용량 트래픽 처리, 데이터베이스 최적화, MSA, 클라우드 인프라 경험을 "
     "두루 보유하고 있습니다. 항상 성장하는 개발자가 되기 위해 노력하고 있으며 귀사에 꼭 기여하고 싶습니다."),
    ("실시간 데이터 분석 파이프라인을 구축한다면 수집부터 활용까지 어떻게 구성하시겠습니까?", "설계우수",
     "수집은 서비스 이벤트를 Kafka로 비동기 발행해 API 응답 지연과 분석 부하를 분리하겠습니다. 처리는 순서 보장과 "
     "윈도우 집계가 필요해 Flink를 쓰고, 트래픽이 적은 초기에는 운영 부담을 줄이려고 Spark Structured Streaming의 "
     "마이크로배치도 검토하겠습니다. 실시간 지표는 Redis에, 검색·대시보드용 데이터는 Elasticsearch에 저장하고, "
     "원본은 S3에 적재해 배치 분석과 재처리에 쓰겠습니다. 지연 시간과 비용이 트레이드오프라서 지표별로 필요한 "
     "신선도를 먼저 정의하고, 파이프라인 지연·유실을 모니터링하는 알림을 함께 두겠습니다."),
]


def parse_score(text):
    m = re.search(r'"score"\s*:\s*(\d+)', text)
    return int(m.group(1)) if m else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter_dir", required=True)
    parser.add_argument("--base_model", default=BASE_MODEL, help="어댑터를 학습한 기본 모델 (예: Bllossom 경로)")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.adapter_dir)
    base = AutoModelForCausalLM.from_pretrained(args.base_model, torch_dtype=torch.bfloat16, device_map={"": 0})
    eos = [tokenizer.eos_token_id, tokenizer.convert_tokens_to_ids("<|eot_id|>")]   # Bllossom은 <|eot_id|> 직접 지정
    model = PeftModel.from_pretrained(base, args.adapter_dir)
    model.eval()

    for question, quality, answer in PROBES:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"면접 질문: {question}\n지원자 답변: {answer}"},
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        enc = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=700, do_sample=False,
                                 pad_token_id=tokenizer.eos_token_id, eos_token_id=eos)
        text = tokenizer.decode(out[0][enc["input_ids"].shape[-1]:], skip_special_tokens=True)
        print(f"[{quality:>2}] {question[:20]:<20} → 점수 {parse_score(text)}", flush=True)


if __name__ == "__main__":
    main()
