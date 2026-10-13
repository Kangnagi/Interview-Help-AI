"""
모델 정의: VoiceScoreNet (CNN → 양방향 GRU → 완전연결 → 로지스틱 출력층)
02(학습) · 03(예측)이 모두 이 파일을 불러 씀
"""
import torch
import torch.nn as nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence


# ---------------- 배치 구성 ----------------
def collate(batch):
    """길이가 다른 스펙트로그램들을 0으로 채워 한 배치로. 실제 길이는 따로 전달"""
    xs, lens, ys = zip(*batch)
    M, T = xs[0].shape[0], max(lens)
    out = torch.zeros(len(xs), 1, M, T)
    for i, x in enumerate(xs):
        out[i, 0, :, : x.shape[1]] = x
    return out, torch.tensor(lens), torch.tensor(ys, dtype=torch.float32)


# ---------------- 모델 ----------------
def conv_block(cin, cout, pool):
    return nn.Sequential(nn.Conv2d(cin, cout, 3, padding=1), nn.BatchNorm2d(cout),
                         nn.ReLU(), nn.MaxPool2d(pool))


class VoiceScoreNet(nn.Module):
    """
    텐서 모양 흐름 (B=배치, T=프레임 수)
      입력           (B, 1, 64, T)
      CNN 블록1      (B, 32, 32, T/2)
      CNN 블록2      (B, 64, 16, T/4)
      CNN 블록3      (B, 128, 8, T/4)   ← 주파수만 한 번 더 축소
      시간축으로 펼침 (B, T/4, 1024)     ← 80ms마다 1024차원 벡터
      양방향 GRU      (B, T/4, 256)
      평균+최대 풀링  (B, 512)           ← 길이 무관 고정 벡터
      완전연결        (B, 64)
      로지스틱 출력층 (B, 1)             ← 불합격 로짓
    """
    def __init__(self, n_mels=64, rnn_hidden=128, fc_hidden=64, dropout=0.3):
        super().__init__()
        self.cnn = nn.Sequential(conv_block(1, 32, (2, 2)),
                                 conv_block(32, 64, (2, 2)),
                                 conv_block(64, 128, (2, 1)))
        self.gru = nn.GRU(128 * (n_mels // 8), rnn_hidden, batch_first=True, bidirectional=True)
        self.fc = nn.Sequential(nn.Linear(4 * rnn_hidden, fc_hidden), nn.ReLU(), nn.Dropout(dropout))
        self.logistic = nn.Linear(fc_hidden, 1)       # ← 출력층 = 로지스틱 회귀

    def embed(self, x, lens):
        h = self.cnn(x)
        h = h.permute(0, 3, 1, 2).flatten(2)
        l2 = torch.clamp(lens // 4, min=1, max=h.shape[1])
        packed = pack_padded_sequence(h.float(), l2.cpu(), batch_first=True, enforce_sorted=False)
        h, _ = self.gru(packed)                       # 채운 0 구간은 GRU가 읽지 않음
        h, _ = pad_packed_sequence(h, batch_first=True)
        mask = (torch.arange(h.shape[1], device=h.device)[None, :]
                < l2.to(h.device)[:, None]).unsqueeze(-1)
        mean = (h * mask).sum(1) / mask.sum(1)
        mx = h.masked_fill(~mask, -1e4).max(1).values
        return self.fc(torch.cat([mean, mx], 1))

    def forward(self, x, lens):
        return self.logistic(self.embed(x, lens)).squeeze(1)
