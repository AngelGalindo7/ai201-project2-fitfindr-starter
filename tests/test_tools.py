# tests/test_tools.py
from tools import (
    search_listings,
    suggest_outfit,
    create_fit_card,
    compare_price,
    get_trends,
)
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe
from utils.data_loader import load_listings
from utils.profile import load_profile, save_profile


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe():
    item = load_listings()[1]   # Y2K Baby Tee
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0

def test_suggest_outfit_populated_wardrobe():
    item = load_listings()[1]
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    item = load_listings()[0]
    result = create_fit_card("", item)
    assert result == "Unable to create fit card: no outfit suggestion was provided."

def test_create_fit_card_varies():
    item = load_listings()[1]
    outfit = "Pair with baggy jeans, chunky white sneakers, and a tiny shoulder bag."
    result_1 = create_fit_card(outfit, item)
    result_2 = create_fit_card(outfit, item)
    assert result_1 != result_2  # if identical, increase temperature in tools.py


# ── Tool 4: compare_price (stretch: price comparison) ─────────────────────────

def test_compare_price_enough_data():
    listings = load_listings()
    # A vintage tee shares category + tags with several other listings.
    item = next(i for i in listings if i["id"] == "lst_002")
    result = compare_price(item, listings)
    assert isinstance(result, str)
    assert "$" in result            # includes the price reasoning
    assert "Verdict:" in result

def test_compare_price_too_few_comparisons():
    listings = load_listings()
    # A one-off item with no category+tag siblings has no comparables.
    item = {
        "id": "lst_fake",
        "category": "accessories",
        "style_tags": ["nonexistent_tag_xyz"],
        "price": 25.0,
    }
    result = compare_price(item, listings)
    assert result == (
        "Not enough comparable listings to evaluate pricing because there "
        "are fewer than 2 similar items in the dataset."
    )


# ── Tool 5: get_trends (stretch: trend awareness) ─────────────────────────────

def test_get_trends_returns_styles_for_size():
    trends = get_trends("M")
    assert trends["size_range"] == "M"
    assert isinstance(trends["trending_styles"], list)
    assert len(trends["trending_styles"]) > 0

def test_get_trends_unknown_size_falls_back_to_overall():
    # A shoe size doesn't map to a letter bucket → overall trends.
    trends = get_trends("US 8")
    assert trends["size_range"] == "overall"
    assert len(trends["trending_styles"]) > 0


# ── Style Profile Memory (stretch) ────────────────────────────────────────────

def test_profile_save_then_load_roundtrips():
    # First interaction saves the wardrobe; a second, separate call loads it
    # back without re-entry.
    save_profile(get_example_wardrobe())
    loaded = load_profile()
    assert loaded["items"] == get_example_wardrobe()["items"]
