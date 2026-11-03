"""
3단계: 학습된 모델로 새 음성 평가 (추론)

  음성(.wav) → 로그-멜(학습 때와 같은 audio_features 전처리) → 모델 → 불합격 확률 → 0/1

사용법
  # 폴더 안 모든 음성 평가 (기본: predict_audio 폴더)
  python 03_predict.py
  python 03_predict.py --model train_results/best_model.pt --audio_root "C:/.../audio" --out predictions.csv
  # 음성 하나만
  python 03_predict.py --wav "C:/.../ckmk_a_bm_f_e_36391.wav"
  # 이미 만든 로그-멜 폴더로 빠르게
  python 03_predict.py --mel_dir logmel --out predictions.csv
  # 결과를 원래 특징 CSV의 score 열(2번째 열)에 채워 넣기
  python 03_predict.py ... --fill_csv extracted_features.csv --filled_out scored.csv

출력 CSV: key, p_fail_raw(모델 원본 확률·판정용), p_fail(보정된 불합격 확률·보여주기용), score(1=합격, 0=불합격)
  학습 때 불합격에 pos_weight 가중치를 줘서 원본 확률은 부풀려져 있음 → 오즈를 pos_weight로 나눠 보정
  보정은 단조 변환이라 판정(score)은 원본 확률·원본 임계값으로 한 것과 똑같음
"""
import os, re, glob, argparse
import numpy as np
import pandas as pd
import torch
from audio_features import wav_to_logmel
from voice_score_model import VoiceScoreNet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join("train_results", "best_model.pt"))
    ap.add_argument("--wav")
    ap.add_argument("--audio_root", default="predict_audio")
    ap.add_argument("--mel_dir")
    ap.add_argument("--out", default=os.path.join("predict_audio", "predictions.csv"))
    ap.add_argument("--threshold", type=float, default=None, help="비우면 학습 때 정한 값 사용")
    ap.add_argument("--fill_csv")
    ap.add_argument("--filled_out", default=os.path.join("predict_audio", "scored.csv"))
    a = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    ck = torch.load(a.model, map_location=device)
    model = VoiceScoreNet(n_mels=ck["n_mels"]).to(device)
    model.load_state_dict(ck["state_dict"]); model.eval()
    th = a.threshold if a.threshold is not None else ck["threshold"]
    max_frames = ck.get("max_frames", 6000)
    w = ck.get("pos_weight", 4.18)                 # 예전 체크포인트엔 없으므로 전체 라벨 기준값 사용
    th_cal = th / (th + w * (1 - th))              # 같은 기준을 보정 확률로 표현
    th_src = "직접 지정" if a.threshold is not None else {
        "f1": "학습 때 F1 최대 기준", "recall": f"학습 때 재현율 {ck.get('min_recall')} 목표 기준"}.get(ck.get("th_mode", "f1"))
    print(f"장치 {device}, 임계값 {th:.2f} ({th_src}, 보정 확률 기준 {th_cal:.2f}), pos_weight {w:.2f}")

    # 입력 목록 만들기
    if a.wav:
        items = [(a.wav, "wav")]
    elif a.mel_dir:
        items = [(p, "npy") for p in sorted(glob.glob(os.path.join(a.mel_dir, "*.npy")))]
    elif a.audio_root:
        items = [(p, "wav") for p in sorted(glob.glob(os.path.join(a.audio_root, "**", "*.wav"), recursive=True))]
    else:
        raise SystemExit("--wav, --audio_root, --mel_dir 중 하나를 지정하세요")
    if not items:
        raise SystemExit(f"평가할 음성이 없습니다. 폴더를 확인하세요: {a.wav or a.mel_dir or a.audio_root}")

    rows = []
    with torch.no_grad():
        for n, (p, kind) in enumerate(items):
            key = os.path.splitext(os.path.basename(p))[0]
            try:
                L = np.load(p) if kind == "npy" else wav_to_logmel(p, ck["n_mels"])
                L = L[:, :max_frames].astype(np.float32)
                x = torch.from_numpy(L)[None, None].to(device)
                prob = torch.sigmoid(model(x, torch.tensor([L.shape[1]]))).item()
                p_cal = prob / (prob + w * (1 - prob))    # 보정된 불합격 확률
                rows.append({"key": key, "p_fail_raw": round(prob, 4), "p_fail": round(p_cal, 4),
                             "score": 0 if prob >= th else 1})
            except Exception as e:
                rows.append({"key": key, "p_fail_raw": np.nan, "p_fail": np.nan, "score": np.nan,
                             "error": str(e)[:200]})
            if (n + 1) % 500 == 0:
                print(f"{n + 1}/{len(items)}")

    res = pd.DataFrame(rows)
    res.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"저장: {a.out}  (불합격 비율 {(res.score == 0).mean():.3f})")
    if a.wav:
        print(res.to_string(index=False))

    # 원래 CSV의 score 열만 채우기 (다른 열·행 순서는 그대로)
    if a.fill_csv:
        lab = dict(zip(res.key, res.score))
        out, filled = [], 0
        for line in open(a.fill_csv, encoding="utf-8-sig").read().splitlines():
            m = re.search(r"([^\\/]+)\.wav", line)
            if m and "," in line:
                r = line.split(",")
                k = m.group(1)
                if k in lab and not pd.isna(lab[k]):
                    r[1] = str(int(lab[k])); filled += 1
                line = ",".join(r)
            out.append(line)
        open(a.filled_out, "w", encoding="utf-8").write("\n".join(out) + "\n")
        print(f"{a.fill_csv} → {a.filled_out}: {filled}행 채움")


if __name__ == "__main__":
    main()
