"""
Evaluation & Validation Plan (Section 26 of the project doc).

Everything here is computed on SYNTHETIC data (simulated learners / a
simulated completion dataset) since the platform has no real learner
history yet. All outputs must be labeled as simulated in any paper/report
until recomputed on real enrollment/completion data.

This module is only ever surfaced on the admin "Research" page, never to
learners.
"""
import os
import json
import random
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from sklearn.metrics import accuracy_score, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression

from .skill_graph import SKILLS, topic_order, build_roadmap, TOPIC_META, build_graph
from .recommend import recommend
from .completion_model import generate_synthetic_dataset

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "research")
METRICS_JSON = os.path.join(STATIC_DIR, "metrics.json")

os.makedirs(STATIC_DIR, exist_ok=True)

K = 5
VARIANTS = {
    "full_model": dict(use_similarity=True, use_gap_weight=True, use_prereq_weight=True, use_context_filter=True),
    "no_similarity": dict(use_similarity=False, use_gap_weight=True, use_prereq_weight=True, use_context_filter=True),
    "no_gap_weight": dict(use_similarity=True, use_gap_weight=False, use_prereq_weight=True, use_context_filter=True),
    "no_prereq_weight": dict(use_similarity=True, use_gap_weight=True, use_prereq_weight=False, use_context_filter=True),
    "no_context_filter": dict(use_similarity=True, use_gap_weight=True, use_prereq_weight=True, use_context_filter=False),
    "plain_cosine_baseline": dict(use_similarity=True, use_gap_weight=False, use_prereq_weight=False, use_context_filter=False),
}


def _random_mastered_set(skill_id, rng):
    """Simulate a learner who has mastered a random-length prefix of the
    topological topic order (a plausible, prerequisite-consistent learner state)."""
    order = topic_order(skill_id)
    cutoff = rng.integers(0, len(order))  # 0 = brand-new learner
    return set(order[:cutoff])


def _ground_truth_relevant(skill_id, mastered_set):
    """The 'correct' next topics: gap topics whose prerequisites are satisfied.
    This acts as the synthetic ground-truth relevant set referenced in Section 26.1."""
    roadmap = build_roadmap(skill_id, mastered_set)
    return set(t["topic_id"] for t in roadmap if t["status"] == "ready")


def _precision_recall_map_at_k(recommended_ids, relevant_set, k):
    top_k = recommended_ids[:k]
    if not top_k:
        return 0.0, 0.0, 0.0
    hits = [1 if tid in relevant_set else 0 for tid in top_k]
    precision = sum(hits) / len(top_k)
    recall = sum(hits) / len(relevant_set) if relevant_set else 0.0

    # Average Precision for this single query
    ap = 0.0
    hit_count = 0
    for i, h in enumerate(hits):
        if h:
            hit_count += 1
            ap += hit_count / (i + 1)
    ap = ap / max(1, sum(hits)) if sum(hits) > 0 else 0.0
    return precision, recall, ap


def run_ablation_study(n_learners=150, seed=7):
    rng = np.random.default_rng(seed)
    skill_ids = list(SKILLS.keys())
    variant_metrics = {v: {"precision": [], "recall": [], "map": [],
                            "gap_coverage": [], "prereq_violation": [],
                            "context_compliance": []} for v in VARIANTS}

    evaluated = 0
    attempts = 0
    max_attempts = n_learners * 8
    while evaluated < n_learners and attempts < max_attempts:
        attempts += 1
        skill_id = skill_ids[rng.integers(0, len(skill_ids))]
        mastered = _random_mastered_set(skill_id, rng)
        relevant = _ground_truth_relevant(skill_id, mastered)
        hours_per_week = int(rng.integers(2, 12))

        full_gap = set(t["topic_id"] for t in build_roadmap(skill_id, mastered) if t["status"] != "mastered")
        # Skip near-complete learners: if the remaining gap is no bigger than K,
        # every variant trivially recommends ~the whole gap regardless of its
        # ranking logic, which washes out any real difference between variants.
        # Keeping only learners with a real gap makes the ablation meaningful.
        if not relevant or len(full_gap) <= K:
            continue
        evaluated += 1

        for variant_name, flags in VARIANTS.items():
            recs = recommend(skill_id, mastered, hours_per_week=hours_per_week, top_k=K, **flags)
            rec_ids = [r["topic_id"] for r in recs]

            precision, recall, ap = _precision_recall_map_at_k(rec_ids, relevant, K)
            variant_metrics[variant_name]["precision"].append(precision)
            variant_metrics[variant_name]["recall"].append(recall)
            variant_metrics[variant_name]["map"].append(ap)

            # skill-gap coverage rate: fraction of the FULL gap covered by top-K combined
            full_gap = set(t["topic_id"] for t in build_roadmap(skill_id, mastered) if t["status"] != "mastered")
            coverage = len(set(rec_ids) & full_gap) / len(full_gap) if full_gap else 0.0
            variant_metrics[variant_name]["gap_coverage"].append(coverage)

            # prerequisite violation rate: fraction of recs the learner ISN'T ready for
            violations = sum(1 for r in recs if not r.get("status") == "ready" and r.get("topic_id") not in relevant)
            prereq_violation = violations / len(recs) if recs else 0.0
            variant_metrics[variant_name]["prereq_violation"].append(prereq_violation)

            # context compliance: fraction of recs fitting the stated time budget
            compliant = sum(1 for r in recs if r.get("context_ok", True))
            variant_metrics[variant_name]["context_compliance"].append(compliant / len(recs) if recs else 0.0)

    summary = {}
    for v, m in variant_metrics.items():
        summary[v] = {k: round(float(np.mean(vals)), 4) if vals else 0.0 for k, vals in m.items()}
    return summary


def plot_ablation_bar_chart(summary):
    variants = list(summary.keys())
    metrics_to_plot = ["precision", "recall", "map", "gap_coverage"]
    x = np.arange(len(variants))
    width = 0.2

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for i, metric in enumerate(metrics_to_plot):
        values = [summary[v][metric] for v in variants]
        ax.bar(x + i * width, values, width, label=metric.replace("_", " ").title())

    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels([v.replace("_", " ") for v in variants], rotation=20, ha="right")
    ax.set_ylabel("Score")
    ax.set_title(f"Ablation Study — Recommendation Quality @K={K} (synthetic learners)")
    ax.legend()
    fig.tight_layout()
    path = os.path.join(STATIC_DIR, "ablation_study.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def evaluate_completion_model():
    """Accuracy, AUC-ROC and a calibration curve for the logistic regression
    completion-confidence model, evaluated on a held-out split of the
    SYNTHETIC training dataset (see completion_model.py docstring)."""
    X, y = generate_synthetic_dataset(n=3000, seed=99)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=1)

    model = LogisticRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_proba)
    fpr, tpr, _ = roc_curve(y_test, y_proba)

    # ROC curve plot
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.plot(fpr, tpr, label=f"ROC (AUC = {auc:.3f})", color="#7c4dff")
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Random baseline")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("Completion-Confidence Model — ROC Curve\n(trained on SYNTHETIC data)")
    ax.legend()
    fig.tight_layout()
    roc_path = os.path.join(STATIC_DIR, "completion_model_roc.png")
    fig.savefig(roc_path, dpi=140)
    plt.close(fig)

    # calibration curve (bin predicted prob vs observed fraction positive)
    bins = np.linspace(0, 1, 11)
    bin_ids = np.digitize(y_proba, bins) - 1
    bin_ids = np.clip(bin_ids, 0, 9)
    observed = []
    predicted_mean = []
    for b in range(10):
        mask = bin_ids == b
        if mask.sum() > 0:
            observed.append(y_test[mask].mean())
            predicted_mean.append(y_proba[mask].mean())
    fig2, ax2 = plt.subplots(figsize=(5.5, 5))
    ax2.plot(predicted_mean, observed, marker="o", color="#ff6b6b", label="Model calibration")
    ax2.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfectly calibrated")
    ax2.set_xlabel("Mean Predicted Probability")
    ax2.set_ylabel("Observed Completion Rate")
    ax2.set_title("Calibration Curve (SYNTHETIC data)")
    ax2.legend()
    fig2.tight_layout()
    cal_path = os.path.join(STATIC_DIR, "completion_model_calibration.png")
    fig2.savefig(cal_path, dpi=140)
    plt.close(fig2)

    return {"accuracy": round(float(acc), 4), "auc_roc": round(float(auc), 4)}


def similarity_vs_rulebased_correlation(n_learners=60, seed=11):
    """Correlation between the TF-IDF similarity score and the rule-based
    gap-coverage/prerequisite score, to justify keeping both as separate,
    complementary ablation components rather than redundant ones."""
    rng = np.random.default_rng(seed)
    skill_ids = list(SKILLS.keys())
    sims, rule_scores = [], []

    for _ in range(n_learners):
        skill_id = skill_ids[rng.integers(0, len(skill_ids))]
        mastered = _random_mastered_set(skill_id, rng)
        recs = recommend(skill_id, mastered, top_k=10)
        for r in recs:
            sims.append(r["similarity_score"])
            rule_scores.append(r["gap_weight"] * r["prereq_score"])

    if len(sims) < 2:
        return {"pearson_r": 0.0}
    corr = float(np.corrcoef(sims, rule_scores)[0, 1])

    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.scatter(sims, rule_scores, alpha=0.5, color="#4dabf7")
    ax.set_xlabel("TF-IDF Similarity Score")
    ax.set_ylabel("Rule-Based Gap-Coverage Score")
    ax.set_title(f"Similarity vs Rule-Based Score (Pearson r = {corr:.3f})")
    fig.tight_layout()
    path = os.path.join(STATIC_DIR, "similarity_vs_rulebased.png")
    fig.savefig(path, dpi=140)
    plt.close(fig)

    return {"pearson_r": round(corr, 4)}


def plot_skill_graph(skill_id):
    g = build_graph(skill_id)
    pos = nx.spring_layout(g, seed=42, k=1.2)
    fig, ax = plt.subplots(figsize=(9, 7))
    nx.draw_networkx_nodes(g, pos, node_color="#7c4dff", node_size=1400, alpha=0.9, ax=ax)
    nx.draw_networkx_edges(g, pos, edge_color="#555", arrows=True, arrowsize=15, ax=ax)
    labels = {n: TOPIC_META[n]["display"] for n in g.nodes()}
    nx.draw_networkx_labels(g, pos, labels, font_size=8, font_color="white", ax=ax)
    ax.set_title(f"Course-Knowledge-Skill Graph — {SKILLS[skill_id]['display_name']}")
    ax.axis("off")
    fig.tight_layout()
    path = os.path.join(STATIC_DIR, f"skill_graph_{skill_id}.png")
    fig.savefig(path, dpi=140, facecolor="#12121c")
    plt.close(fig)
    return path


def run_full_evaluation():
    """Runs everything and writes static/research/metrics.json for the admin panel."""
    ablation_summary = run_ablation_study()
    plot_ablation_bar_chart(ablation_summary)
    completion_metrics = evaluate_completion_model()
    correlation = similarity_vs_rulebased_correlation()
    for skill_id in SKILLS:
        plot_skill_graph(skill_id)

    metrics = {
        "note": "All metrics below are computed on SYNTHETIC simulated learners / simulated completion data. "
                "They are placeholders for real evaluation once real learners use the platform (see project docs, Section 26).",
        "k": K,
        "ablation_study": ablation_summary,
        "completion_model": completion_metrics,
        "similarity_vs_rulebased_correlation": correlation,
        "skills_evaluated": list(SKILLS.keys()),
    }
    with open(METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    return metrics


def load_last_metrics():
    if os.path.exists(METRICS_JSON):
        with open(METRICS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return None
