from src.services.openrouter_keys import OpenRouterKeyPool


def test_pool_round_robins_keys():
    pool = OpenRouterKeyPool(["a", "b", "c"])
    assert [pool.next_key() for _ in range(4)] == ["a", "b", "c", "a"]


def test_pool_skips_key_in_cooldown():
    pool = OpenRouterKeyPool(["a", "b"])
    first = pool.next_key()
    pool.mark_unavailable(first)
    assert pool.next_key() != first
