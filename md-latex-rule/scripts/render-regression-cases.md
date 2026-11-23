<!--
render_check.mjs / check_md_math.mjs 的回归探针（2026-09-20）。

期望结果（故意制造失败，勿当成可发布文档）：
- check_md_math.mjs：UNCLOSED-DOLLAR ×2（P1 两行）+ INDENTED-BLOCK ×2（P2）
  + unicodeTextInMathMode 警告（P3/P4 的中文标点）
- render_check.mjs：FAIL；P1 报 MULTILINE-INLINE ×2 + RAW-DELIMITER ×1；
  P2–P7 其余正常（P3/P4 只出 CONSOLE WARN）；
  P8（2026-10-05 新增，纯文本公式）应正常原样显示，不应报 KATEX-ERROR / RAW-DELIMITER / NO-MATH。
若 render_check 对 P1 报 PASS，说明 `<pre>` 跳过逻辑又把跨行公式漏掉了。
-->

# 渲染探针：真实 Vditor 行为测试

> 目的：测定下列写法在 zaaack Markdown Editor 的真实 webview 中
> 是渲染、还是显示为源码。每个小节只含一种病灶。

## P1 跨行行内公式（硬失败）

**P1**：奖励是 $r_j = \mathrm{sg}(\log p_T(a_j) -
\log p_\theta(a_j))$ 之后。

## P2 列表内缩进块公式（Vditor 可渲染，GFM 不可）

1. **条目**：极小点使学生的

   $$
   \bar\pi_\theta(\cdot \mid s) = q_T(\cdot \mid s)
   $$

   在候选集上成立。

## P3 块公式内含中文句号（渲染但 Console warn）

$$
s_t \in \mathcal{S}, \quad a_t \in \mathcal{A},
\quad r_t = -1 \text{（或终局 } r_T = 0 \text{）}。
$$

## P4 \text 外的中文右括号（渲染但 Console warn）

$$
\quad r_t = -1 \text{（或终局 } r_T = 0）。
$$

## P5 对照组：\text 内 CJK（正常）

价值定义为 $d(s) = \mathbb{E}[\text{剩余步数} \mid s]$，以及
$\text{（成功链）}$ 的说明。

## P6 对照组：行内公式紧贴中文标点（正常）

均值记为 $\bar{x}$，方差 $\sigma^2$，用量 $\approx$ 1B 参数。

## P7 对照组：代码围栏内的美元号（正常，不应报）

```
$a = b$ 与 \(x\) 都是字面量
```

## P8 对照组：纯文本公式（2026-10-05 首选策略；正常，不应报）

```text
L_pol = -(1/T) Σₜ log πθ(a*ₜ | s, a*₋ₜ)
θ     ← θ + η·(r - 2βΔ) · ∇log πθ(a | s)
```

行内纯文本写法：`πθ(a|s)`、`xₜ`、`a/b`、`Σₜ xₜ`、`1 - solve@16 ∈ [0.5, 0.9]`
——应原样显示为等宽文本，不产生 KaTeX 节点，也不应触发任何错误告警。
