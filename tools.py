"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()
    keywords = description.lower().split()

    scored = []
    for listing in listings:
        # Size filter — case-insensitive substring match (e.g. "M" matches "S/M")
        if size is not None:
            if size.lower() not in listing["size"].lower():
                continue

        # Price filter — inclusive ceiling
        if max_price is not None:
            if listing["price"] > max_price:
                continue

        # Score by keyword overlap across title, description, and style_tags
        searchable = (
            listing["title"].lower()
            + " "
            + listing["description"].lower()
            + " "
            + " ".join(listing["style_tags"]).lower()
        )
        score = sum(1 for kw in keywords if kw in searchable)

        if score > 0:
            scored.append((score, listing))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict, trends: dict | None = None) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one complete outfit.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.
        trends:   Optional trend dict from get_trends(). When it has a non-empty
                  'trending_styles' list, the prompt asks the LLM to lean into
                  one current trend and name it, so the trend visibly shapes the
                  suggestion. None or empty trends → behaves exactly as before.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    client = _get_groq_client()

    if not wardrobe.get("items"):
        prompt = (
            f"Suggest one outfit built around a '{new_item['title']}' "
            f"({new_item['description']}). Name specific colors, a bottom, and a "
            f"shoe that pair well. Keep it to 2-3 sentences, no preamble or lists."
        )
    else:
        wardrobe_list = "\n".join(
            f"- {item['name']}" for item in wardrobe["items"]
        )
        prompt = (
            f"Suggest one outfit using this thrifted find: '{new_item['title']}' "
            f"({new_item['description']}), paired with specific pieces from this "
            f"wardrobe:\n{wardrobe_list}\n"
            f"Name the exact wardrobe pieces you use. Keep it to 2-3 sentences, "
            f"no preamble or lists."
        )

    # Trend Awareness: if we have live trend data, steer the suggestion toward it
    # and ask the model to call out which trend it leaned into so the influence
    # is visible to the user.
    trending = (trends or {}).get("trending_styles")
    if trending:
        prompt += (
            f"\n\nStyles currently trending in this size range: "
            f"{', '.join(trending)}. "
            f"Lean into at least one of these trends and explicitly name which "
            f"trend you're leaning into."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=180,
    )
    return response.choices[0].message.content


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A one-sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Unable to create fit card: no outfit suggestion was provided."

    client = _get_groq_client()

    prompt = (
        f"Write ONE short, casual Instagram caption — a single sentence, 25 words "
        f"max — for this OOTD post. Sound like a real person, not an ad. "
        f"Work in the item name ('{new_item['title']}'), its price "
        f"(${new_item['price']:g}), and platform ({new_item['platform']}) once each. "
        f"Be punchy and specific about the vibe. No hashtags. "
        f"Outfit details: {outfit}"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=70,
        temperature=1.2,
    )
    return response.choices[0].message.content


# ── Tool 4: compare_price (Stretch Feature: Price Comparison) ──────────────────

def compare_price(item: dict, listings: list[dict]) -> str:
    """
    Estimate whether an item's price is fair by comparing it to similar listings
    in the dataset.

    Comparison method: a listing is "comparable" if it is in the SAME category
    as `item` AND shares at least one style_tag with it (and isn't `item`
    itself). The verdict is based on how the item's price compares to the
    average price of those comparables:
        - more than 10% below average → "Great deal"
        - within 10% of average        → "Fair price"
        - more than 10% above average  → "Above average"

    This tool does not call the LLM — it's pure arithmetic over the dataset.

    Args:
        item:     The listing dict being evaluated (e.g. session["selected_item"]).
        listings: All listings to compare against (from load_listings()).

    Returns:
        A string with the verdict and its reasoning, including the item price,
        the comparable average, and how many comparables were used. If fewer
        than 2 comparables are found, returns a message saying so instead —
        never raises.
    """
    item_tags = set(item.get("style_tags", []))

    comparables = [
        other
        for other in listings
        if other.get("id") != item.get("id")
        and other.get("category") == item.get("category")
        and item_tags.intersection(other.get("style_tags", []))
    ]

    if len(comparables) < 2:
        return (
            "Not enough comparable listings to evaluate pricing because there "
            "are fewer than 2 similar items in the dataset."
        )

    avg = sum(other["price"] for other in comparables) / len(comparables)
    price = item["price"]
    diff = price - avg
    pct = diff / avg  # negative = cheaper than average

    if pct < -0.10:
        verdict = "Great deal"
    elif pct <= 0.10:
        verdict = "Fair price"
    else:
        verdict = "Above average"

    direction = "below" if diff < 0 else "above"
    return (
        f"At ${price:.2f}, this is ${abs(diff):.2f} {direction} the average for "
        f"comparable {item['category']} ({len(comparables)} similar listings "
        f"average ${avg:.2f}). Verdict: {verdict}."
    )


# ── Tool 5: get_trends (Stretch Feature: Trend Awareness) ─────────────────────

_TRENDS_PATH = os.path.join(os.path.dirname(__file__), "data", "trends.json")
_SIZE_BUCKETS = ["XL", "L", "M", "S"]  # check XL before L before M before S


def _size_bucket(size: str | None) -> str:
    """
    Normalize a raw size string into a trend bucket (S / M / L / XL).

    Splits on non-letters and looks for a standalone letter-size token, so
    "S/M" → "M", "M/L" → "L", and "XL (oversized)" → "XL". Waist sizes, shoe
    sizes, "One Size", and None all fall back to "overall".
    """
    if not size:
        return "overall"
    tokens = [t for t in re.split(r"[^A-Za-z]+", size.upper()) if t]
    for bucket in _SIZE_BUCKETS:
        if bucket in tokens:
            return bucket
    return "overall"


def get_trends(size: str | None) -> dict:
    """
    Surface what styles are currently trending for the user's size range.

    Reads data/trends.json — a mock snapshot of trending tags from a public
    fashion platform (Depop) — and returns the trends for the size's bucket.
    The result is fed into suggest_outfit() so the recommendation can lean into
    a current trend.

    Args:
        size: The size string parsed from the query (e.g. "M"), or None.

    Returns:
        A dict: {"size_range": str, "platform": str,
                 "trending_styles": list[str], "summary": str}.
        If trends.json is missing/corrupt or has no entry for the bucket,
        returns the same shape with trending_styles=[] and a "data unavailable"
        summary — never raises.
    """
    bucket = _size_bucket(size)

    try:
        with open(_TRENDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {
            "size_range": bucket,
            "platform": "unknown",
            "trending_styles": [],
            "summary": "Trend data is unavailable right now.",
        }

    platform = data.get("platform", "a public fashion platform")

    if bucket == "overall":
        trending = data.get("overall", [])
    else:
        trending = data.get("by_size", {}).get(bucket) or data.get("overall", [])

    if not trending:
        return {
            "size_range": bucket,
            "platform": platform,
            "trending_styles": [],
            "summary": "Trend data is unavailable right now.",
        }

    where = "right now" if bucket == "overall" else f"in size {bucket} right now"
    summary = (
        f"Trending on {platform} {where}: {', '.join(trending)}."
    )
    return {
        "size_range": bucket,
        "platform": platform,
        "trending_styles": trending,
        "summary": summary,
    }
