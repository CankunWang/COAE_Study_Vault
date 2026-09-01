"""Reusable EAD/FISTA exam template for authorized local model testing."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor, nn


def set_reproducibility(seed: int = 1337) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


@dataclass
class EADConfig:
    beta: float = 0.01
    learning_rate: float = 0.01
    confidence: float = 0.0
    initial_const: float = 0.001
    binary_search_steps: int = 9
    max_iterations: int = 500
    targeted: bool = False
    clip_min: float = 0.0
    clip_max: float = 1.0
    l0_tolerance: float = 1e-6
    const_growth: float = 10.0


def to_onehot(labels: Tensor, num_classes: int) -> Tensor:
    return F.one_hot(labels.long(), num_classes=num_classes).float()


def _feature_dims(tensor: Tensor) -> Tuple[int, ...]:
    if tensor.ndim < 2:
        raise ValueError("Expected a batched tensor.")
    return tuple(range(1, tensor.ndim))


def compute_distances(
    adv_images: Tensor,
    original_images: Tensor,
    beta: float,
    tolerance: float = 1e-6,
) -> Dict[str, Tensor]:
    """Return per-example L0, L1, L2, squared L2, and elastic cost."""
    if adv_images.shape != original_images.shape:
        raise ValueError("Adversarial and original shapes must match.")
    delta = adv_images - original_images
    dims = _feature_dims(delta)
    l0 = torch.sum(torch.abs(delta) > tolerance, dim=dims)
    l1 = torch.sum(torch.abs(delta), dim=dims)
    l2_squared = torch.sum(delta.square(), dim=dims)
    l2 = torch.sqrt(l2_squared.clamp_min(0.0))
    return {
        "l0": l0,
        "l1": l1,
        "l2": l2,
        "l2_squared": l2_squared,
        "elastic": l2_squared + beta * l1,
    }


def count_changed_spatial_pixels(
    adv_images: Tensor,
    original_images: Tensor,
    tolerance: float = 1e-6,
) -> Tensor:
    if adv_images.ndim != 4:
        raise ValueError("Expected shape (B, C, H, W).")
    changed = torch.abs(adv_images - original_images) > tolerance
    return torch.any(changed, dim=1).sum(dim=(1, 2))


def extract_selected_and_other_logits(
    logits: Tensor,
    selected_onehot: Tensor,
) -> Tuple[Tensor, Tensor]:
    if logits.shape != selected_onehot.shape:
        raise ValueError("Logits and one-hot labels must have equal shape.")
    selected = torch.sum(selected_onehot * logits, dim=1)
    other = logits.masked_fill(
        selected_onehot.bool(),
        float("-inf"),
    ).max(dim=1).values
    return selected, other


def compute_adversarial_loss(
    logits: Tensor,
    selected_onehot: Tensor,
    confidence: float = 0.0,
    targeted: bool = False,
) -> Tensor:
    """
    Untargeted: max(Z_real - max_other + kappa, 0).
    Targeted: max(max_other - Z_target + kappa, 0).
    """
    selected, other = extract_selected_and_other_logits(
        logits,
        selected_onehot,
    )
    margin = (
        other - selected + confidence
        if targeted
        else selected - other + confidence
    )
    return torch.clamp(margin, min=0.0)


def check_attack_success(
    logits: Tensor,
    attack_labels: Tensor,
    targeted: bool = False,
) -> Tensor:
    predictions = logits.argmax(dim=1)
    return (
        predictions.eq(attack_labels)
        if targeted
        else predictions.ne(attack_labels)
    )


def check_margin_success(
    logits: Tensor,
    selected_onehot: Tensor,
    confidence: float = 0.0,
    targeted: bool = False,
) -> Tensor:
    selected, other = extract_selected_and_other_logits(
        logits,
        selected_onehot,
    )
    return (
        selected >= other + confidence
        if targeted
        else other >= selected + confidence
    )


def soft_threshold(values: Tensor, threshold: float) -> Tensor:
    """Element-wise L1 proximal operator."""
    if threshold < 0:
        raise ValueError("Threshold must be non-negative.")
    return torch.sign(values) * torch.clamp(
        torch.abs(values) - threshold,
        min=0.0,
    )


def apply_shrinkage_thresholding(
    candidate_images: Tensor,
    original_images: Tensor,
    threshold: float,
    clip_min: float = 0.0,
    clip_max: float = 1.0,
) -> Tensor:
    candidate_delta = candidate_images - original_images
    sparse_delta = soft_threshold(candidate_delta, threshold)
    return torch.clamp(
        original_images + sparse_delta,
        min=clip_min,
        max=clip_max,
    )


def compute_fista_momentum(iteration: int) -> float:
    if iteration < 0:
        raise ValueError("Iteration must be non-negative.")
    return iteration / (iteration + 3.0)


def update_standard_fista_momentum(
    t_current: float,
) -> Tuple[float, float]:
    t_next = (
        1.0 + (1.0 + 4.0 * t_current * t_current) ** 0.5
    ) / 2.0
    return t_next, (t_current - 1.0) / t_next


def compute_total_loss(
    adv_images: Tensor,
    original_images: Tensor,
    selected_onehot: Tensor,
    const: Tensor,
    model: nn.Module,
    beta: float,
    confidence: float = 0.0,
    targeted: bool = False,
) -> Tuple[Tensor, Tensor, Dict[str, Tensor], Tensor]:
    """Smooth loss only; L1 is handled by the proximal step."""
    logits = model(adv_images)
    adversarial_loss = compute_adversarial_loss(
        logits,
        selected_onehot,
        confidence,
        targeted,
    )
    metrics = compute_distances(
        adv_images,
        original_images,
        beta,
    )
    smooth_loss = (
        const * adversarial_loss
        + metrics["l2_squared"]
    )
    return smooth_loss, adversarial_loss, metrics, logits


def fista_step(
    adv_images: Tensor,
    y_momentum: Tensor,
    original_images: Tensor,
    selected_onehot: Tensor,
    const: Tensor,
    model: nn.Module,
    beta: float,
    learning_rate: float,
    confidence: float,
    iteration: int,
    targeted: bool = False,
    clip_min: float = 0.0,
    clip_max: float = 1.0,
) -> Tuple[Tensor, Tensor, Dict[str, Tensor]]:
    """Perform one simplified FISTA step."""
    y_current = y_momentum.detach().requires_grad_(True)
    smooth_loss, adversarial_loss, metrics, logits = (
        compute_total_loss(
            y_current,
            original_images,
            selected_onehot,
            const,
            model,
            beta,
            confidence,
            targeted,
        )
    )
    gradient = torch.autograd.grad(
        smooth_loss.sum(),
        y_current,
    )[0]
    candidate = y_current - learning_rate * gradient
    adv_new = apply_shrinkage_thresholding(
        candidate,
        original_images,
        learning_rate * beta,
        clip_min,
        clip_max,
    )
    momentum = compute_fista_momentum(iteration)
    y_new = adv_new + momentum * (adv_new - adv_images)
    flat_gradient = gradient.detach().flatten(1)
    diagnostics = {
        "smooth_loss": smooth_loss.detach(),
        "adversarial_loss": adversarial_loss.detach(),
        "gradient_abs_mean": flat_gradient.abs().mean(1),
        "gradient_abs_max": flat_gradient.abs().max(1).values,
        "elastic": metrics["elastic"].detach(),
        "predictions": logits.detach().argmax(dim=1),
    }
    return adv_new.detach(), y_new.detach(), diagnostics


def update_binary_search_bounds(
    lower_bound: Tensor,
    upper_bound: Tensor,
    const: Tensor,
    success_mask: Tensor,
    growth: float = 10.0,
) -> Tuple[Tensor, Tensor, Tensor]:
    """Update an independent c interval for every batch example."""
    lower = torch.where(
        success_mask,
        lower_bound,
        torch.maximum(lower_bound, const),
    )
    upper = torch.where(
        success_mask,
        torch.minimum(upper_bound, const),
        upper_bound,
    )
    finite = torch.isfinite(upper)
    next_const = torch.where(
        finite,
        (lower + upper) / 2.0,
        const * growth,
    )
    return lower, upper, next_const


def _update_best(
    best_adv: Tensor,
    best_elastic: Tensor,
    candidate_adv: Tensor,
    candidate_elastic: Tensor,
    success: Tensor,
) -> Tuple[Tensor, Tensor]:
    improved = success & (candidate_elastic < best_elastic)
    if improved.any():
        best_adv = best_adv.clone()
        best_elastic = best_elastic.clone()
        best_adv[improved] = candidate_adv[improved]
        best_elastic[improved] = candidate_elastic[improved]
    return best_adv, best_elastic


def elastic_net_attack(
    model: nn.Module,
    original_images: Tensor,
    attack_labels: Tensor,
    config: Optional[EADConfig] = None,
    require_confidence_margin: bool = False,
) -> Tuple[Tensor, Dict[str, Tensor]]:
    """
    Complete batched EAD.

    Untargeted: attack_labels are original labels.
    Targeted: attack_labels are desired target labels.
    The model must return raw logits and accept pixel-space inputs.
    """
    cfg = config or EADConfig()
    batch_size = original_images.shape[0]
    device = original_images.device
    if attack_labels.shape != (batch_size,):
        raise ValueError("attack_labels must have shape (B,).")

    model.eval()
    parameters = list(model.parameters())
    old_flags = [p.requires_grad for p in parameters]
    for parameter in parameters:
        parameter.requires_grad_(False)

    try:
        with torch.no_grad():
            initial_logits = model(original_images)
        selected_onehot = to_onehot(
            attack_labels,
            initial_logits.shape[1],
        ).to(device=device, dtype=original_images.dtype)

        lower = torch.zeros(
            batch_size,
            device=device,
            dtype=original_images.dtype,
        )
        upper = torch.full_like(lower, float("inf"))
        const = torch.full_like(lower, cfg.initial_const)
        best_adv = original_images.detach().clone()
        best_elastic = torch.full_like(lower, float("inf"))
        ever_success = torch.zeros(
            batch_size,
            device=device,
            dtype=torch.bool,
        )

        for _ in range(cfg.binary_search_steps):
            adv = original_images.detach().clone()
            y = original_images.detach().clone()
            step_success = torch.zeros_like(ever_success)

            for iteration in range(cfg.max_iterations):
                adv, y, _ = fista_step(
                    adv,
                    y,
                    original_images,
                    selected_onehot,
                    const,
                    model,
                    cfg.beta,
                    cfg.learning_rate,
                    cfg.confidence,
                    iteration,
                    cfg.targeted,
                    cfg.clip_min,
                    cfg.clip_max,
                )
                with torch.no_grad():
                    logits = model(adv)
                    success = check_attack_success(
                        logits,
                        attack_labels,
                        cfg.targeted,
                    )
                    if require_confidence_margin:
                        success &= check_margin_success(
                            logits,
                            selected_onehot,
                            cfg.confidence,
                            cfg.targeted,
                        )
                    metrics = compute_distances(
                        adv,
                        original_images,
                        cfg.beta,
                        cfg.l0_tolerance,
                    )
                    step_success |= success
                    ever_success |= success
                    best_adv, best_elastic = _update_best(
                        best_adv,
                        best_elastic,
                        adv,
                        metrics["elastic"],
                        success,
                    )

            lower, upper, const = update_binary_search_bounds(
                lower,
                upper,
                const,
                step_success,
                cfg.const_growth,
            )

        final_metrics = compute_distances(
            best_adv,
            original_images,
            cfg.beta,
            cfg.l0_tolerance,
        )
        with torch.no_grad():
            predictions = model(best_adv).argmax(dim=1)
        report = {
            "success": ever_success,
            "predictions": predictions,
            "best_elastic": best_elastic,
            "final_const": const,
            "lower_bound": lower,
            "upper_bound": upper,
            **final_metrics,
        }
        return best_adv, report
    finally:
        for parameter, old_flag in zip(parameters, old_flags):
            parameter.requires_grad_(old_flag)


def run_basic_self_tests() -> None:
    """Fast tests for the most common exam implementation errors."""
    values = torch.tensor([0.12, 0.08, -0.25])
    expected = torch.tensor([0.02, 0.0, -0.15])
    assert torch.allclose(
        soft_threshold(values, 0.1),
        expected,
        atol=1e-6,
    )

    original = torch.zeros(4, 1, 3, 3)
    adversarial = original.clone()
    adversarial[:, :, 0, 0] = 0.2
    metrics = compute_distances(
        adversarial,
        original,
        beta=0.1,
    )
    assert all(value.shape == (4,) for value in metrics.values())


if __name__ == "__main__":
    run_basic_self_tests()
    print("EAD template basic tests passed.")

