"""
학습한 점수 어댑터를 평가셋(학습에 안 쓴 데이터)으로 검증한다.

- JSON 형식 준수율: 백엔드가 파싱할 수 있는 {"score","feedback","tip"}를 내놓는지
- 점수 오차(MAE): 같은 답변에 정답 라벨(선생님 모델 점수)과 얼마나 차이 나는지
- 평가셋에 meta.target_level이 있으면 품질 단계별 평균 점수도 출력

실행:
    python eval_score_adapter.py --adapter_dir output/llama-3.2-3b-score-teacher --eval_path data/teacher_eval.jsonl
"""
import argparse
import json
import re
from collections import defaultdict

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL = "meta-llama/Llama-3.2-3B-Instruct"
LEVEL_NAMES = ["매우 부실", "부족", "보통", "좋음", "매우 우수"]


def parse_json(text: str):
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        text = m.group(1).strip() if m else text
    si, ei = text.find("{"), text.rfind("}")
    if si == -1 or ei <= si:
        raise ValueError("JSON 객체 없음")
    return json.loads(text[si:ei + 1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter_dir", required=True)
    parser.add_argument("--eval_path", required=True)
    parser.add_argument("--batch_size", type=int, default=8)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.adapter_dir, padding_side="left")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.bfloat16, device_map={"": 0})
    model = PeftModel.from_pretrained(base, args.adapter_dir)
    model.eval()

    examples = [json.loads(l) for l in open(args.eval_path, encoding="utf-8") if l.strip()]
    valid, errors = 0, []
    by_level = defaultdict(lambda: {"label": [], "pred": []})

    for b in range(0, len(examples), args.batch_size):
        batch = examples[b:b + args.batch_size]
        prompts = [tokenizer.apply_chat_template(ex["messages"][:2], tokenize=False, add_generation_prompt=True)
                   for ex in batch]
        enc = tokenizer(prompts, return_tensors="pt", padding=True).to(model.device)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=700, do_sample=False,
                                 pad_token_id=tokenizer.pad_token_id)
        for k, (ex, o) in enumerate(zip(batch, out), b + 1):
            label = json.loads(ex["messages"][2]["content"])
            text = tokenizer.decode(o[enc["input_ids"].shape[-1]:], skip_special_tokens=True)
            try:
                pred = parse_json(text)
                score = int(pred["score"])
                if not (pred.get("feedback") and pred.get("tip")):
                    raise ValueError("feedback/tip 누락")
                valid += 1
                errors.append(abs(score - label["score"]))
                lvl = ex.get("meta", {}).get("target_level")
                if lvl is not None:
                    by_level[lvl]["label"].append(label["score"])
                    by_level[lvl]["pred"].append(score)
                print(f"[{k}] 정답 {label['score']:>3} / Llama {score:>3}  (차이 {abs(score - label['score'])})",
                      flush=True)
            except Exception as e:
                print(f"[{k}] 파싱 실패: {e} — 출력: {text[:120]!r}", flush=True)

    print("\n=== 결과 ===")
    print(f"JSON 형식 준수: {valid}/{len(examples)}")
    if errors:
        print(f"점수 평균 오차(MAE): {sum(errors) / len(errors):.1f}점")
        print(f"10점 이내 일치: {sum(e <= 10 for e in errors)}/{len(errors)}")
    for lvl in sorted(by_level):
        d = by_level[lvl]
        print(f"레벨 {lvl} ({LEVEL_NAMES[lvl]}): 정답 평균 {sum(d['label']) / len(d['label']):5.1f} / "
              f"Llama 평균 {sum(d['pred']) / len(d['pred']):5.1f}  (범위 {min(d['pred'])}~{max(d['pred'])}, "
              f"{len(d['pred'])}개)")


if __name__ == "__main__":
    main()
