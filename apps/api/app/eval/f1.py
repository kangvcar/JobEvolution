from __future__ import annotations


def set_f1(pred: set[str] | list[str], gold: set[str] | list[str]) -> dict:
    """Skill-id set P/R/F1. Empty vs empty is 1; one side empty is 0."""
    pred_set = {str(x) for x in pred if x}
    gold_set = {str(x) for x in gold if x}
    if not pred_set and not gold_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "n_pred": 0, "n_gold": 0}
    if not pred_set or not gold_set:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "n_pred": len(pred_set),
            "n_gold": len(gold_set),
        }
    hit = pred_set & gold_set
    precision = len(hit) / len(pred_set)
    recall = len(hit) / len(gold_set)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "n_pred": len(pred_set),
        "n_gold": len(gold_set),
    }


def mean_f1(rows: list[dict]) -> dict:
    if not rows:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "n": 0}
    n = len(rows)
    return {
        "precision": sum(row["precision"] for row in rows) / n,
        "recall": sum(row["recall"] for row in rows) / n,
        "f1": sum(row["f1"] for row in rows) / n,
        "n": n,
    }
