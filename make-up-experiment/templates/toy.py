"""共享玩具库：零依赖（只用 math / json），供各章脚本复用。

复制后按主题删减：只保留这条链需要的算子。
约定：
- 所有数字只有一个来源：data/toy_world.json
- 不 import torch / 不连网 / 不碰 GPU
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "data" / "toy_world.json"


# --------------------------------------------------------------------------- #
# 数据
# --------------------------------------------------------------------------- #
def load_world(path: Path | str = WORLD_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# 概率与信息量
# --------------------------------------------------------------------------- #
def softmax(z: Sequence[float]) -> List[float]:
    m = max(z)
    e = [math.exp(x - m) for x in z]
    s = sum(e)
    return [x / s for x in e]


def log_softmax(z: Sequence[float]) -> List[float]:
    m = max(z)
    lse = m + math.log(sum(math.exp(x - m) for x in z))
    return [x - lse for x in z]


def entropy(p: Sequence[float]) -> float:
    return -sum(x * math.log(x) for x in p if x > 0.0) or 0.0


def kl(p: Sequence[float], q: Sequence[float]) -> float:
    return sum(x * (math.log(x) - math.log(y)) for x, y in zip(p, q) if x > 0.0)


def cross_entropy(p: Sequence[float], q: Sequence[float]) -> float:
    """H(p, q) = -Σ p·log q：p 是目标，q 是预测。"""
    return -sum(x * math.log(y) for x, y in zip(p, q) if x > 0.0)


def one_hot(i: int, n: int) -> List[float]:
    v = [0.0] * n
    v[i] = 1.0
    return v


def normalize(p: Sequence[float]) -> List[float]:
    s = sum(p)
    return [x / s for x in p]


# --------------------------------------------------------------------------- #
# 标签编码（分类目标）
# --------------------------------------------------------------------------- #
def two_hot(d: float, bins: int = 4, lo: float = 1.0) -> List[float]:
    """标量目标 → 相邻两桶的线性插值分布（一阶矩恰为 clamp(d)）。"""
    d = min(max(float(d), lo), float(bins))
    k = int(math.floor(d))
    alpha = d - k
    q = [0.0] * bins
    q[k - 1] += 1.0 - alpha
    q[min(k + 1, bins) - 1] += alpha
    return q


def decode(q: Sequence[float]) -> float:
    """期望解码：Σ_b b·q_b（b 从 1 开始）。"""
    return sum((b + 1) * p for b, p in enumerate(q))


# --------------------------------------------------------------------------- #
# 优化器（与 torch.optim.AdamW 默认一致）
# --------------------------------------------------------------------------- #
class AdamW:
    def __init__(self, params: Sequence[float], lr: float = 1e-2,
                 betas: Tuple[float, float] = (0.9, 0.999), eps: float = 1e-8,
                 weight_decay: float = 0.01) -> None:
        self.p = list(params)
        self.lr, self.b1, self.b2, self.eps, self.wd = lr, betas[0], betas[1], eps, weight_decay
        self.m = [0.0] * len(self.p)
        self.v = [0.0] * len(self.p)
        self.t = 0

    def step(self, grads: Sequence[float]) -> List[float]:
        self.t += 1
        for i, g in enumerate(grads):
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * g
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * g * g
            mh = self.m[i] / (1 - self.b1 ** self.t)
            vh = self.v[i] / (1 - self.b2 ** self.t)
            self.p[i] -= self.lr * (mh / (math.sqrt(vh) + self.eps) + self.wd * self.p[i])
        return self.p


# --------------------------------------------------------------------------- #
# 打印与断言
# --------------------------------------------------------------------------- #
def table(headers: Sequence[str], rows: Iterable[Sequence], digits: int = 6) -> None:
    def fmt(x) -> str:
        if isinstance(x, float):
            return f"{x:.{digits}f}"
        return str(x)

    cells = [[fmt(h) for h in headers]] + [[fmt(c) for c in r] for r in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    for r_i, row in enumerate(cells):
        print("  ".join(c.rjust(w) for c, w in zip(row, widths)))
        if r_i == 0:
            print("  ".join("-" * w for w in widths))


class Checker:
    """每章末尾的断言表：全 PASS 才算正文与代码一致。"""

    def __init__(self) -> None:
        self.items: List[Tuple[str, bool, str]] = []

    def ok(self, name: str, cond: bool, note: str = "") -> None:
        self.items.append((name, bool(cond), note))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({note})" if note else ""))

    def report(self) -> None:
        bad = [x for x in self.items if not x[1]]
        print(f"\n{len(self.items) - len(bad)}/{len(self.items)} PASS")
        if bad:
            raise SystemExit(1)


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def banner(text: str) -> None:
    print("\n" + "=" * 72)
    print(text)
    print("=" * 72)
