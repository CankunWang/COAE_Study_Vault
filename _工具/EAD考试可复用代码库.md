---
id: coae-tool-ead-exam-3d91a785
title: '稀疏攻击考试可复用代码库（EAD 与 JSMA）'
aliases:
  - EAD Exam Code Bank
  - Sparsity Attack Exam Code Bank
domain:
  - 'vault'
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
# 稀疏攻击考试可复用代码库（EAD 与 JSMA）

> 通用算法模块：[ead_exam_template.py](ead_exam_template.py) 与 [jsma_exam_template.py](jsma_exam_template.py)
>
> 原理笔记：[[稀疏规避攻击与EAD从零学习笔记]]
>
> 用途：按“可复制积木”维护 EAD、FISTA、JSMA、练习题与 Skill Assessment 代码。这里不绑定固定靶机、模型结构、URL 或 JSON 字段；考试时只替换标有 `TODO` 的适配点。仅用于本地模型、课程靶场或明确授权环境。

---

## 0. 已包含的函数

| 类别 | 可复用函数 |
|---|---|
| 环境 | set_reproducibility、EADConfig |
| 标签 | to_onehot |
| 距离 | compute_distances、count_changed_spatial_pixels |
| 损失 | compute_adversarial_loss、compute_total_loss |
| 成功判定 | check_attack_success、check_margin_success |
| 近端操作 | soft_threshold、apply_shrinkage_thresholding |
| FISTA | compute_fista_momentum、fista_step |
| 二分搜索 | update_binary_search_bounds |
| 完整攻击 | elastic_net_attack |
| 自测 | run_basic_self_tests |
| JSMA | JSMAConfig、compute_jacobian、saliency_scores、jsma_targeted |

---

## 1. 考试前先运行自测

~~~powershell
python .\_工具\ead_exam_template.py
~~~

期望输出：

~~~text
EAD template basic tests passed.
~~~

---

## 2. 导入模板

~~~python
from ead_exam_template import (
    EADConfig,
    apply_shrinkage_thresholding,
    check_attack_success,
    check_margin_success,
    compute_adversarial_loss,
    compute_distances,
    compute_fista_momentum,
    compute_total_loss,
    elastic_net_attack,
    fista_step,
    set_reproducibility,
    soft_threshold,
    to_onehot,
    update_binary_search_bounds,
)
~~~

若脚本不在同一目录：

~~~python
import sys
sys.path.append(r"D:\COAE_Study_Vault\_工具")

from ead_exam_template import EADConfig, elastic_net_attack
~~~

---

## 3. 环境准备块

~~~python
import torch

from ead_exam_template import (
    EADConfig,
    elastic_net_attack,
    set_reproducibility,
)

set_reproducibility(1337)

device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

model = model.to(device)
model.eval()
~~~

模型需要标准化时，将预处理包装进模型，让攻击变量继续位于像素空间：

~~~python
class NormalizedModel(torch.nn.Module):
    def __init__(self, model, mean, std):
        super().__init__()
        self.model = model
        self.register_buffer("mean", mean)
        self.register_buffer("std", std)

    def forward(self, pixel_images):
        normalized = (
            pixel_images - self.mean
        ) / self.std
        return self.model(normalized)
~~~

---

## 4. 距离指标块

~~~python
metrics = compute_distances(
    adv_images=adv_images,
    original_images=original_images,
    beta=0.01,
    tolerance=1e-6,
)

print("L0:", metrics["l0"])
print("L1:", metrics["l1"])
print("L2:", metrics["l2"])
print("L2 squared:", metrics["l2_squared"])
print("Elastic:", metrics["elastic"])
~~~

~~~text
L0 = 非零坐标数量
L1 = 绝对变化总量
L2 = 真正欧氏距离
L2² = EAD 内部平方距离
Elastic = L2² + beta * L1
~~~

---

## 5. Margin Loss 块

~~~python
selected_onehot = to_onehot(
    attack_labels,
    num_classes=logits.shape[1],
).to(logits.device)

loss_per_example = compute_adversarial_loss(
    logits=logits,
    selected_onehot=selected_onehot,
    confidence=0.0,
    targeted=False,
)
~~~

~~~text
Untargeted: max(Z_real - max_other + kappa, 0)
Targeted:   max(max_other - Z_target + kappa, 0)

Untargeted 的 attack_labels 是原始标签。
Targeted 的 attack_labels 是目标标签。
~~~

---

## 6. 软阈值块

~~~python
candidate_delta = candidate_images - original_images
threshold = learning_rate * beta

sparse_delta = soft_threshold(
    candidate_delta,
    threshold,
)

adv_images = torch.clamp(
    original_images + sparse_delta,
    min=0.0,
    max=1.0,
)
~~~

封装版本：

~~~python
adv_images = apply_shrinkage_thresholding(
    candidate_images=candidate_images,
    original_images=original_images,
    threshold=learning_rate * beta,
    clip_min=0.0,
    clip_max=1.0,
)
~~~

---

## 7. 单轮 FISTA 块

~~~python
adv_images, y_momentum, diagnostics = fista_step(
    adv_images=adv_images,
    y_momentum=y_momentum,
    original_images=original_images,
    selected_onehot=selected_onehot,
    const=const,
    model=model,
    beta=beta,
    learning_rate=learning_rate,
    confidence=confidence,
    iteration=iteration,
    targeted=targeted,
    clip_min=0.0,
    clip_max=1.0,
)
~~~

~~~text
y.detach().requires_grad_(True)
→ smooth loss = c * adversarial + L2²
→ autograd.grad(loss.sum(), y)
→ candidate = y - learning_rate * gradient
→ soft_threshold(candidate - original, learning_rate * beta)
→ adv_new = original + sparse_delta
→ y_new = adv_new + momentum * (adv_new - adv_old)
~~~

---

## 8. 非目标完整调用

~~~python
config = EADConfig(
    beta=0.01,
    learning_rate=0.01,
    confidence=0.0,
    initial_const=0.001,
    binary_search_steps=9,
    max_iterations=500,
    targeted=False,
)

adv_images, report = elastic_net_attack(
    model=model,
    original_images=images.to(device),
    attack_labels=true_labels.to(device),
    config=config,
)

print("Success:", report["success"])
print("Predictions:", report["predictions"])
print("L0:", report["l0"])
print("L1:", report["l1"])
print("L2:", report["l2"])
print("Elastic:", report["elastic"])
~~~

---

## 9. 目标攻击完整调用

~~~python
target_labels = (true_labels + 1) % num_classes

config = EADConfig(
    beta=0.01,
    learning_rate=0.01,
    confidence=0.0,
    initial_const=0.001,
    binary_search_steps=9,
    max_iterations=500,
    targeted=True,
)

adv_images, report = elastic_net_attack(
    model=model,
    original_images=images.to(device),
    attack_labels=target_labels.to(device),
    config=config,
    require_confidence_margin=False,
)
~~~

---

## 10. 只攻击原本正确的样本

~~~python
with torch.no_grad():
    clean_logits = model(images)
    clean_predictions = clean_logits.argmax(dim=1)

correct_mask = clean_predictions.eq(true_labels)
attack_images = images[correct_mask]
attack_labels = true_labels[correct_mask]
~~~

~~~python
attack_success_rate = (
    report["success"].float().mean().item()
)
~~~

分母必须是实际参与攻击的原始正确样本。

---

## 11. 二分搜索块

~~~python
lower, upper, const = update_binary_search_bounds(
    lower_bound=lower,
    upper_bound=upper,
    const=const,
    success_mask=success_mask,
    growth=10.0,
)
~~~

~~~text
成功：upper = min(upper, c)，尝试更小 c
失败：lower = max(lower, c)，需要更大 c
上下界有限：c = (lower + upper) / 2
尚无成功上界：c = c * 10
~~~

---

## 12. 高频填空代码

~~~python
# 输入梯度，不是模型参数梯度
y = y.detach().requires_grad_(True)
grad = torch.autograd.grad(loss.sum(), y)[0]

# 距离
l2_squared = torch.sum(
    (adv - original) ** 2,
    dim=(1, 2, 3),
)
l1 = torch.sum(
    torch.abs(adv - original),
    dim=(1, 2, 3),
)
elastic = l2_squared + beta * l1

# 软阈值
delta = candidate - original
shrunk = torch.sign(delta) * torch.clamp(
    torch.abs(delta) - learning_rate * beta,
    min=0.0,
)

# 简化 FISTA 动量
momentum = iteration / (iteration + 3.0)
y_next = adv_next + momentum * (
    adv_next - adv_current
)
~~~

---

## 13. 考试前检查清单

~~~text
[ ] 模型输出是 logits，没有提前做 Softmax
[ ] model.eval() 已调用
[ ] targeted / untargeted 标签语义正确
[ ] smooth loss 中没有重复加入 L1
[ ] threshold = learning_rate * beta
[ ] 软阈值作用于 candidate - original
[ ] 软阈值后加回 original 并裁剪
[ ] 距离计算保留 batch 维
[ ] 每个样本独立维护 c
[ ] 最终显式检查 argmax
[ ] 需要 kappa 时检查 margin
[ ] 保存历史最佳成功样本
~~~

---

## 14. 任意 Challenge 都能复用的适配代码块

这一节不提供固定 solver。每道题先复制需要的代码块，再替换 `TODO`。

### 14.1 题目契约摘录块

~~~python
# TODO 1：数据集形状与通道
IMAGE_SIZE = (28, 28)
CHANNELS = 1

# TODO 2：服务器字段
IMAGE_KEY = "image_b64"
LABEL_KEY = "original_label"
TARGET_KEY = "target_class"
BUDGET_KEY = "l0_budget"

# TODO 3：接口路径
CHALLENGE_PATH = "/challenge"
WEIGHTS_PATH = "/weights"
SUBMIT_PATH = "/submit"
~~~

先集中修改这些常量，避免字段名散落在整个答案中。

### 14.2 通用 HTTP 块

~~~python
import requests

def get_json(host: str, path: str) -> dict:
    response = requests.get(f"{host.rstrip('/')}{path}", timeout=30)
    response.raise_for_status()
    return response.json()

def post_json(host: str, path: str, body: dict) -> dict:
    response = requests.post(
        f"{host.rstrip('/')}{path}", json=body, timeout=60
    )
    if not response.ok:
        print("Server response:", response.text)
    response.raise_for_status()
    return response.json()
~~~

### 14.3 灰度与 RGB PNG/base64 块

~~~python
import base64
import io
import numpy as np
from PIL import Image

def decode_png(encoded: str, mode: str = "L") -> np.ndarray:
    image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert(mode)
    array = np.asarray(image, dtype=np.float32) / 255.0
    if mode == "L":
        return array[None, None, ...]          # (1,1,H,W)
    return np.transpose(array, (2, 0, 1))[None, ...]  # (1,3,H,W)

def encode_png(x4d: np.ndarray, mode: str = "L") -> str:
    if mode == "L":
        array = x4d[0, 0]
    else:
        array = np.transpose(x4d[0], (1, 2, 0))
    x255 = np.clip(np.rint(array * 255.0), 0, 255).astype(np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(x255, mode=mode).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
~~~

### 14.4 归一化模型包装块

~~~python
import torch
from torch import nn

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

# MNIST 示例：PixelSpaceModel(base_model, [0.1307], [0.3081])
# CIFAR-10 示例：PixelSpaceModel(
#     base_model,
#     [0.4914, 0.4822, 0.4465],
#     [0.2470, 0.2435, 0.2616],
# )
~~~

攻击函数从此只接收像素空间 `[0,1]`，不用在每一轮手动处理归一化。

### 14.5 EAD 调用块

~~~python
from ead_exam_template import EADConfig, elastic_net_attack

config = EADConfig(
    targeted=True,                 # TODO：非目标攻击改为 False
    beta=0.01,
    learning_rate=0.01,
    initial_const=0.001,
    binary_search_steps=9,
    max_iterations=500,
    confidence=0.0,
)

# targeted=True 时 attack_labels 是目标类；False 时是原始类。
attack_labels = torch.tensor([target_class], device=x.device)
x_adv, report = elastic_net_attack(
    pixel_model,
    x,
    attack_labels,
    config=config,
)
~~~

### 14.6 JSMA 调用块

~~~python
from jsma_exam_template import JSMAConfig, jsma_targeted

config = JSMAConfig(
    theta=1.0,        # CIFAR 可从更小值如 0.05、0.1 开始
    max_iterations=250,
    pair_size=2,
    top_k=128,
)

x_adv, report = jsma_targeted(
    pixel_model,
    x,
    target_class=target_class,
    l0_budget=l0_budget,
    config=config,
)
~~~

### 14.7 通用距离与成功验证块

~~~python
def attack_metrics(model, original, candidate, label, target=None, tol=1e-6):
    with torch.no_grad():
        prediction = int(model(candidate).argmax(dim=1).item())
    delta = candidate - original
    changed_coordinates = torch.abs(delta) > tol
    changed_spatial = torch.any(changed_coordinates, dim=1)
    return {
        "prediction": prediction,
        "success": prediction == target if target is not None else prediction != label,
        "l0_coordinates": int(changed_coordinates.sum()),
        "l0_spatial": int(changed_spatial.sum()),
        "l1": float(delta.abs().sum()),
        "l2": float(delta.flatten().norm(p=2)),
        "l2_squared": float(delta.square().sum()),
        "linf": float(delta.abs().max()),
    }
~~~

### 14.8 PNG 回环块

~~~python
# 服务器接收 PNG 时，必须验证服务器实际会看到的量化图片。
encoded = encode_png(x_adv.detach().cpu().numpy(), mode="L")  # TODO: RGB 改为 mode="RGB"
x_submitted = torch.from_numpy(decode_png(encoded, mode="L")).to(x.device)
metrics = attack_metrics(
    pixel_model, x, x_submitted, label=original_label, target=target_class
)
assert metrics["success"], metrics
assert metrics["l0_spatial"] <= l0_budget, metrics
~~~

### 14.9 模型与权重一致性块

~~~python
checkpoint = torch.load(weights_path, map_location=device, weights_only=True)
state_dict = checkpoint.get("state_dict", checkpoint)
base_model.load_state_dict(state_dict, strict=True)
pixel_model.eval()

with torch.no_grad():
    clean_prediction = int(pixel_model(x).argmax(dim=1).item())
assert clean_prediction == original_label, (
    clean_prediction,
    original_label,
    "检查模型结构、权重、通道顺序和 normalization",
)
~~~

---

## 15. Skill Assessment 拼装骨架

Assessment 常见变化是“一次返回多张图片，并为每张指定方法”。不重写攻击算法，只写适配层：

~~~python
adversarial_by_id = {}
method_by_id = {}

for item in challenge_payload["items"]:          # TODO：替换列表字段
    sample_id = int(item["sample_id"])
    required = item["required_method"].lower()
    x = torch.from_numpy(decode_png(item["image_b64"], mode="RGB")).to(device)
    target = int(item["target"])

    if required == "ead":
        candidate, _ = elastic_net_attack(
            pixel_model,
            x,
            torch.tensor([target], device=device),
            config=ead_config,
        )
        method_used = "ead"
    elif required in {"jacobian", "jsma"}:
        candidate, _ = jsma_targeted(
            pixel_model,
            x,
            target_class=target,
            l0_budget=jsma_budget,
            config=jsma_config,
        )
        method_used = "jacobian"                 # TODO：按接口要求命名
    else:
        raise ValueError(f"Unknown required method: {required}")

    # TODO：在这里做 PNG 回环与成功/预算断言
    adversarial_by_id[sample_id] = candidate.detach().cpu().numpy()
    method_by_id[sample_id] = method_used

submission = {
    "items": [
        {
            "sample_id": sample_id,
            "method": method_by_id[sample_id],
            "image_b64": encode_png(adversarial_by_id[sample_id], mode="RGB"),
        }
        for sample_id in adversarial_by_id
    ]
}
~~~

考试时真正需要从头写的通常只有四类适配内容：

~~~text
1. 题目给定的模型结构
2. challenge JSON 字段映射
3. 权重下载与 state_dict 提取
4. submit JSON 字段映射
~~~

EAD、FISTA、Jacobian、Saliency、距离统计和 PNG 工具均直接从本代码库复制。

---

## 16. 新练习题的收录格式

以后收到新的练习题或 Skill Assessment，只追加“与现有积木不同的部分”：

~~~text
题型：
新增接口字段：
新增模型结构：
需要替换的 TODO：
新增约束或判定：
可复用代码块：
最小自测：
易错点：
~~~

不再保存绑定某个临时 IP、动态 Flag 或单一样本的一次性完整 solver。
