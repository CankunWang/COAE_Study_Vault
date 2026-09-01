"""Reusable FGSM, I-FGSM/BIM, and DeepFool blocks for authorized exercises.

All functions expect a model that accepts pixel-space tensors in [0, 1] and
returns raw logits. Put normalization inside a model wrapper when necessary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import torch
from torch import Tensor, nn
import torch.nn.functional as F


@dataclass
class IterativeAttackConfig:
    epsilon: float = 8.0 / 255.0
    step_size: float = 2.0 / 255.0
    max_iterations: int = 20
    clip_min: float = 0.0
    clip_max: float = 1.0


class PixelSpaceModel(nn.Module):
    """Wrap a normalized-input classifier with a pixel-space interface."""

    def __init__(self, base_model: nn.Module, mean: list[float], std: list[float]):
        super().__init__()
        self.base_model = base_model
        self.register_buffer(
            "mean", torch.tensor(mean, dtype=torch.float32)[None, :, None, None]
        )
        self.register_buffer(
            "std", torch.tensor(std, dtype=torch.float32)[None, :, None, None]
        )

    def forward(self, x01: Tensor) -> Tensor:
        return self.base_model((x01 - self.mean) / self.std)


def fgsm(
    model: nn.Module,
    images: Tensor,
    labels: Tensor,
    epsilon: float,
    targeted: bool = False,
    clip_min: float = 0.0,
    clip_max: float = 1.0,
) -> Tensor:
    """Batched FGSM in pixel space under an L-infinity budget."""
    x = images.detach().clone().requires_grad_(True)
    loss = F.cross_entropy(model(x), labels)
    gradient = torch.autograd.grad(loss, x)[0]
    direction = -1.0 if targeted else 1.0
    return torch.clamp(
        x + direction * epsilon * gradient.sign(), clip_min, clip_max
    ).detach()


def iterative_fgsm(
    model: nn.Module,
    images: Tensor,
    labels: Tensor,
    config: IterativeAttackConfig | None = None,
    targeted: bool = False,
) -> Tensor:
    """Batched I-FGSM/BIM with projection around the clean image."""
    cfg = config or IterativeAttackConfig()
    original = images.detach().clone()
    adversarial = original.clone()
    direction = -1.0 if targeted else 1.0

    for _ in range(cfg.max_iterations):
        current = adversarial.detach().requires_grad_(True)
        loss = F.cross_entropy(model(current), labels)
        gradient = torch.autograd.grad(loss, current)[0]
        candidate = current + direction * cfg.step_size * gradient.sign()
        delta = torch.clamp(
            candidate - original, -cfg.epsilon, cfg.epsilon
        )
        adversarial = torch.clamp(
            original + delta, cfg.clip_min, cfg.clip_max
        ).detach()
    return adversarial


def deepfool_targeted(
    model: nn.Module,
    image: Tensor,
    target_class: int,
    overshoot: float = 0.02,
    max_iterations: int = 100,
    clip_min: float = 0.0,
    clip_max: float = 1.0,
) -> Tuple[Tensor, Dict[str, int | float | bool]]:
    """Single-image targeted DeepFool-style local boundary projection."""
    if image.ndim != 4 or image.shape[0] != 1:
        raise ValueError("Expected one image with shape (1,C,H,W).")
    original = image.detach().clone()
    perturbation = torch.zeros_like(original)
    iterations = 0

    for iteration in range(max_iterations):
        iterations = iteration + 1
        current = torch.clamp(
            original + (1.0 + overshoot) * perturbation,
            clip_min,
            clip_max,
        ).detach().requires_grad_(True)
        logits = model(current)
        prediction = int(logits.argmax(dim=1).item())
        if prediction == target_class:
            break

        gradient_current = torch.autograd.grad(
            logits[0, prediction], current, retain_graph=True
        )[0]
        gradient_target = torch.autograd.grad(
            logits[0, target_class], current
        )[0]
        normal = gradient_target - gradient_current
        logit_gap = logits[0, target_class] - logits[0, prediction]
        denominator = normal.flatten().square().sum().clamp_min(1e-12)
        step = (logit_gap.abs() / denominator + 1e-6) * normal
        perturbation = perturbation + step.detach()

    adversarial = torch.clamp(
        original + (1.0 + overshoot) * perturbation, clip_min, clip_max
    ).detach()
    with torch.no_grad():
        prediction = int(model(adversarial).argmax(dim=1).item())
    report: Dict[str, int | float | bool] = {
        "success": prediction == target_class,
        "prediction": prediction,
        "target": target_class,
        "iterations": iterations,
        "l2_pixel": float((adversarial - original).flatten().norm(p=2)),
    }
    return adversarial, report


def deepfool_untargeted(
    model: nn.Module,
    image: Tensor,
    num_classes: int | None = None,
    overshoot: float = 0.02,
    max_iterations: int = 50,
    clip_min: float = 0.0,
    clip_max: float = 1.0,
) -> Tuple[Tensor, Dict[str, int | float | bool]]:
    """Single-image untargeted DeepFool using the nearest local class plane."""
    if image.ndim != 4 or image.shape[0] != 1:
        raise ValueError("Expected one image with shape (1,C,H,W).")
    original = image.detach().clone()
    adversarial = original.clone()
    with torch.no_grad():
        original_prediction = int(model(original).argmax(dim=1).item())
    iterations = 0

    for iteration in range(max_iterations):
        iterations = iteration + 1
        current = adversarial.detach().requires_grad_(True)
        logits = model(current)
        prediction = int(logits.argmax(dim=1).item())
        if prediction != original_prediction:
            break

        class_count = logits.shape[1] if num_classes is None else num_classes
        gradient_reference = torch.autograd.grad(
            logits[0, prediction], current, retain_graph=True
        )[0]
        best_distance = float("inf")
        best_normal = None
        best_gap = None

        for class_index in range(class_count):
            if class_index == prediction:
                continue
            gradient_class = torch.autograd.grad(
                logits[0, class_index], current, retain_graph=True
            )[0]
            normal = gradient_class - gradient_reference
            gap = logits[0, class_index] - logits[0, prediction]
            distance = gap.abs() / normal.flatten().norm(p=2).clamp_min(1e-12)
            if float(distance) < best_distance:
                best_distance = float(distance)
                best_normal = normal
                best_gap = gap

        if best_normal is None or best_gap is None:
            break
        denominator = best_normal.flatten().square().sum().clamp_min(1e-12)
        step = (best_gap.abs() / denominator + 1e-6) * best_normal
        adversarial = torch.clamp(
            current + (1.0 + overshoot) * step,
            clip_min,
            clip_max,
        ).detach()

    with torch.no_grad():
        prediction = int(model(adversarial).argmax(dim=1).item())
    report: Dict[str, int | float | bool] = {
        "success": prediction != original_prediction,
        "original_prediction": original_prediction,
        "prediction": prediction,
        "iterations": iterations,
        "l2_pixel": float((adversarial - original).flatten().norm(p=2)),
    }
    return adversarial, report


def perturbation_metrics(adversarial: Tensor, original: Tensor) -> Dict[str, Tensor]:
    """Return per-example L0, L1, L2 and L-infinity in pixel space."""
    if adversarial.shape != original.shape:
        raise ValueError("Tensor shapes must match.")
    delta = adversarial - original
    dims = tuple(range(1, delta.ndim))
    return {
        "l0": (delta.abs() > 1e-6).sum(dim=dims),
        "l1": delta.abs().sum(dim=dims),
        "l2": delta.square().sum(dim=dims).sqrt(),
        "linf": delta.abs().amax(dim=dims),
    }


def run_basic_self_tests() -> None:
    model = nn.Sequential(nn.Flatten(), nn.Linear(4, 2, bias=False))
    with torch.no_grad():
        model[1].weight.copy_(torch.tensor([[1.0, 1.0, 0.0, 0.0], [-1.0, -1.0, 0.0, 0.0]]))
    images = torch.full((1, 1, 2, 2), 0.75)
    labels = torch.tensor([0])
    adversarial = fgsm(model, images, labels, epsilon=0.25)
    metrics = perturbation_metrics(adversarial, images)
    assert float(metrics["linf"][0]) <= 0.25 + 1e-6

    config = IterativeAttackConfig(epsilon=0.2, step_size=0.05, max_iterations=5)
    adversarial = iterative_fgsm(model, images, labels, config=config)
    metrics = perturbation_metrics(adversarial, images)
    assert float(metrics["linf"][0]) <= 0.2 + 1e-6

    boundary_model = nn.Sequential(nn.Flatten(), nn.Linear(1, 2))
    with torch.no_grad():
        boundary_model[1].weight.copy_(torch.tensor([[1.0], [-1.0]]))
        boundary_model[1].bias.copy_(torch.tensor([0.0, 1.0]))
    boundary_image = torch.tensor([[[[0.75]]]])
    _, targeted_report = deepfool_targeted(
        boundary_model, boundary_image, target_class=1, overshoot=0.05
    )
    _, untargeted_report = deepfool_untargeted(
        boundary_model, boundary_image, overshoot=0.05
    )
    assert bool(targeted_report["success"])
    assert bool(untargeted_report["success"])
    print("First-order evasion template self-tests passed.")


if __name__ == "__main__":
    run_basic_self_tests()
