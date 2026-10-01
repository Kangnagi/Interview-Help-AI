
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import filedialog, messagebox


def load_csv(path):
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows.append({
                "time": float(row["time_sec"]),
                "face": int(row["face_detected"]),
                "landmark": int(row["landmark_detected"]),
                "landmark_count": int(row["landmark_count"]),
                "blink": float(row["blink_score"]),
                "expression": float(row["expression_score"]),
            })
    return rows


def draw_dashboard(rows, canvas, labels):
    for ax in axes:
        ax.clear()

    if not rows:
        return

    t = [r["time"] for r in rows]
    face = [r["face"] for r in rows]
    landmark = [r["landmark"] for r in rows]
    blink = [r["blink"] for r in rows]
    expression = [r["expression"] for r in rows]
    lc = [r["landmark_count"] for r in rows]

    face_rate = sum(face) / len(face) * 100
    landmark_rate = sum(landmark) / len(landmark) * 100
    avg_blink = sum(blink) / len(blink)
    avg_expression = sum(expression) / len(expression)

    # 1. Overall detection
    axes[0].bar(
        ["Face detection", "Landmark detection"],
        [face_rate, landmark_rate],
    )
    axes[0].set_ylim(0, 100)
    axes[0].set_ylabel("Detection rate (%)")
    axes[0].set_title("Face recognition stability")
    axes[0].grid(axis="y", alpha=0.3)

    # 2. Detection state over time
    axes[1].step(t, face, where="post", label="Face")
    axes[1].step(t, landmark, where="post", label="Landmark")
    axes[1].set_ylim(-0.1, 1.1)
    axes[1].set_yticks([0, 1])
    axes[1].set_yticklabels(["Not detected", "Detected"])
    axes[1].set_xlabel("Time (sec)")
    axes[1].set_title("Detection status over time")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    # 3. Blink / Expression
    axes[2].plot(t, blink, label="Blink score")
    axes[2].plot(t, expression, label="Expression score")
    axes[2].set_ylim(0, 100)
    axes[2].set_xlabel("Time (sec)")
    axes[2].set_ylabel("Score")
    axes[2].set_title("Face metrics over time")
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    # 4. Landmark count
    axes[3].plot(t, lc, label="Landmark count")
    axes[3].set_xlabel("Time (sec)")
    axes[3].set_ylabel("Count")
    axes[3].set_title("Detected landmark count")
    axes[3].legend()
    axes[3].grid(alpha=0.3)

    labels["face"].config(text=f"얼굴 검출률\n{face_rate:.1f}%")
    labels["landmark"].config(text=f"랜드마크 검출률\n{landmark_rate:.1f}%")
    labels["blink"].config(text=f"평균 Blink\n{avg_blink:.1f}")
    labels["expression"].config(text=f"평균 Expression\n{avg_expression:.1f}")

    fig.tight_layout()
    canvas.draw()


def choose_file():
    path = filedialog.askopenfilename(
        title="webcam_face_analysis.csv 선택",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if not path:
        return
    try:
        rows = load_csv(path)
        draw_dashboard(rows, canvas, labels)
        title_var.set(Path(path).name)
    except Exception as e:
        messagebox.showerror("오류", str(e))


root = tk.Tk()
root.title("MediaPipe 얼굴 인식 분석 대시보드")
root.geometry("1250x900")
root.minsize(1000, 750)

title_var = tk.StringVar(value="CSV 파일을 선택하세요")

header = tk.Frame(root, padx=15, pady=10)
header.pack(fill="x")

tk.Label(
    header,
    text="MediaPipe 얼굴 인식 분석",
    font=("Arial", 20, "bold"),
).pack(side="left")

tk.Button(
    header,
    text="CSV 불러오기",
    command=choose_file,
    font=("Arial", 11),
    padx=12,
    pady=6,
).pack(side="right")

tk.Label(
    root,
    textvariable=title_var,
    font=("Arial", 10),
).pack()

summary = tk.Frame(root, padx=15, pady=10)
summary.pack(fill="x")

labels = {}
for key in ("face", "landmark", "blink", "expression"):
    frame = tk.Frame(summary, relief="groove", borderwidth=1, padx=20, pady=10)
    frame.pack(side="left", expand=True, fill="x", padx=5)
    labels[key] = tk.Label(frame, text="-", font=("Arial", 15, "bold"))
    labels[key].pack()

fig, axes = plt.subplots(2, 2, figsize=(12, 7))
axes = axes.flatten()
fig.subplots_adjust(hspace=0.35, wspace=0.25)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=10)

# 시작 시 기본 결과 파일 자동 탐색
default_csv = Path(__file__).resolve().parent / "webcam_test_results" / "webcam_face_analysis.csv"
if default_csv.exists():
    try:
        rows = load_csv(default_csv)
        draw_dashboard(rows, canvas, labels)
        title_var.set(default_csv.name)
    except Exception:
        pass

root.mainloop()
