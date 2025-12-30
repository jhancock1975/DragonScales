import json
from pathlib import Path

import pytest

from dragonscales.router import Expert, LocalFileStorage, UCBRouter


def test_router_prefers_higher_reward(tmp_path: Path):
    experts = [Expert("a"), Expert("b")]
    storage = LocalFileStorage(tmp_path)
    router = UCBRouter(experts, storage=storage, checkpoint_key="state.json", exploration=0.1)

    chosen = router.select()
    router.record_reward(chosen.id, reward=0.0)
    router.record_reward("b", reward=1.0)

    for _ in range(5):
        router.record_reward("b", reward=1.0)

    assert router.select().id == "b"


def test_router_checkpoint_round_trip(tmp_path: Path):
    experts = [Expert("x"), Expert("y")]
    storage = LocalFileStorage(tmp_path)
    router = UCBRouter(experts, storage=storage, checkpoint_key="state.json", exploration=0.1)

    router.record_reward("x", 1.0)
    router.record_reward("y", 0.0)

    # simulate new process
    reloaded = UCBRouter(experts, storage=storage, checkpoint_key="state.json", exploration=0.1)
    assert reloaded.state["x"].pulls == 1
    assert reloaded.state["y"].pulls == 1
    assert reloaded.select().id == "x"


def test_router_uses_min_pulls_for_exploration():
    experts = [Expert("a"), Expert("b"), Expert("c")]
    router = UCBRouter(experts, storage=None, min_pulls=1, exploration=1.4)

    # With no pulls, first expert is picked deterministically
    assert router.select().id == "a"

    # After logging one reward, others still get exploration opportunity
    router.record_reward("a", 0.0)
    pick_ids = {router.select().id for _ in range(3)}
    assert "b" in pick_ids or "c" in pick_ids
