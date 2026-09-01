---
id: coae-tips-first-order-evasion-code-9b71d5f0
title: 'COAE 一阶规避攻击考试代码模板'
aliases:
  - FGSM Exam Template
  - I-FGSM Exam Template
  - DeepFool Exam Template
domain:
  - '技巧提示'
note_type:
  - cheatsheet
  - guide
attack_phase:
  - inference
status: validated
tags:
  - coae
  - ai-security
  - adversarial-ml
updated: 2026-08-17
---
# COAE 一阶规避攻击考试代码模板

> 这里保存的是题型级代码积木，不是绑定某个 Challenge 的完整 solver。考试时只需复制需要的算法、输入输出适配和验证块，再替换标有 `TODO` 的位置。仅用于课程靶场、自有模型或明确授权环境。

对应原理：[[一阶梯度规避攻击FGSM与I-FGSM从零学习笔记]]、[[DeepFool最小扰动规避攻击从零学习笔记]]。

完整通用模块：[first_order_evasion_exam_template.py](../_工具/first_order_evasion_exam_template.py)。

## 0. 先判断题型

```text
攻击目标：targeted 还是 untargeted
攻击方法：FGSM / I-FGSM(BIM) / DeepFool
预算口径：pixel-space L∞ / pixel-space L2 / normalized-space L2
模型输入：像素 [0,1] 还是已经 normalized
模型输出：raw logits / log_softmax / probabilities
传输格式：PNG base64 / 原始 tensor / 数组
```

| 方法 | 典型目标 | 预算 | 核心操作 |
|---|---|---|---|
| FGSM | 目标或非目标 | $L_\infty$ | 一次梯度符号更新 |
| I-FGSM / BIM | 目标或非目标 | $L_\infty$ | 多轮更新并投影回预算球 |
| DeepFool | 常见为非目标，也可固定目标 | $L_2$ | 投影到局部线性决策边界 |

## 1. 最小 imports

```python
import base64
import io
import json

import numpy as np
from PIL import Image
import requests
import torch
from torch import nn
import torch.nn.functional as F
```

不要一开始导入所有可能依赖；复制了哪一块，再保留那一块需要的 imports。

## 2. 像素空间模型包装块

攻击代码统一接收 $[0,1]$ 像素张量，normalization 放进模型包装器：

```python
class PixelSpaceModel(nn.Module):
    def __init__(self, base_model, mean, std):
        super().__init__()
        self.base_model = base_model
        self.register_buffer(
            "mean", torch.tensor(mean, dtype=torch.float32)[None, :, None, None]
        )
        self.register_buffer(
            "std", torch.tensor(std, dtype=torch.float32)[None, :, None, None]
        )

    def forward(self, x01):
        return self.base_model((x01 - self.mean) / self.std)


# TODO：按题目替换 base_model 和统计量。
# MNIST: mean=[0.1307], std=[0.3081]
# CIFAR-10: mean=[0.4914,0.4822,0.4465], std=[0.2470,0.2435,0.2616]
pixel_model = PixelSpaceModel(base_model, mean, std).to(device).eval()
```

这样自动微分会通过 normalization 使用链式法则，不需要手工再除一次 `std`。

## 3. FGSM 通用积木

```python
def fgsm(model, images, labels, epsilon, targeted=False):
    """images: (B,C,H,W) in [0,1]; model returns raw logits."""
    x = images.detach().clone().requires_grad_(True)
    loss = F.cross_entropy(model(x), labels)
    gradient = torch.autograd.grad(loss, x)[0]
    direction = -1.0 if targeted else 1.0
    return torch.clamp(
        x + direction * epsilon * gradient.sign(), 0.0, 1.0
    ).detach()
```

调用：

```python
# 非目标：labels 是原始类别，增加真实类 loss。
x_adv = fgsm(pixel_model, x, original_labels, epsilon, targeted=False)

# 目标：labels 是目标类别，降低目标类 loss。
x_adv = fgsm(pixel_model, x, target_labels, epsilon, targeted=True)
```

## 4. I-FGSM / BIM 通用积木

```python
def iterative_fgsm(
    model,
    images,
    labels,
    epsilon,
    step_size,
    max_iterations,
    targeted=False,
):
    original = images.detach().clone()
    adversarial = original.clone()
    direction = -1.0 if targeted else 1.0

    for _ in range(max_iterations):
        current = adversarial.detach().requires_grad_(True)
        loss = F.cross_entropy(model(current), labels)
        gradient = torch.autograd.grad(loss, current)[0]
        candidate = current + direction * step_size * gradient.sign()

        # 投影中心永远是干净图 original。
        delta = torch.clamp(candidate - original, -epsilon, epsilon)
        adversarial = torch.clamp(original + delta, 0.0, 1.0).detach()

    return adversarial
```

调用：

```python
x_adv = iterative_fgsm(
    pixel_model,
    x,
    target_labels,          # 非目标攻击时改为 original_labels
    epsilon=8/255,
    step_size=2/255,
    max_iterations=20,
    targeted=True,
)
```

## 5. Targeted DeepFool 通用积木

```python
def deepfool_targeted(
    model,
    image,
    target_class,
    overshoot=0.02,
    max_iterations=100,
):
    """Single image (1,C,H,W), pixel-space model."""
    original = image.detach().clone()
    perturbation = torch.zeros_like(original)

    for _ in range(max_iterations):
        current = torch.clamp(
            original + (1.0 + overshoot) * perturbation, 0.0, 1.0
        ).detach().requires_grad_(True)
        logits = model(current)
        prediction = int(logits.argmax(dim=1).item())
        if prediction == target_class:
            break

        grad_current = torch.autograd.grad(
            logits[0, prediction], current, retain_graph=True
        )[0]
        grad_target = torch.autograd.grad(
            logits[0, target_class], current
        )[0]
        normal = grad_target - grad_current
        gap = logits[0, target_class] - logits[0, prediction]
        denominator = normal.flatten().square().sum().clamp_min(1e-12)
        perturbation += ((gap.abs() / denominator + 1e-6) * normal).detach()

    return torch.clamp(
        original + (1.0 + overshoot) * perturbation, 0.0, 1.0
    ).detach()
```

## 6. Untargeted DeepFool 通用积木

```python
def deepfool_untargeted(model, image, overshoot=0.02, max_iterations=50):
    original = image.detach().clone()
    adversarial = original.clone()
    with torch.no_grad():
        original_class = int(model(original).argmax(dim=1).item())

    for _ in range(max_iterations):
        current = adversarial.detach().requires_grad_(True)
        logits = model(current)
        current_class = int(logits.argmax(dim=1).item())
        if current_class != original_class:
            break

        grad_current = torch.autograd.grad(
            logits[0, current_class], current, retain_graph=True
        )[0]
        best_distance = float("inf")
        best_normal = None
        best_gap = None

        for class_index in range(logits.shape[1]):
            if class_index == current_class:
                continue
            grad_class = torch.autograd.grad(
                logits[0, class_index], current, retain_graph=True
            )[0]
            normal = grad_class - grad_current
            gap = logits[0, class_index] - logits[0, current_class]
            distance = gap.abs() / normal.flatten().norm(p=2).clamp_min(1e-12)
            if float(distance) < best_distance:
                best_distance = float(distance)
                best_normal, best_gap = normal, gap

        if best_normal is None:
            break
        denominator = best_normal.flatten().square().sum().clamp_min(1e-12)
        step = (best_gap.abs() / denominator + 1e-6) * best_normal
        adversarial = torch.clamp(
            current + (1.0 + overshoot) * step, 0.0, 1.0
        ).detach()

    return adversarial
```

## 7. 距离和成功判定积木

```python
def perturbation_metrics(adversarial, original, tolerance=1e-6):
    delta = adversarial - original
    dims = tuple(range(1, delta.ndim))
    return {
        "l0": (delta.abs() > tolerance).sum(dim=dims),
        "l1": delta.abs().sum(dim=dims),
        "l2": delta.square().sum(dim=dims).sqrt(),
        "linf": delta.abs().amax(dim=dims),
    }


def success_mask(model, adversarial, labels, targeted=False):
    with torch.no_grad():
        predictions = model(adversarial).argmax(dim=1)
    return predictions.eq(labels) if targeted else predictions.ne(labels)
```

Normalized-space $L_2$ 单独计算：

```python
def normalized_l2(adversarial, original, std):
    std_tensor = torch.tensor(
        std, device=original.device, dtype=original.dtype
    )[None, :, None, None]
    return ((adversarial - original) / std_tensor).flatten(1).norm(p=2, dim=1)
```

因为两张图使用相同 `mean`，差分中的 `mean` 会抵消，只剩除以 `std`。

## 8. PNG/base64 回环积木

```python
def encode_png(x4d, mode="L"):
    array = x4d[0, 0] if mode == "L" else np.transpose(x4d[0], (1, 2, 0))
    x255 = np.clip(np.rint(array * 255.0), 0, 255).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(x255, mode=mode).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def decode_png(encoded, mode="L"):
    image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert(mode)
    array = np.asarray(image, dtype=np.float32) / 255.0
    if mode == "L":
        return array[None, None, ...]
    return np.transpose(array, (2, 0, 1))[None, ...]
```

提交前必须验证量化后的版本：

```python
mode = "L"  # TODO：RGB 题改为 "RGB"
encoded = encode_png(x_adv.detach().cpu().numpy(), mode)
x_submitted = torch.from_numpy(decode_png(encoded, mode)).to(device)

metrics = perturbation_metrics(x_submitted, x)
passed = success_mask(pixel_model, x_submitted, attack_labels, targeted)
assert bool(passed.all()), (passed, metrics)
```

## 9. API 适配积木

字段和路径只在一个位置定义：

```python
API = {
    "challenge_path": "/challenge",       # TODO
    "weights_path": "/weights",           # TODO
    "submit_path": "/submit",             # TODO
    "image_key": "image_b64",              # TODO
    "label_key": "label",                  # TODO
    "target_key": "target_class",          # TODO
    "budget_key": "epsilon",               # TODO
    "submit_image_key": "image_b64",       # TODO
}


def get_json(host, path):
    response = requests.get(f"{host.rstrip('/')}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def post_json(host, path, body):
    response = requests.post(
        f"{host.rstrip('/')}{path}", json=body, timeout=60
    )
    if not response.ok:
        print("Server response:", response.text)
    response.raise_for_status()
    return response.json()
```

考试时不要把 `/challenge`、`image_b64` 等假设散落到攻击函数中。

## 10. 权重加载积木

```python
checkpoint = torch.load(weights_path, map_location=device, weights_only=True)
state_dict = checkpoint.get("state_dict", checkpoint)
base_model.load_state_dict(state_dict, strict=True)
pixel_model.eval()

with torch.no_grad():
    clean_prediction = pixel_model(x).argmax(dim=1)
assert torch.equal(clean_prediction.cpu(), original_labels.cpu()), (
    clean_prediction,
    original_labels,
    "检查模型结构、权重、通道顺序和 normalization",
)
```

如果 checkpoint 还包含 `arch`，应显式选择对应模型类；不要在架构不匹配时使用 `strict=False` 掩盖错误。

## 11. Assessment 多样本拼装骨架

```python
results = []

for item in payload["items"]:                       # TODO：列表字段
    sample_id = item["sample_id"]
    method = item["required_method"].lower()
    x = torch.from_numpy(decode_png(item[API["image_key"]], mode)).to(device)

    if method == "fgsm":
        x_adv = fgsm(pixel_model, x, labels, epsilon, targeted=False)
    elif method in {"ifgsm", "bim"}:
        x_adv = iterative_fgsm(
            pixel_model, x, attack_labels,
            epsilon, step_size, max_iterations, targeted=targeted,
        )
    elif method == "deepfool":
        x_adv, _ = deepfool_untargeted(pixel_model, x)
    else:
        raise ValueError(f"Unknown method: {method}")

    # TODO：PNG 回环后重新验证成功条件和预算。
    results.append({
        "sample_id": sample_id,
        "method": method,
        API["submit_image_key"]: encode_png(x_adv.cpu().numpy(), mode),
    })

submission = {"items": results}                    # TODO：顶层字段
```

这里只负责拼装；算法函数不读取 HTTP、不解析 JSON，也不打印 Flag。

## 12. 最小自测

```powershell
python .\_工具\first_order_evasion_exam_template.py
```

预期输出：

```text
First-order evasion template self-tests passed.
```

## 13. 高频错误

```text
[ ] targeted 使用负号，untargeted 使用正号
[ ] I-FGSM 每轮都投影到以原图为中心的 L∞ 球
[ ] 攻击代码操作 pixel-space [0,1]
[ ] normalization 只做一次
[ ] 原始模型返回 raw logits；若返回 log_softmax，要确认损失契约
[ ] DeepFool 的预算口径与服务器一致
[ ] PNG/base64 提交前做量化回环
[ ] clean prediction 与题目标签一致
[ ] 最终显式验证预测、targeted/untargeted 成功条件和距离
[ ] 模型架构与 state_dict 使用 strict=True 匹配
```

## 14. 新题只记录差异

以后收到 FGSM、I-FGSM 或 DeepFool 新题，只追加下列内容，不再保存一次性完整 solver：

```text
新增模型结构：
JSON 字段映射：
接口路径映射：
攻击目标与预算空间：
提交格式：
需要替换的 TODO：
最小自测：
```
