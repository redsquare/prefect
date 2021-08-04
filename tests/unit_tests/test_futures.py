import pytest
from uuid import uuid4
from collections import OrderedDict
from unittest.mock import MagicMock
from dataclasses import dataclass

from prefect.futures import PrefectFuture, resolve_futures
from prefect.orion.schemas.core import State, StateType
from prefect.client import OrionClient


mock_client = MagicMock(spec=OrionClient)()
mock_client.read_flow_run_states.return_value = [
    State(type=StateType.COMPLETED, data=None)
]


def test_resolve_futures_transforms_future():
    future = PrefectFuture(
        flow_run_id=uuid4(),
        client=mock_client,
        wait_callback=lambda _: "foo",
    )
    assert resolve_futures(future) == "foo"


def test_resolve_futures_transforms_state():
    state = State(type=StateType.COMPLETED, data="foo")
    assert resolve_futures(state) == "foo"


@pytest.mark.parametrize("typ", [list, tuple, set])
def test_resolve_futures_transforms_future_in_listlike_type(typ):
    future = PrefectFuture(
        flow_run_id=uuid4(),
        client=mock_client,
        wait_callback=lambda _: "foo",
    )
    assert resolve_futures(typ(["a", future, "b"])) == typ(["a", "foo", "b"])


@pytest.mark.parametrize("typ", [dict, OrderedDict])
def test_resolve_futures_transforms_future_in_dictlike_type(typ):
    key_future = PrefectFuture(
        flow_run_id=uuid4(),
        client=mock_client,
        wait_callback=lambda _: "foo",
    )
    value_future = PrefectFuture(
        flow_run_id=uuid4(),
        client=mock_client,
        wait_callback=lambda _: "bar",
    )
    assert resolve_futures(
        typ([("a", 1), (key_future, value_future), ("b", 2)])
    ) == typ([("a", 1), ("foo", "bar"), ("b", 2)])


def test_resolve_futures_transforms_future_in_dataclass():
    @dataclass
    class Foo:
        a: int
        foo: str
        b: int = 2

    future = PrefectFuture(
        flow_run_id=uuid4(),
        client=mock_client,
        wait_callback=lambda _: "bar",
    )
    assert resolve_futures(Foo(a=1, foo=future)) == Foo(a=1, foo="bar", b=2)


def test_resolves_futures_in_nested_collections():
    @dataclass
    class Foo:
        foo: str
        nested_list: list
        nested_dict: dict

    future = PrefectFuture(
        flow_run_id=uuid4(),
        client=mock_client,
        wait_callback=lambda _: "bar",
    )
    assert resolve_futures(
        Foo(foo=future, nested_list=[[future]], nested_dict={"key": [future]})
    ) == Foo(foo="bar", nested_list=[["bar"]], nested_dict={"key": ["bar"]})
