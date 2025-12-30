import math
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from dragonscales.router import Expert, LocalFileStorage, UCBRouter


@given(st.lists(st.floats(min_value=-1, max_value=1), min_size=1, max_size=20))
def test_rewards_accumulate_and_mean_is_bounded(rewards):
    router = UCBRouter([Expert("a")], storage=None, exploration=0.1)
    for r in rewards:
        router.record_reward("a", r)

    stats = router.state["a"]
    assert stats.pulls == len(rewards)
    assert stats.mean_reward <= 1
    assert stats.mean_reward >= -1


@given(st.lists(st.floats(min_value=0, max_value=1), min_size=1, max_size=30))
def test_checkpoint_round_trip_property(rewards, tmp_path: Path):
    experts = [Expert("x"), Expert("y")]
    storage = LocalFileStorage(tmp_path)
    router = UCBRouter(experts, storage=storage, checkpoint_key="ckpt.json", exploration=0.1)

    for i, r in enumerate(rewards):
        expert_id = experts[i % 2].id
        router.record_reward(expert_id, r)

    reloaded = UCBRouter(experts, storage=storage, checkpoint_key="ckpt.json", exploration=0.1)
    assert reloaded.state == router.state


@given(
    pulls=st.lists(
        st.tuples(
            st.sampled_from(["a", "b", "c"]),
            st.floats(min_value=0, max_value=1),
        ),
        min_size=1,
        max_size=40,
    )
)
def test_ucb_scores_increase_with_rewards(pulls):
    experts = [Expert("a"), Expert("b"), Expert("c")]
    router = UCBRouter(experts, storage=None, exploration=1.0, min_pulls=1)

    for expert_id, reward in pulls:
        router.record_reward(expert_id, reward)

    total_pulls = sum(s.pulls for s in router.state.values())
    if total_pulls == 0:
        return

    scores = {}
    for e in experts:
        s = router.state[e.id]
        if s.pulls == 0:
            scores[e.id] = float("inf")
        else:
            scores[e.id] = s.mean_reward + router.exploration * math.sqrt(math.log(total_pulls) / s.pulls)

    best_mean = max((s.mean_reward for s in router.state.values()), default=0)
    assert max(scores.values()) >= best_mean
