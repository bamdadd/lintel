import sys
sys.path.insert(0, "src")

from math_utils import add, is_prime


def test_add():
    assert add(1, 2) == 3
    assert add(-1, 1) == 0


def test_is_prime():
    assert is_prime(2)
    assert is_prime(7)
    assert not is_prime(4)
    assert not is_prime(1)
