import pytest
from hypothesis import given, strategies as st

from dragonscales.dragon import Dragon


@pytest.mark.hypothesis
@given(st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False)))
def test_price_value_numeric_round_trip(value):
    dragon = Dragon(client=None)

    assert dragon._price_value({"prompt": value}, "prompt") == pytest.approx(float(value))


@pytest.mark.hypothesis
@given(
    st.one_of(
        st.none(),
        st.text(alphabet="abc", min_size=1),
        st.dictionaries(keys=st.text(min_size=1, max_size=3), values=st.integers(), max_size=2),
    )
)
def test_price_value_rejects_non_numeric(value):
    dragon = Dragon(client=None)

    assert dragon._price_value({"prompt": value}, "prompt") is None


@pytest.mark.hypothesis
@given(
    prompt=st.floats(allow_nan=False, allow_infinity=False),
    completion=st.floats(allow_nan=False, allow_infinity=False),
)
def test_is_free_requires_zero_prices(prompt, completion):
    dragon = Dragon(client=None)
    model = {"pricing": {"prompt": prompt, "completion": completion}}

    expected = float(prompt) == 0 and float(completion) == 0
    assert dragon._is_free(model) is expected
