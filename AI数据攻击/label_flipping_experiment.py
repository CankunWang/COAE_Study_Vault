"""完整的二分类标签翻转（Label Flipping）教学实验。

仅用于合成数据和授权测试。脚本不会读取或修改真实数据集。

依赖：
    python -m pip install numpy matplotlib seaborn scikit-learn

示例：
    python label_flipping_experiment.py
    python label_flipping_experiment.py --sampling independent --show
    python label_flipping_experiment.py --percentages 0 0.05 0.1 0.2 0.3 0.4 0.5
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.colors import ListedColormap
from sklearn.datasets import make_blobs
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    log_loss,
)
from sklearn.model_selection import train_test_split


SEED = 1337

# Plot colors
HTB_GREEN = "#9fef00"
NODE_BLACK = "#141d2b"
HACKER_GREY = "#a4b1cd"
WHITE = "#ffffff"
AZURE = "#0086ff"
NUGGET_YELLOW = "#ffaf00"
MALWARE_RED = "#ff3e3e"
VIVID_PURPLE = "#9f00ff"
AQUAMARINE = "#2ee7b6"

CLASS_CMAP = ListedColormap([AZURE, NUGGET_YELLOW])
BOUNDARY_COLORS = {
    0.00: HTB_GREEN,
    0.05: "#ffffff",
    0.10: AQUAMARINE,
    0.20: NUGGET_YELLOW,
    0.30: VIVID_PURPLE,
    0.40: AZURE,
    0.50: MALWARE_RED,
}


@dataclass
class ExperimentResult:
    """One trained model and its evaluation evidence."""

    percentage: float
    n_flipped: int
    accuracy: float
    log_loss: float
    model: LogisticRegression
    y_train_poisoned: np.ndarray
    flipped_indices: np.ndarray
    y_pred: np.ndarray
    y_probability: np.ndarray
    confusion: np.ndarray


def configure_plot_style() -> None:
    """Configure a consistent dark plotting theme."""
    plt.style.use("seaborn-v0_8-darkgrid")
    plt.rcParams.update(
        {
            "figure.facecolor": NODE_BLACK,
            "axes.facecolor": NODE_BLACK,
            "axes.edgecolor": HACKER_GREY,
            "axes.labelcolor": WHITE,
            "text.color": WHITE,
            "xtick.color": HACKER_GREY,
            "ytick.color": HACKER_GREY,
            "grid.color": HACKER_GREY,
            "grid.alpha": 0.1,
            "legend.facecolor": NODE_BLACK,
            "legend.edgecolor": HACKER_GREY,
            "legend.frameon": True,
            "legend.framealpha": 1.0,
            "legend.labelcolor": WHITE,
            "savefig.facecolor": NODE_BLACK,
            "savefig.bbox": "tight",
        }
    )


def validate_percentages(percentages: Iterable[float]) -> list[float]:
    """Validate, deduplicate, and sort poisoning percentages."""
    values = sorted(set(float(value) for value in percentages))
    if not values:
        raise ValueError("At least one poisoning percentage is required.")
    if any(value < 0 or value > 0.5 for value in values):
        raise ValueError("Percentages must be between 0.0 and 0.5.")
    if 0.0 not in values:
        values.insert(0, 0.0)
    return values


def generate_dataset(
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate and split the two-dimensional binary dataset."""
    x, y = make_blobs(
        n_samples=1000,
        centers=[(0, 5), (5, 0)],
        n_features=2,
        cluster_std=1.25,
        random_state=seed,
    )

    return train_test_split(
        x,
        y,
        test_size=0.30,
        random_state=seed,
    )


def build_nested_flip_order(n_labels: int, seed: int) -> np.ndarray:
    """Return one fixed permutation for cumulative/nested experiments."""
    rng = np.random.default_rng(seed)
    return rng.permutation(n_labels)


def flip_binary_labels(
    y_clean: np.ndarray,
    percentage: float,
    *,
    seed: int,
    flip_order: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Flip a fraction of labels in a copy of a {0, 1} label array.

    When flip_order is supplied, the first N indices are selected. Reusing the
    same order across percentages produces nested sets: the 20% set contains
    every point from the 10% set. Without flip_order, an independent seeded
    sample is used for this percentage.
    """
    labels = np.asarray(y_clean)
    if labels.ndim != 1:
        raise ValueError("y_clean must be a one-dimensional array.")
    if not np.array_equal(np.unique(labels), np.array([0, 1])):
        raise ValueError("This experiment requires binary labels {0, 1}.")
    if not 0 <= percentage <= 0.5:
        raise ValueError("percentage must be between 0.0 and 0.5.")

    n_flipped = int(len(labels) * percentage)
    poisoned = labels.copy()

    if flip_order is not None:
        if len(flip_order) != len(labels):
            raise ValueError("flip_order length must match y_clean length.")
        flipped_indices = np.asarray(flip_order[:n_flipped], dtype=int)
    else:
        # Include the percentage in the seed so each independent experiment is
        # reproducible while selecting a different subset.
        percentage_seed = seed + int(round(percentage * 10_000))
        rng = np.random.default_rng(percentage_seed)
        flipped_indices = rng.choice(
            len(labels),
            size=n_flipped,
            replace=False,
        )

    poisoned[flipped_indices] = 1 - poisoned[flipped_indices]

    # Evidence-preserving invariants.
    unchanged_mask = np.ones(len(labels), dtype=bool)
    unchanged_mask[flipped_indices] = False
    assert np.array_equal(poisoned[unchanged_mask], labels[unchanged_mask])
    assert np.array_equal(
        poisoned[flipped_indices],
        1 - labels[flipped_indices],
    )

    return poisoned, flipped_indices


def train_and_evaluate(
    x_train: np.ndarray,
    y_train_poisoned: np.ndarray,
    x_test: np.ndarray,
    y_test_clean: np.ndarray,
    percentage: float,
    flipped_indices: np.ndarray,
    seed: int,
) -> ExperimentResult:
    """Train on poisoned labels and evaluate only against clean test labels."""
    model = LogisticRegression(random_state=seed, max_iter=1000)
    model.fit(x_train, y_train_poisoned)

    y_pred = model.predict(x_test)
    y_probability = model.predict_proba(x_test)[:, 1]

    return ExperimentResult(
        percentage=percentage,
        n_flipped=len(flipped_indices),
        accuracy=accuracy_score(y_test_clean, y_pred),
        log_loss=log_loss(y_test_clean, y_probability),
        model=model,
        y_train_poisoned=y_train_poisoned.copy(),
        flipped_indices=flipped_indices.copy(),
        y_pred=y_pred,
        y_probability=y_probability,
        confusion=confusion_matrix(y_test_clean, y_pred, labels=[0, 1]),
    )


def save_figure(path: Path, show: bool) -> None:
    """Save the active figure, optionally display it, then release memory."""
    plt.savefig(path, dpi=180)
    if show:
        plt.show()
    plt.close()


def plot_clean_data(
    x_train: np.ndarray,
    y_train: np.ndarray,
    output_dir: Path,
    show: bool,
) -> None:
    """Plot the original clean training distribution."""
    plt.figure(figsize=(12, 6))
    plt.scatter(
        x_train[:, 0],
        x_train[:, 1],
        c=y_train,
        cmap=CLASS_CMAP,
        edgecolors=NODE_BLACK,
        s=50,
        alpha=0.8,
    )
    plt.title("Original Training Data Distribution", fontsize=16, color=HTB_GREEN)
    plt.xlabel("Sentiment Feature 1")
    plt.ylabel("Sentiment Feature 2")
    save_figure(output_dir / "01_clean_training_data.png", show)


def plot_poisoned_data(
    x_train: np.ndarray,
    y_clean: np.ndarray,
    result: ExperimentResult,
    output_dir: Path,
    show: bool,
) -> None:
    """Plot unchanged and flipped training points."""
    unchanged_mask = np.ones(len(y_clean), dtype=bool)
    unchanged_mask[result.flipped_indices] = False

    plt.figure(figsize=(12, 6))
    plt.scatter(
        x_train[unchanged_mask, 0],
        x_train[unchanged_mask, 1],
        c=result.y_train_poisoned[unchanged_mask],
        cmap=CLASS_CMAP,
        edgecolors=NODE_BLACK,
        s=50,
        alpha=0.65,
        label="Unchanged label",
    )

    if result.n_flipped:
        plt.scatter(
            x_train[result.flipped_indices, 0],
            x_train[result.flipped_indices, 1],
            c=result.y_train_poisoned[result.flipped_indices],
            cmap=CLASS_CMAP,
            edgecolors=MALWARE_RED,
            linewidths=1.5,
            marker="X",
            s=100,
            alpha=0.9,
            label="Flipped label",
        )

    percent = result.percentage * 100
    plt.title(
        f"Training Data with {percent:.0f}% Flipped Labels",
        fontsize=16,
        color=HTB_GREEN,
    )
    plt.xlabel("Sentiment Feature 1")
    plt.ylabel("Sentiment Feature 2")
    plt.legend()
    save_figure(
        output_dir / f"poisoned_data_{percent:02.0f}_percent.png",
        show,
    )


def create_mesh(x_train: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create one common mesh for all boundary comparisons."""
    step = 0.02
    x_min, x_max = x_train[:, 0].min() - 1, x_train[:, 0].max() + 1
    y_min, y_max = x_train[:, 1].min() - 1, x_train[:, 1].max() + 1
    xx, yy = np.meshgrid(
        np.arange(x_min, x_max, step),
        np.arange(y_min, y_max, step),
    )
    return xx, yy, np.c_[xx.ravel(), yy.ravel()]


def plot_decision_boundary(
    x_train: np.ndarray,
    result: ExperimentResult,
    mesh: tuple[np.ndarray, np.ndarray, np.ndarray],
    output_dir: Path,
    show: bool,
) -> None:
    """Plot the probability field, 0.5 boundary, and poisoned labels."""
    xx, yy, mesh_points = mesh
    probability = result.model.predict_proba(mesh_points)[:, 1].reshape(xx.shape)

    plt.figure(figsize=(12, 6))
    plt.contourf(
        xx,
        yy,
        probability,
        levels=np.linspace(0, 1, 21),
        cmap=CLASS_CMAP,
        alpha=0.30,
    )
    plt.contour(
        xx,
        yy,
        probability,
        levels=[0.5],
        colors=[WHITE],
        linewidths=[2.0],
    )
    plt.scatter(
        x_train[:, 0],
        x_train[:, 1],
        c=result.y_train_poisoned,
        cmap=CLASS_CMAP,
        edgecolors=NODE_BLACK,
        s=50,
        alpha=0.8,
    )

    percent = result.percentage * 100
    plt.title(
        f"Decision Boundary ({percent:.0f}% Poisoned)\n"
        f"Accuracy={result.accuracy:.4f}, Log Loss={result.log_loss:.4f}",
        fontsize=16,
        color=HTB_GREEN,
    )
    plt.xlabel("Feature 1")
    plt.ylabel("Feature 2")
    save_figure(
        output_dir / f"decision_boundary_{percent:02.0f}_percent.png",
        show,
    )


def plot_accuracy_and_loss(
    results: list[ExperimentResult],
    output_dir: Path,
    show: bool,
) -> None:
    """Plot accuracy and log loss against poisoning percentage."""
    percentages = [result.percentage * 100 for result in results]
    accuracies = [result.accuracy for result in results]
    losses = [result.log_loss for result in results]

    figure, accuracy_axis = plt.subplots(figsize=(10, 6))
    loss_axis = accuracy_axis.twinx()

    accuracy_line = accuracy_axis.plot(
        percentages,
        accuracies,
        marker="o",
        color=HTB_GREEN,
        linewidth=2,
        label="Accuracy",
    )
    loss_line = loss_axis.plot(
        percentages,
        losses,
        marker="s",
        color=MALWARE_RED,
        linewidth=2,
        label="Log Loss",
    )

    accuracy_axis.set_title(
        "Model Performance vs. Label Flipping Percentage",
        fontsize=16,
        color=HTB_GREEN,
    )
    accuracy_axis.set_xlabel("Training Labels Flipped (%)")
    accuracy_axis.set_ylabel("Accuracy", color=HTB_GREEN)
    accuracy_axis.set_ylim(0, 1.05)
    accuracy_axis.set_xticks(percentages)
    loss_axis.set_ylabel("Log Loss", color=MALWARE_RED)

    lines = accuracy_line + loss_line
    accuracy_axis.legend(lines, [line.get_label() for line in lines])
    figure.tight_layout()
    save_figure(output_dir / "performance_trend.png", show)


def plot_all_boundaries(
    x_train: np.ndarray,
    y_train_clean: np.ndarray,
    results: list[ExperimentResult],
    mesh: tuple[np.ndarray, np.ndarray, np.ndarray],
    output_dir: Path,
    show: bool,
) -> None:
    """Overlay all p=0.5 decision boundaries on the clean data."""
    xx, yy, mesh_points = mesh

    plt.figure(figsize=(12, 8))
    plt.scatter(
        x_train[:, 0],
        x_train[:, 1],
        c=y_train_clean,
        cmap=CLASS_CMAP,
        edgecolors=NODE_BLACK,
        s=50,
        alpha=0.45,
    )

    legend_handles = []
    fallback_colors = plt.cm.viridis(np.linspace(0, 1, len(results)))
    for index, result in enumerate(results):
        probability = result.model.predict_proba(mesh_points)[:, 1].reshape(xx.shape)
        color = BOUNDARY_COLORS.get(result.percentage, fallback_colors[index])
        linestyle = "solid" if result.percentage == 0 else "dashed"
        plt.contour(
            xx,
            yy,
            probability,
            levels=[0.5],
            colors=[color],
            linestyles=[linestyle],
            linewidths=[2.5],
        )
        legend_handles.append(
            plt.Line2D(
                [0],
                [0],
                color=color,
                linewidth=2.5,
                linestyle=linestyle,
                label=f"{result.percentage * 100:.0f}% poisoned",
            )
        )

    plt.title(
        "Shift in Decision Boundary with Increasing Label Flipping",
        fontsize=16,
        color=HTB_GREEN,
    )
    plt.xlabel("Feature 1")
    plt.ylabel("Feature 2")
    plt.legend(handles=legend_handles, title="Decision Boundaries")
    save_figure(output_dir / "all_decision_boundaries.png", show)


def plot_confusion_matrices(
    results: list[ExperimentResult],
    output_dir: Path,
    show: bool,
) -> None:
    """Plot clean-test confusion matrices for all models in one figure."""
    columns = 3
    rows = int(np.ceil(len(results) / columns))
    figure, axes = plt.subplots(rows, columns, figsize=(15, 4.5 * rows))
    axes_array = np.atleast_1d(axes).ravel()

    for axis, result in zip(axes_array, results):
        sns.heatmap(
            result.confusion,
            annot=True,
            fmt="d",
            cmap="Blues",
            cbar=False,
            ax=axis,
        )
        axis.set_title(
            f"{result.percentage * 100:.0f}% poisoned\n"
            f"Accuracy={result.accuracy:.4f}"
        )
        axis.set_xlabel("Predicted label")
        axis.set_ylabel("True label")

    for unused_axis in axes_array[len(results) :]:
        unused_axis.set_visible(False)

    figure.suptitle("Confusion Matrices on the Clean Test Set", fontsize=16)
    figure.tight_layout()
    save_figure(output_dir / "confusion_matrices.png", show)


def save_results_csv(results: list[ExperimentResult], output_dir: Path) -> None:
    """Save compact metrics and learned parameters for later analysis."""
    path = output_dir / "results.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "poison_percentage",
                "n_flipped",
                "accuracy",
                "log_loss",
                "weight_1",
                "weight_2",
                "intercept",
                "tn",
                "fp",
                "fn",
                "tp",
            ]
        )
        for result in results:
            tn, fp, fn, tp = result.confusion.ravel()
            weights = result.model.coef_[0]
            writer.writerow(
                [
                    result.percentage,
                    result.n_flipped,
                    result.accuracy,
                    result.log_loss,
                    weights[0],
                    weights[1],
                    result.model.intercept_[0],
                    tn,
                    fp,
                    fn,
                    tp,
                ]
            )


def print_result(result: ExperimentResult, y_test_clean: np.ndarray) -> None:
    """Print the metrics for one poisoning level."""
    percent = result.percentage * 100
    print(f"\n--- {percent:.0f}% labels flipped ---")
    print(f"Flipped labels: {result.n_flipped}")
    print(f"Accuracy:       {result.accuracy:.4f}")
    print(f"Log Loss:       {result.log_loss:.4f}")
    print("Confusion matrix:")
    print(result.confusion)
    print("Classification report:")
    print(
        classification_report(
            y_test_clean,
            result.y_pred,
            target_names=["Negative", "Positive"],
            digits=4,
            zero_division=0,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a reproducible label-flipping poisoning experiment."
    )
    parser.add_argument(
        "--percentages",
        nargs="+",
        type=float,
        default=[0.0, 0.10, 0.20, 0.30, 0.40, 0.50],
        help="Fractions of training labels to flip (0.0 through 0.5).",
    )
    parser.add_argument(
        "--sampling",
        choices=["nested", "independent"],
        default="nested",
        help="Use cumulative nested indices or a new sample at each percentage.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help="Random seed used for data and poisoning (default: 1337).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).with_name("label_flipping_output"),
        help="Directory for figures and results.csv.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Display plots interactively in addition to saving them.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    percentages = validate_percentages(args.percentages)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    configure_plot_style()

    x_train, x_test, y_train, y_test = generate_dataset(args.seed)

    # Preserve immutable clean references for every later comparison.
    x_train_clean = x_train.copy()
    y_train_clean = y_train.copy()
    x_test_clean = x_test.copy()
    y_test_clean = y_test.copy()

    print(f"Training samples: {len(x_train_clean)}")
    print(f"Test samples:     {len(x_test_clean)}")
    print(f"Sampling mode:    {args.sampling}")
    print(f"Output directory: {args.output_dir.resolve()}")

    plot_clean_data(x_train_clean, y_train_clean, args.output_dir, args.show)
    mesh = create_mesh(x_train_clean)
    flip_order = (
        build_nested_flip_order(len(y_train_clean), args.seed)
        if args.sampling == "nested"
        else None
    )

    results: list[ExperimentResult] = []
    for percentage in percentages:
        y_poisoned, flipped_indices = flip_binary_labels(
            y_train_clean,
            percentage,
            seed=args.seed,
            flip_order=flip_order,
        )

        # Prove that the clean evidence and all feature arrays remain unchanged.
        assert np.array_equal(x_train, x_train_clean)
        assert np.array_equal(y_train, y_train_clean)
        assert np.array_equal(x_test, x_test_clean)
        assert np.array_equal(y_test, y_test_clean)

        result = train_and_evaluate(
            x_train_clean,
            y_poisoned,
            x_test_clean,
            y_test_clean,
            percentage,
            flipped_indices,
            args.seed,
        )
        results.append(result)
        print_result(result, y_test_clean)

        plot_decision_boundary(
            x_train_clean,
            result,
            mesh,
            args.output_dir,
            args.show,
        )
        if percentage > 0:
            plot_poisoned_data(
                x_train_clean,
                y_train_clean,
                result,
                args.output_dir,
                args.show,
            )

    plot_accuracy_and_loss(results, args.output_dir, args.show)
    plot_all_boundaries(
        x_train_clean,
        y_train_clean,
        results,
        mesh,
        args.output_dir,
        args.show,
    )
    plot_confusion_matrices(results, args.output_dir, args.show)
    save_results_csv(results, args.output_dir)

    print("\nExperiment complete.")
    print(f"Results saved to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
