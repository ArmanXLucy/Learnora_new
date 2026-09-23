"""
Completion-Confidence Model ("AI match %").

A logistic regression model predicting the probability a learner completes
a given course/topic, using 3 features:
  1. learner's average relevant skill level (0-1, normalized)
  2. course's normalized difficulty (0-1)
  3. prerequisite readiness (0 or 1)

IMPORTANT (disclosed, as required by the project's own documentation):
No real completion history exists yet. This model is trained on a
SYNTHETICALLY GENERATED dataset built from a principled rule: completion
likelihood is highest when skill level closely matches difficulty and
prerequisites are met, and falls off as that gap widens or prerequisites
are unmet. Any output should be labeled "based on simulated data" until
the model is retrained on real enrollment/completion logs.
"""
import os
import numpy as np
from sklearn.linear_model import LogisticRegression
import joblib

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "instance", "completion_model.joblib")


def generate_synthetic_dataset(n=2000, seed=42):
    rng = np.random.default_rng(seed)
    skill_level = rng.uniform(0, 1, n)          # normalized learner level
    difficulty = rng.uniform(0, 1, n)            # normalized course difficulty
    prereq_ready = rng.integers(0, 2, n)         # 0 or 1

    gap = np.abs(skill_level - difficulty)
    # principled rule: base probability high when gap is small & prereqs met,
    # decays as gap grows or prereqs are missing; small random noise added.
    base_prob = (1 - gap) * (0.55 + 0.45 * prereq_ready)
    noise = rng.normal(0, 0.08, n)
    prob = np.clip(base_prob + noise, 0.01, 0.99)
    labels = (rng.uniform(0, 1, n) < prob).astype(int)

    X = np.column_stack([skill_level, difficulty, prereq_ready])
    y = labels
    return X, y


def train_and_save():
    X, y = generate_synthetic_dataset()
    model = LogisticRegression()
    model.fit(X, y)
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    return model


def load_model():
    if not os.path.exists(MODEL_PATH):
        return train_and_save()
    return joblib.load(MODEL_PATH)


def predict_completion_probability(skill_level_norm, difficulty_norm, prereq_ready):
    model = load_model()
    X = np.array([[skill_level_norm, difficulty_norm, float(prereq_ready)]])
    prob = model.predict_proba(X)[0][1]
    return float(prob)
