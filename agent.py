"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

from tools import search_listings, suggest_outfit, create_fit_card, compare_price, get_trends
from utils.data_loader import load_listings

load_dotenv()

# System prompt used to LLM-parse the free-text query into structured filters.
_PARSE_SYSTEM_PROMPT = (
    "Extract the clothing description, size (or null), and max price as a "
    "float (or null) from the user query. Return JSON only, no explanation: "
    '{"description": str, "size": str|null, "max_price": float|null}'
)


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
        "loosened": None,            # set if filters were relaxed during retry
        "price_verdict": None,       # string from compare_price (stretch: price comparison)
        "trends": None,              # dict from get_trends (stretch: trend awareness)
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # ── Step 1: initialize session ────────────────────────────────────────────
    session = _new_session(query, wardrobe)

    # ── Step 2: LLM-parse the query into structured filters ───────────────────
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        response_format={"type": "json_object"},
        max_tokens=200,
    )
    parsed = json.loads(response.choices[0].message.content)
    session["parsed"] = parsed

    description = parsed["description"]
    size = parsed.get("size")
    max_price = parsed.get("max_price")
    if max_price is not None:
        max_price = float(max_price)

    no_results_msg = (
        f"No listings found for '{description}'. Try different keywords."
    )

    # ── Step 3: search, relaxing filters one at a time if nothing matches ─────
    # Try the full filters first, then drop size, then drop price. The item that
    # ends up selected is the same as before — what changed is how the relaxation
    # is *reported* (Step 4), so the note matches the item the user actually gets.
    results = search_listings(description, size, max_price)
    if not results and size is not None:
        results = search_listings(description, size=None, max_price=max_price)
    if not results and max_price is not None:
        results = search_listings(description, size=None, max_price=None)

    if not results:
        session["error"] = no_results_msg
        return session

    session["search_results"] = results

    # ── Step 4: select the top result, and note how it differs from the query ─
    item = session["search_results"][0]
    session["selected_item"] = item

    # Only flag the constraints the chosen item *actually* misses, so we never
    # claim the size filter was relaxed for an item that's already the right size.
    differences = []
    if size is not None and size.lower() not in item["size"].lower():
        differences.append(f"size {item['size']} instead of {size}")
    if max_price is not None and item["price"] > max_price:
        differences.append(f"${item['price']:g}, over your ${max_price:g} budget")
    if differences:
        session["loosened"] = (
            "no exact match — closest is " + " and ".join(differences)
        )

    # ── Step 4.5: assess the price against comparable listings (stretch) ──────
    session["price_verdict"] = compare_price(
        item=session["selected_item"],
        listings=load_listings(),
    )

    # ── Step 4.6: pull current trends for the user's size range (stretch) ─────
    session["trends"] = get_trends(size=size)

    # ── Step 5: suggest an outfit from the selected item + wardrobe + trends ──
    session["outfit_suggestion"] = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
        trends=session["trends"],
    )

    # ── Step 6: create a shareable fit card ───────────────────────────────────
    session["fit_card"] = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )

    # ── Step 7: return the completed session ──────────────────────────────────
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nPrice check: {session['price_verdict']}")
        print(f"\nTrends: {session['trends']['summary']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
