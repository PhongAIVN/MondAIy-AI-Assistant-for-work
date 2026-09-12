from src.services.llm_routing import RouteLane, classify_query


def test_small_talk_fixtures_use_small_talk_lane():
    assert classify_query("hi") == RouteLane.SMALL_TALK
    assert classify_query("how are you?") == RouteLane.SMALL_TALK
    assert classify_query("  CHÀO! ") == RouteLane.SMALL_TALK
    assert classify_query("cảm ơn nha") == RouteLane.SMALL_TALK
    assert classify_query("kể một câu đùa ngắn đi") == RouteLane.SMALL_TALK


def test_mixed_or_ambiguous_query_defaults_to_work_lane():
    assert classify_query("hi, hôm nay tôi cần làm gì?") == RouteLane.WORK
    assert classify_query("cái kia thì sao?") == RouteLane.WORK
