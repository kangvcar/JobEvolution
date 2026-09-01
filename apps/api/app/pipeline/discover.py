from __future__ import annotations

import logging
from typing import Literal

from openai import APIError
from pydantic import BaseModel

from app.targets import JOB_TARGET_NAMES

logger = logging.getLogger(__name__)


class ClusterLabel(BaseModel):
    kind: Literal["new", "alias", "noise"] = "noise"
    alias_of: str | None = None

CLASSIFY_PROMPT = (
    "Classify a job-title cluster as JSON: "
    '{"kind":"new"|"alias"|"noise","alias_of": null or one of the 17 target names}. '
    "alias_of is required when kind is alias."
)


def classify_cluster(title: str, skill_names: list[str], complete_json) -> tuple[str, str | None]:
    try:
        payload = complete_json(
            [
                {"role": "system", "content": CLASSIFY_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"title: {title}\nskills: {', '.join(skill_names)}\n"
                        f"targets: {', '.join(JOB_TARGET_NAMES)}"
                    ),
                },
            ],
        )
    except APIError as exc:
        logger.warning("近名岗位簇判别失败：%s", exc)
        return "noise", None
    try:
        label = ClusterLabel.model_validate(payload if isinstance(payload, dict) else {})
    except Exception:
        return "noise", None
    if label.kind == "alias":
        if label.alias_of not in JOB_TARGET_NAMES:
            return "noise", None
        return "alias", label.alias_of
    if label.kind == "new":
        return "new", None
    return "noise", None
