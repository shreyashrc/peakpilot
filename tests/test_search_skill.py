from mcp.skills.search_skill import SearchSkill


def test_extract_entities_basic():
    s = SearchSkill()
    q = "Is Kedarkanta safe in December?"
    entities = s.extract_entities(q)
    assert entities["trail"] == "Kedarkantha"
    assert entities["intent"] in {"safety", "weather"}
    assert any(m for m in entities["months"])  # has months
    assert "mountain_forecast" in entities["sources"]


def test_fuzzy_valley_of_flowers():
    s = SearchSkill()
    q = "How to get permits for VOF in July?"
    entities = s.extract_entities(q)
    assert entities["trail"] == "Valley of Flowers"
    assert entities["intent"] == "permits"
    assert "wikivoyage" in entities["sources"]
