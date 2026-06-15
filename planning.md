# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listing dataset for items matching the description, optional size, and optional price ceiling.

**Input parameters:**
- `description` (str): Key words of what the user is looking for in the listing dataset
- `size` (str): Size string to filter by, or None to skip size filtering.Matching is case-insensitive (e.g., "M" matches "S/M").
- `max_price` (float): Maximum price (inclusive), or None to skip price filtering.

**What it returns:**
A list of matching listing dicts, sorted by relevance (best match first). Each dict contains at minimum: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str), and `platform` (str).

**What happens if it fails or returns nothing:**
Returns an empty list if nothing matches it does NOT raise an exception.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

**Input parameters:**
- `new_item` (dict): A listing dict (the item the user is considering buying).
- `wardrobe` (dict): A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

**What it returns:**
A non-empty string with outfit suggestions.
        

**What happens if it fails or returns nothing:**
If the wardrobe is empty, offer general styling advice for the item rather than raising an exception or returning an empty string.
---

### Tool 3: create_fit_card

**What it does:**
Generate a short, shareable outfit caption for the thrifted find. Takes the outfit suggestion and the listing dict, then calls the LLM to produce an authentic-sounding OOTD post that mentions the item name, price, and platform naturally.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by suggest_outfit().
- `new_item` (dict): The listing dict for the thrifted item.

**What it returns:**
A real Instagram caption. It mentions the item's title, price (as a dollar amount), and platform once each, and describes the outfit vibe in specific terms.

**What happens if it fails or returns nothing:**
If `outfit` is an empty string or whitespace only, return the string `"Unable to create fit card: no outfit suggestion was provided."` — do NOT raise an exception.

---

### Additional Tools (if any)

### Tool 4: compare_price  *(Stretch Feature: Price Comparison)*

**What it does:**
Given a selected listing and the full dataset, estimates whether the price is fair by comparing it to similar items in the same category with at least one overlapping style_tag. Returns a verdict string shown alongside the listing.

**Input parameters:**
- `item` (dict): The listing dict being evaluated (from `session["selected_item"]`).
- `listings` (list[dict]): All listings from `load_listings()` (the comparison pool).

**What it returns:**
A formatted string, e.g.: `"At $22, this is $8 below the average for similar graphic tees in the dataset ($30 avg across 4 comparable listings). Great deal."` Always includes the item price, the comparison average, the sample size, and a verdict label (Great deal / Fair price / Above average).

**What happens if it fails or returns nothing:**
If fewer than 2 comparable listings are found (no items share the same category AND at least one style_tag), return `"Not enough comparable listings to evaluate pricing because there are fewer than 2 similar items in the dataset."` Do NOT raise an exception.

---

### Tool 5: Style Profile Memory  *(Stretch Feature: Style Profile Memory)*

**What it does:**
Persists the user's wardrobe to `wardrobe_profile.json` so it reloads automatically on the next session. Provides `load_profile()` to read the saved wardrobe and `save_profile(wardrobe)` to write it.

**Input parameters:**
- `load_profile()` takes no parameters.
- `wardrobe` (dict): passed to `save_profile()` — a wardrobe dict with an `'items'` key containing a list of wardrobe item dicts (same schema as `get_example_wardrobe()`).

**What it returns:**
`load_profile()` returns a wardrobe dict matching the `get_example_wardrobe()` schema, or `get_empty_wardrobe()` if the file is missing or unreadable. `save_profile(wardrobe)` returns None.

**What happens if it fails or returns nothing:**
If `wardrobe_profile.json` is missing, corrupted, or fails to parse, `load_profile()` catches the exception silently and returns `get_empty_wardrobe()` — does NOT raise. If the write fails, `save_profile()` catches the exception and returns without raising; the session continues normally.

---

### Tool 6: get_trends  *(Stretch Feature: Trend Awareness)*

**What it does:**
Surfaces what styles are currently popular for the user's size range by reading a mock snapshot of trending tags pulled from a public fashion platform (Depop). The returned trend list is then fed into `suggest_outfit` so the outfit recommendation leans into at least one current trend.

**Input parameters:**
- `size` (str | None): the size string parsed from the user's query (e.g. `"M"`). Normalized into a size bucket (S / M / L / XL); anything that doesn't map to a letter size (waist sizes, shoe sizes, "One Size", or `None`) falls back to the platform-wide `"overall"` trends.

**What it returns:**
A dict: `{"size_range": str, "platform": str, "trending_styles": list[str], "summary": str}`. `trending_styles` is a short list of style tags that overlap with the dataset's vocabulary (e.g. `["90s", "streetwear", "grunge", "graphic tee"]`) so the trend can coherently influence outfit suggestions.

**What happens if it fails or returns nothing:**
If `data/trends.json` is missing, corrupted, or has no entry for the bucket, return a dict with `trending_styles: []` and a `summary` of `"Trend data is unavailable right now."` — does NOT raise. When `trending_styles` is empty, `suggest_outfit` simply omits the trend line and behaves exactly as before.

**Data source:**
`data/trends.json` — a static, mock snapshot standing in for recent posts/tags on a public fashion platform (Depop). The project ships with mock data and no external API, so trends are read from this committed file rather than scraped live. It maps each size bucket to a list of currently-trending style tags drawn from the same vocabulary as `listings.json`.

---

## Planning Loop

**How does your agent decide which tool to call next?**

Step 1 -- Parse the query.
Send the raw user query to the LLM (Groq) with a system prompt: "Extract the clothing
description, size (or null), and max price as a float (or null). Return JSON only:
{"description": str, "size": str|null, "max_price": float|null}."
Store result in session["parsed"].

Step 2 -- Call search_listings.
Call search_listings(description, size, max_price) from session["parsed"].
Store return value in session["search_results"].

Step 3 -- Check results.
- If session["search_results"] is non-empty -> go to Step 4.

- If empty AND size was set:
    session["search_results"] = search_listings(description, size=None, max_price)
    - If non-empty -> go to Step 4.
    - If still empty AND max_price was set:
        session["search_results"] = search_listings(description, None, None)
        - If non-empty -> go to Step 4.
        - If still empty -> set session["error"], return.
    - If still empty AND max_price not set -> set session["error"], return.

- If empty AND size was NOT set AND max_price was set:
    session["search_results"] = search_listings(description, None, None)
    - If non-empty -> go to Step 4.
    - If still empty -> set session["error"], return.

- If empty AND no filters set -> set session["error"], return immediately.



Step 4 -- Select top result.
session["selected_item"] = session["search_results"][0]

Step 4.5 -- Call compare_price (Stretch Feature: Price Comparison).
compare_price(item=session["selected_item"], listings=load_listings())
Store result in session["price_verdict"].
(compare_price always returns a string so no branch or early exit needed here.)

Step 4.6 -- Call get_trends (Stretch Feature: Trend Awareness).
get_trends(size=session["parsed"]["size"])
Store result in session["trends"].
(get_trends always returns a dict so no branch or early exit needed here.)

Step 5 -- Call suggest_outfit.
suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"], trends=session["trends"])
Store result in session["outfit_suggestion"].
(suggest_outfit handles empty wardrobe internally — no branch needed here. When session["trends"]["trending_styles"] is non-empty, the prompt asks the LLM to lean into at least one trend and name it, so the trend visibly shapes the suggestion.)

Step 6 -- Call create_fit_card.
create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])
Store result in session["fit_card"].

Step 7 -- Return session.
Caller checks session["error"] first; if None, the interaction succeeded.


---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single session dict initialized by _new_session() at the start of
each run. The planning loop reads and writes this dict at each step — no global variables.

session["query"]             -> original query; sent to LLM for parsing
session["parsed"]            -> {description, size, max_price}; feeds search_listings
session["search_results"]    -> list of listing dicts from search_listings
session["selected_item"]     -> search_results[0]; passed to suggest_outfit and create_fit_card
session["wardrobe"]          -> set at init; passed to suggest_outfit unchanged
session["outfit_suggestion"] -> string from suggest_outfit; passed to create_fit_card
session["fit_card"]          -> string from create_fit_card; shown to user
session["error"]             -> None on success; set on early exit; caller checks this first
session["loosened"]          -> None if all filters held; otherwise describes what was dropped (e.g. "size filter removed") — shown to user so they know the result is a looser match
session["price_verdict"]     -> string from compare_price (Stretch Feature: Price Comparison); shown in its own "Price check" panel in the UI (and by the CLI, python agent.py)
session["trends"]            -> dict from get_trends (Stretch Feature: Trend Awareness); its trending_styles are passed into suggest_outfit (so the trend visibly shapes the outfit panel), and its summary is shown in its own "Trending now" panel in the UI (and printed by the CLI)

The user never re-enters data between steps. selected_item flows from search_results[0]
directly into both suggest_outfit and create_fit_card. The size parsed in Step 1 flows into
get_trends, whose trending_styles then flow into suggest_outfit.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set session["error"] = "No listings found for '[description]'. Try raising your budget or using different keywords." Return session immediately. suggest_outfit is never called. |
| suggest_outfit | Wardrobe is empty | Don't raise. Call LLM with general styling prompt: "Suggest 2 outfit ideas for [item title] -- what colors, silhouettes, and shoe styles pair well with it." Return that string. Planning loop continues normally. |
| create_fit_card | Outfit input is missing or incomplete | Return the string "Unable to create fit card: no outfit suggestion was provided." Do not raise. |
| compare_price | Fewer than 2 comparable listings found | Return "Not enough comparable listings to evaluate pricing because there are fewer than 2 similar items in the dataset." Do not raise. Planning loop continues normally (price verdict is advisory, not required). |
| get_trends | trends.json missing/corrupt or no entry for the size bucket | Return a dict with `trending_styles: []` and summary "Trend data is unavailable right now." Do not raise. suggest_outfit omits the trend line and behaves normally. |
| load_profile / save_profile | wardrobe_profile.json missing, corrupt, or unwritable | load_profile() returns get_empty_wardrobe(); save_profile() returns without raising. The session continues normally. |

---

## Architecture

User query
    │
    ▼
Planning Loop
    │
    │  LLM parse → session["parsed"] = {description, size, max_price}
    │
    ├─► search_listings(description, size, max_price)          ← attempt 1 (full filters)
    │       │
    │       │ results=[]  AND size was set
    │       ├──► search_listings(description, size=None, max_price)   ← attempt 2 (drop size)
    │       │       │ session["loosened"] = "size filter removed"
    │       │       │
    │       │       │ results=[]  AND max_price was set
    │       │       ├──► search_listings(description, None, None)      ← attempt 3 (drop all)
    │       │       │       │ session["loosened"] = "size and price filters removed"
    │       │       │       │
    │       │       │       │ results=[]
    │       │       │       └──► [EARLY EXIT] session["error"] = "No listings found..." → return
    │       │       │
    │       │       │ results=[item, ...]
    │       │       └──► continue ↓
    │       │
    │       │ results=[]  AND no size set  AND max_price was set
    │       ├──► search_listings(description, None, None)              ← attempt 2 (drop price)
    │       │       │ session["loosened"] = "price filter removed"
    │       │       │
    │       │       │ results=[]
    │       │       └──► [EARLY EXIT] session["error"] = "No listings found..." → return
    │       │
    │       │ results=[]  AND no filters set
    │       ├──► [EARLY EXIT] session["error"] = "No listings found..." → return
    │       │
    │       │ results=[item, ...]  (any attempt)
    │       ▼
    │   session["search_results"] = [...]
    │   session["selected_item"]  = results[0]
    │       │
    ├─► compare_price(selected_item, load_listings())   ← Stretch Feature: Price Comparison
    │       │ always returns a string — no early exit
    │   session["price_verdict"] = "Great deal / Fair price / Above average / Not enough data"
    │       │
    ├─► get_trends(parsed["size"])                       ← Stretch Feature: Trend Awareness
    │       │ always returns a dict — no early exit (empty trending_styles on data failure)
    │   session["trends"] = {size_range, platform, trending_styles, summary}
    │       │
    ├─► suggest_outfit(selected_item, wardrobe, trends)  ← trends visibly shape the suggestion
    │       │ wardrobe["items"]=[]
    │       ├──► LLM: general styling advice (no error raised)
    │       │ trends["trending_styles"] non-empty
    │       ├──► LLM: lean into a current trend and name it
    │       │
    │   session["outfit_suggestion"] = "..."
    │       │
    └─► create_fit_card(outfit_suggestion, selected_item)
            │ outfit="" → return error string (no exception)
            │
        session["fit_card"] = "..."
            │
            ▼
        Return session → caller displays selected_item + outfit_suggestion + fit_card + price_verdict + trends summary
                         (if session["loosened"] is set, caller notes which filters were dropped)


---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

- **search_listings:** Give Claude the Tool 1 spec + `load_listings()` signature. Ask for keyword scoring across title/description/style_tags, case-insensitive size matching, and price filtering. Tests: `test_search_returns_results`, `test_search_empty_results` (returns `[]`, no exception), `test_search_price_filter` (all results ≤ max_price). Run `pytest tests/` before moving on.

- **suggest_outfit:** Give Claude the Tool 2 spec + example_wardrobe from wardrobe_schema.json. Ask for two prompt branches (empty wardrobe → general advice; populated → specific pairings by name). Tests: `test_suggest_outfit_empty_wardrobe`, `test_suggest_outfit_populated_wardrobe`. Both must return a non-empty string without raising.

- **create_fit_card:** Give Claude the Tool 3 spec. Ask for a Groq prompt that includes item title, price, and platform. Tests: `test_create_fit_card_empty_outfit` (returns exact error string, no exception), `test_create_fit_card_varies` (two calls on same input return different strings; if identical, raise LLM temperature). Run `pytest tests/` before Milestone 4.

**Milestone 4 — Planning loop and state management:**

Give Claude the Planning Loop section, State Management section, and Architecture diagram. Ask it to implement `run_agent()` in agent.py and `handle_query()` in app.py. Verify: `_new_session()` is called first; query is LLM-parsed into `session["parsed"]`; early exit fires when search returns empty (suggest_outfit never called); retry drops size filter first, then price, setting `session["loosened"]` each time. Run both `__main__` test cases in agent.py and print the full session dict to confirm every key from State Management is present.

**Stretch Feature: Price Comparison Tool (compare_price):**

Give Claude the Tool 4 spec + listings schema from data_loader.py. Ask it to implement `compare_price()` in tools.py: filter by same category AND ≥1 overlapping style_tag, require ≥2 comparables, return a formatted string with item price, average, sample size, and verdict label. Also add `session["price_verdict"] = None` to `_new_session()` and wire the call at Step 4.5 in `run_agent()`. Tests: `test_compare_price_enough_data` (result contains "$"), `test_compare_price_too_few_comparisons` (returns "Not enough comparable" string). Run `pytest tests/`.

**Stretch Feature: Style Profile Memory:**

Give Claude the goal: persist the wardrobe to `wardrobe_profile.json` so it loads automatically next session. Ask for two functions in a new file `utils/profile.py`: `load_profile()` (reads the file; returns `get_empty_wardrobe()` if missing or corrupted) and `save_profile(wardrobe)` (writes to the file). In app.py, add a "My saved profile" wardrobe option wired to `load_profile()` and a "Save as my profile" button wired to `save_profile()`. Verify: save then load returns the same dict (`test_profile_save_then_load_roundtrips`); missing file returns empty wardrobe without raising.

**Stretch Feature: Trend Awareness Tool (get_trends):**

Give Claude the Tool 6 spec + the style_tag vocabulary from listings.json. Ask it to (1) author `data/trends.json` mapping size buckets (S/M/L/XL/overall) to trending style tags drawn from that vocabulary, (2) implement `get_trends(size)` in tools.py that normalizes the size to a bucket, reads the file, and returns the trend dict (empty trending_styles on any failure, no exception), and (3) extend `suggest_outfit(new_item, wardrobe, trends=None)` so a non-empty `trending_styles` adds a prompt line asking the LLM to lean into one trend and name it. Wire `get_trends` at Step 4.6 in run_agent and pass session["trends"] into suggest_outfit. Verify: the returned outfit text references a trending tag; missing trends.json returns empty trending_styles without raising; existing suggest_outfit tests (called without trends) still pass.

---

## A Complete Interaction (Step by Step)

search_listings always runs first. If it comes back empty the agent stops and tells the user to adjust their filters. It won't pass nothing into suggest_outfit. If something is found, that item goes into suggest_outfit (specific outfit combos if a wardrobe exists, general advice if not), and that suggestion feeds into create_fit_card for the caption.

**Example user query:** "I'm looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers."

**Step 1:**
LLM parses the query → description="vintage graphic tee", size="M", max_price=30.0. Calls search_listings with those values. Results go into session["search_results"].

**Step 2:**
If nothing matches, session["error"] gets set ("No listings found for 'vintage graphic tee' under $30. Try raising your budget or removing filters.") and the agent returns immediately. suggest_outfit is never called with empty input.

If results come back, session["selected_item"] = results[0], then suggest_outfit is called with the item and the user's wardrobe.

**Step 3:**
Empty wardrobe → general styling advice. Populated wardrobe → specific outfit combos using actual wardrobe item names. Either way suggest_outfit always returns a non-empty string.

That string goes into session["outfit_suggestion"] and straight into create_fit_card. LLM writes a 2–4 sentence caption → session["fit_card"].

**Final output to user:**
Three panels: listing details (title, price, platform, condition) from session["selected_item"], the outfit suggestion, and the fit card.
