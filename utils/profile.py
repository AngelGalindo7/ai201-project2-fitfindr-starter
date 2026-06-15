"""
profile.py

Style Profile Memory (stretch feature).

Persists a user's wardrobe to a JSON file so their style preferences survive
across sessions — they don't have to re-describe their closet every time they
open FitFindr. The whole approach is one file on disk written/read as JSON:

    save_profile(wardrobe)  ->  writes the wardrobe dict to wardrobe_profile.json
    load_profile()          ->  reads it back; falls back to an empty wardrobe

The file is intentionally simple and human-readable so a user can inspect or
hand-edit their saved profile.
"""

import json
import os

from utils.data_loader import get_empty_wardrobe

# Saved next to the project root so it persists between runs.
_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "wardrobe_profile.json")


def save_profile(wardrobe: dict) -> None:
    """
    Save the user's wardrobe to wardrobe_profile.json so it loads automatically
    next session.

    Args:
        wardrobe: A wardrobe dict with an 'items' key (same schema as
                  get_example_wardrobe()).

    Returns:
        None. If the write fails for any reason it is swallowed — saving a
        profile should never crash the app — so the caller can keep going.
    """
    try:
        with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(wardrobe, f, indent=2)
    except OSError:
        # Disk/permission problem — not worth crashing the session over.
        return


def load_profile() -> dict:
    """
    Load the user's saved wardrobe from wardrobe_profile.json.

    Returns:
        The saved wardrobe dict if the file exists and parses. If the file is
        missing, corrupted, or doesn't contain an 'items' list, returns
        get_empty_wardrobe() instead — never raises.
    """
    try:
        with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
            wardrobe = json.load(f)
        # Basic shape check — anything that isn't a wardrobe falls back.
        if isinstance(wardrobe, dict) and isinstance(wardrobe.get("items"), list):
            return wardrobe
        return get_empty_wardrobe()
    except (OSError, json.JSONDecodeError):
        return get_empty_wardrobe()


# --- Quick sanity check: two interactions, second reuses the first's prefs ---
if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    # Interaction 1 — user saves their wardrobe once.
    save_profile(get_example_wardrobe())
    print("Interaction 1: saved wardrobe to profile.")

    # Interaction 2 — a *fresh* call loads it back without re-entering anything.
    loaded = load_profile()
    print(f"Interaction 2: loaded {len(loaded['items'])} items from profile "
          f"(no re-entry). First item: {loaded['items'][0]['name']}")
