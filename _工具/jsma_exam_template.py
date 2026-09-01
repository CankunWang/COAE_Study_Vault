"""Reusable JSMA template for authorized model robustness exercises.

The model passed to this module must accept pixel-space tensors in [0, 1] and
return raw logits. Wrap normalization inside the model when necessary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import torch
from torch import Tensor, nn


@dataclass
class JSMAConfig:
    theta: float = 1.0
    max_iterations: int = 250
    pair_size: int = 2
    top_k: int = 128
    clip_min: float = 0.0
    clip_max: float = 1.0
    tolerance: float = 1e-6


def count_changed_spatial_pixels(
    adversarial: Tensor,
    original: Tensor,
    tolerance: float = 1e-6,
) -> Tensor:
    """Count changed HxW positions; all channels at one position count once."""
    if adversarial.shape != original.shape or adversarial.ndim != 4:
        raise ValueError("Expected equal tensors with shape (B, C, H, W).")
    changed = torch.any(torch.abs(adversarial - original) > tolerance, dim=1)
    return changed.sum(dim=(1, 2))


def compute_jacobian(model: nn.Module, x01: Tensor) -> Tensor:
    """Return d(logit_k)/d(x_i), shaped (classes, C, H, W), for B=1."""
    if x01.ndim != 4 or x01.shape[0] != 1:
        raise ValueError("JSMA template expects one image with shape (1,C,H,W).")
    x = x01.detach().clone().requires_grad_(True)
    logits = model(x)
    if logits.ndim != 2 or logits.shape[0] != 1:
        raise ValueError("Model must return logits with shape (1,num_classes).")
    rows = []
    for class_index in range(logits.shape[1]):
        gradient = torch.autograd.grad(
            logits[0, class_index],
            x,
            retain_graph=class_index + 1 < logits.shape[1],
        )[0]
        rows.append(gradient[0])
    return torch.stack(rows, dim=0)


def spatial_saliency_terms(
    jacobian: Tensor,
    target_class: int,
) -> Tuple[Tensor, Tensor]:
    """Return target-gradient alpha and competitor-gradient beta per pixel."""
    if jacobian.ndim != 4:
        raise ValueError("Expected Jacobian shape (classes,C,H,W).")
    target_gradient = jacobian[target_class]
    other_gradient = jacobian.sum(dim=0) - target_gradient
    # RGB channels at one HxW position are one L0 feature in this template.
    alpha = target_gradient.sum(dim=0).flatten()
    beta = other_gradient.sum(dim=0).flatten()
    return alpha, beta


def saliency_scores(
    alpha: Tensor,
    beta: Tensor,
    search_space: Tensor,
) -> Tuple[Tensor, Tensor]:
    """Compute classical targeted JSMA scores for increase/decrease directions."""
    if alpha.shape != beta.shape or alpha.shape != search_space.shape:
        raise ValueError("alpha, beta, and search_space must have equal shapes.")
    increase = torch.zeros_like(alpha)
    decrease = torch.zeros_like(alpha)
    inc_mask = (alpha > 0) & (beta < 0) & search_space
    dec_mask = (alpha < 0) & (beta > 0) & search_space
    increase[inc_mask] = alpha[inc_mask] * (-beta[inc_mask])
    decrease[dec_mask] = (-alpha[dec_mask]) * beta[dec_mask]
    return increase, decrease


def select_single_feature(
    increase: Tensor,
    decrease: Tensor,
) -> Tuple[Tuple[int, ...], int, float]:
    """Return selected index tuple, direction (+1/-1), and score."""
    inc_score, inc_index = increase.max(dim=0)
    dec_score, dec_index = decrease.max(dim=0)
    if float(inc_score) <= 0.0 and float(dec_score) <= 0.0:
        return (), 0, 0.0
    if inc_score >= dec_score:
        return (int(inc_index),), 1, float(inc_score)
    return (int(dec_index),), -1, float(dec_score)


def select_feature_pair(
    alpha: Tensor,
    beta: Tensor,
    search_space: Tensor,
    top_k: int = 128,
) -> Tuple[Tuple[int, ...], int, float]:
    """Select a classical JSMA feature pair after a top-k prefilter."""
    valid = torch.nonzero(search_space, as_tuple=False).flatten()
    if valid.numel() < 2:
        return (), 0, 0.0
    if valid.numel() > top_k:
        preliminary = torch.abs(alpha[valid] * beta[valid])
        valid = valid[torch.topk(preliminary, k=top_k).indices]

    a = alpha[valid]
    b = beta[valid]
    alpha_pair = a[:, None] + a[None, :]
    beta_pair = b[:, None] + b[None, :]
    upper = torch.triu(
        torch.ones_like(alpha_pair, dtype=torch.bool), diagonal=1
    )

    inc_valid = (alpha_pair > 0) & (beta_pair < 0) & upper
    dec_valid = (alpha_pair < 0) & (beta_pair > 0) & upper
    inc_scores = torch.where(
        inc_valid, alpha_pair * (-beta_pair), torch.zeros_like(alpha_pair)
    )
    dec_scores = torch.where(
        dec_valid, (-alpha_pair) * beta_pair, torch.zeros_like(alpha_pair)
    )

    inc_score, inc_flat = inc_scores.flatten().max(dim=0)
    dec_score, dec_flat = dec_scores.flatten().max(dim=0)
    if float(inc_score) <= 0.0 and float(dec_score) <= 0.0:
        return (), 0, 0.0

    width = valid.numel()
    if inc_score >= dec_score:
        row, col = divmod(int(inc_flat), width)
        return (int(valid[row]), int(valid[col])), 1, float(inc_score)
    row, col = divmod(int(dec_flat), width)
    return (int(valid[row]), int(valid[col])), -1, float(dec_score)


def jsma_targeted(
    model: nn.Module,
    original: Tensor,
    target_class: int,
    l0_budget: int,
    config: JSMAConfig | None = None,
) -> Tuple[Tensor, Dict[str, object]]:
    """Run a targeted, single-image JSMA under a spatial-pixel L0 budget."""
    cfg = config or JSMAConfig()
    if original.ndim != 4 or original.shape[0] != 1:
        raise ValueError("Expected one image with shape (1,C,H,W).")
    if l0_budget < 1:
        raise ValueError("l0_budget must be positive.")
    if cfg.pair_size not in (1, 2):
        raise ValueError("pair_size must be 1 or 2.")

    model.eval()
    parameters = list(model.parameters())
    old_flags = [parameter.requires_grad for parameter in parameters]
    for parameter in parameters:
        parameter.requires_grad_(False)

    x_orig = original.detach().clone()
    x_adv = x_orig.clone()
    _, _, height, width = x_adv.shape
    search_space = torch.ones(height * width, dtype=torch.bool, device=x_adv.device)
    success = False
    iterations = 0

    try:
        for iteration in range(cfg.max_iterations):
            iterations = iteration + 1
            with torch.no_grad():
                prediction = int(model(x_adv).argmax(dim=1).item())
            if prediction == target_class:
                success = True
                break

            changed_map = torch.any(
                torch.abs(x_adv - x_orig) > cfg.tolerance, dim=1
            )[0].flatten()
            used = int(changed_map.sum().item())
            remaining = l0_budget - used
            if remaining <= 0 or not bool(search_space.any()):
                break

            jacobian = compute_jacobian(model, x_adv)
            alpha, beta = spatial_saliency_terms(jacobian, target_class)
            increase, decrease = saliency_scores(alpha, beta, search_space)
            if cfg.pair_size == 2 and remaining >= 2:
                indices, direction, score = select_feature_pair(
                    alpha, beta, search_space, cfg.top_k
                )
            else:
                indices, direction, score = select_single_feature(
                    increase, decrease
                )
            if not indices or score <= 0.0:
                break

            flat = x_adv[0].reshape(x_adv.shape[1], -1)
            for index in indices:
                before = flat[:, index].clone()
                flat[:, index] = torch.clamp(
                    flat[:, index] + direction * cfg.theta,
                    cfg.clip_min,
                    cfg.clip_max,
                )
                if torch.allclose(before, flat[:, index]):
                    search_space[index] = False
                elif bool(
                    torch.all(
                        (flat[:, index] <= cfg.clip_min + cfg.tolerance)
                        | (flat[:, index] >= cfg.clip_max - cfg.tolerance)
                    )
                ):
                    search_space[index] = False
            x_adv = flat.reshape_as(x_adv).detach()

        with torch.no_grad():
            prediction = int(model(x_adv).argmax(dim=1).item())
        success = prediction == target_class
        l0_used = int(
            count_changed_spatial_pixels(x_adv, x_orig, cfg.tolerance)[0].item()
        )
        report: Dict[str, object] = {
            "success": success,
            "prediction": prediction,
            "target": target_class,
            "l0_used": l0_used,
            "l0_budget": l0_budget,
            "iterations": iterations,
        }
        return x_adv.detach(), report
    finally:
        for parameter, old_flag in zip(parameters, old_flags):
            parameter.requires_grad_(old_flag)


def run_basic_self_tests() -> None:
    original = torch.zeros(1, 3, 2, 2)
    adversarial = original.clone()
    adversarial[0, :, 0, 0] = 0.5
    assert int(count_changed_spatial_pixels(adversarial, original)[0]) == 1

    alpha = torch.tensor([1.0, 2.0, -1.0])
    beta = torch.tensor([-1.0, -3.0, 2.0])
    space = torch.ones(3, dtype=torch.bool)
    inc, dec = saliency_scores(alpha, beta, space)
    assert float(inc[1]) == 6.0
    assert float(dec[2]) == 2.0
    assert select_single_feature(inc, dec)[1] == 1
    print("JSMA template self-tests passed.")


if __name__ == "__main__":
    run_basic_self_tests()
