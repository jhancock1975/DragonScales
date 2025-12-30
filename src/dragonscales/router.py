"""Expert router that learns which free model to call."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol


@dataclass
class Expert:
    """Represents a single expert (e.g., a free LLM model)."""

    id: str
    metadata: Mapping[str, Any] | None = None


@dataclass
class ExpertStats:
    """Tracks routing performance for an expert."""

    pulls: int = 0
    reward_sum: float = 0.0

    @property
    def mean_reward(self) -> float:
        return self.reward_sum / self.pulls if self.pulls else 0.0


class Storage(Protocol):
    """Checkpoint storage backend."""

    def save(self, key: str, data: bytes) -> None:  # pragma: no cover - Protocol
        ...

    def load(self, key: str) -> bytes | None:  # pragma: no cover - Protocol
        ...


class LocalFileStorage:
    """Store checkpoints on the filesystem."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: bytes) -> None:
        path = self.base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def load(self, key: str) -> bytes | None:
        path = self.base_dir / key
        if not path.exists():
            return None
        return path.read_bytes()


class S3Storage:
    """S3-compatible storage (e.g., MinIO) for checkpoints."""

    def __init__(self, bucket: str, base_path: str = "", **client_kwargs: Any) -> None:  # pragma: no cover - thin wrapper
        try:
            import boto3  # type: ignore
        except ImportError as exc:  # pragma: no cover - runtime check
            raise RuntimeError("Install the 'moe' extra to enable S3Storage (boto3)") from exc

        self.bucket = bucket
        self.base_path = base_path.strip("/")
        self.client = boto3.client("s3", **client_kwargs)

    def _key(self, key: str) -> str:  # pragma: no cover - deterministic helper
        return f"{self.base_path}/{key}" if self.base_path else key

    def save(self, key: str, data: bytes) -> None:  # pragma: no cover - exercised in integration
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data)

    def load(self, key: str) -> bytes | None:  # pragma: no cover - exercised in integration
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
            return resp["Body"].read()
        except self.client.exceptions.NoSuchKey:  # type: ignore[attr-defined]
            return None


class UCBRouter:
    """
    Upper Confidence Bound (UCB1) router to select experts.

    Inspired by MoE gating patterns (see openai/gpt-oss-120b) but simplified to
    a lightweight bandit for free-model routing.
    """

    def __init__(
        self,
        experts: Iterable[Expert],
        storage: Storage | None = None,
        checkpoint_key: str = "router_state.json",
        min_pulls: int = 1,
        exploration: float = 1.4,
    ) -> None:
        self.experts = list(experts)
        self.storage = storage
        self.checkpoint_key = checkpoint_key
        self.exploration = exploration
        self.min_pulls = min_pulls
        self.state: dict[str, ExpertStats] = {e.id: ExpertStats() for e in self.experts}
        self._load()

    def select(self) -> Expert:
        """Pick the next expert to call."""
        total_pulls = sum(s.pulls for s in self.state.values())
        if total_pulls == 0:
            return self.experts[0]

        def score(expert: Expert) -> float:
            stats = self.state[expert.id]
            if stats.pulls < self.min_pulls:
                return float("inf")
            ucb = stats.mean_reward + self.exploration * math.sqrt(math.log(total_pulls) / stats.pulls)
            return ucb

        return max(self.experts, key=score)

    def record_reward(self, expert_id: str, reward: float) -> None:
        """Update stats for an expert after an invocation."""
        stats = self.state.setdefault(expert_id, ExpertStats())
        stats.pulls += 1
        stats.reward_sum += reward
        self._save()

    def _save(self) -> None:
        if not self.storage:
            return
        payload = {
            "experts": [asdict(e) for e in self.experts],
            "state": {k: asdict(v) for k, v in self.state.items()},
        }
        self.storage.save(self.checkpoint_key, json.dumps(payload).encode("utf-8"))

    def _load(self) -> None:
        if not self.storage:
            return
        raw = self.storage.load(self.checkpoint_key)
        if not raw:
            return
        data = json.loads(raw.decode("utf-8"))
        self.state = {
            k: ExpertStats(**v)
            for k, v in data.get("state", {}).items()
        }
