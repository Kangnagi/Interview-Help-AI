"""
A1 학습 데이터 구성: 합성 데이터(v2.1) + 실제 면접 답변 채점 데이터(score_teacher_real)를 섞는다.

- 합성: split_teacher_dataset.py와 같은 방식(조합 단위, seed 42, 24개 조합)으로 평가셋을 떼어
        teacher_eval.jsonl을 v2.1 평가 때와 똑같이 만든다 → v2.1 어댑터와 같은 시험지로 비교 가능
- 실제: 채점 실패를 빼고 무작위로 200개를 real_eval.jsonl로 떼어 둔다 (학습에 절대 안 씀)
- 나머지를 섞어 mix_train.jsonl (meta 제거)

실행 (WSL):
    python build_mix_dataset.py
"""
import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
SYNTH = DATA / "score_teacher_qwen_v21.jsonl"
REAL = DATA / "score_teacher_real.jsonl"
SYNTH_EVAL_GROUPS = 24
REAL_EVAL_COUNT = 200


def read(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def write(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main():
    synth = read(SYNTH)
    groups = sorted({(r["meta"]["round"], r["meta"]["role"], r["meta"]["question"]) for r in synth})
    random.Random(42).shuffle(groups)
    held = set(groups[:SYNTH_EVAL_GROUPS])
    synth_eval = [r for r in synth if (r["meta"]["round"], r["meta"]["role"], r["meta"]["question"]) in held]
    synth_train = [{"messages": r["messages"]} for r in synth
                   if (r["meta"]["round"], r["meta"]["role"], r["meta"]["question"]) not in held]

    real = [r for r in read(REAL) if not r["meta"].get("failed")]
    random.Random(42).shuffle(real)
    real_eval, real_train = real[:REAL_EVAL_COUNT], [{"messages": r["messages"]} for r in real[REAL_EVAL_COUNT:]]

    mix = synth_train + real_train
    random.Random(7).shuffle(mix)
    write(DATA / "teacher_eval.jsonl", synth_eval)
    write(DATA / "real_eval.jsonl", real_eval)
    write(DATA / "mix_train.jsonl", mix)
    print(f"학습 {len(mix)}개 (합성 {len(synth_train)} + 실제 {len(real_train)}) / "
          f"평가 합성 {len(synth_eval)}개, 실제 {len(real_eval)}개")


if __name__ == "__main__":
    main()
