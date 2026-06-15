# FitFindr

FitFindr is a small agent for shopping secondhand. You type what you want in plain
language (like "vintage graphic tee under $30, size M") and it searches a mock listings
dataset, suggests outfits using your wardrobe, and writes a caption you could actually
post. It's the three required tools — plus two stretch tools (a price check and a trend
check) — wired together by a planning loop that passes everything through one session dict.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   ├── wardrobe_schema.json   # Wardrobe format + example/empty wardrobes
│   └── trends.json            # Mock trend snapshot (stretch: trend awareness)
├── utils/
│   ├── data_loader.py         # Helpers for loading the listings + wardrobes
│   └── profile.py             # Save/load a style profile (stretch: profile memory)
├── tests/
│   └── test_tools.py          # Unit tests for the tools
├── tools.py                   # The 3 required tools + compare_price + get_trends
├── agent.py                   # The planning loop (run_agent) + session state
├── app.py                     # Gradio UI (handle_query)
├── planning.md                # The plan I wrote before coding
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Put your Groq API key in a `.env` file (free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

Then:
```bash
pytest tests/        # run the tool tests
python agent.py      # run the loop from the terminal (happy path + a no-results case)
python app.py        # launch the UI, then open the localhost URL it prints
```

The query parsing, suggest_outfit, and create_fit_card all call Groq
(llama-3.3-70b-versatile). search_listings, compare_price, and get_trends don't touch the
LLM at all — they just filter, score, and read the mock data.

## The Mock Listings Dataset

`data/listings.json` has 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` is the format the agent uses for a user's wardrobe. It has:

- `schema`: the field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items for testing
- `empty_wardrobe`: a starting template for a new user

Load the example with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

---

## Tools

The agent has five tools, all in tools.py — the three required ones plus two stretch
tools (compare_price and get_trends). Each one is a standalone function so I could test it
on its own before wiring it into the loop. Inputs and return values here match the real
function signatures.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for items matching the description, optional size, and optional price ceiling. This is the only tool that doesn't call the LLM.

**Input parameters:**
- `description` (str): keywords for what the user is looking for, e.g. "vintage graphic tee".
- `size` (str or None): size to filter by, or None to skip it. Matching is case-insensitive and a substring, so "M" matches "S/M".
- `max_price` (float or None): max price, inclusive, or None to skip it.

**What it returns:**
A list of matching listing dicts, sorted by relevance (best match first). It scores each listing by how many of the keywords show up in the title + description + style_tags, drops the ones that score 0, and sorts the rest.

**What happens if it fails or returns nothing:**
Returns an empty list. It does NOT raise an exception.

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted item and the user's wardrobe, asks the LLM for one complete outfit.

**Input parameters:**
- `new_item` (dict): a listing dict (the item the user is thinking about buying).
- `wardrobe` (dict): a wardrobe dict with an `items` key (a list of item dicts). Can be empty.
- `trends` (dict or None): optional trend dict from get_trends (stretch feature). If it has a non-empty `trending_styles` list, the prompt tells the LLM to lean into one of those trends and name it. None (or empty) → the tool behaves exactly as it did before trends existed.

**What it returns:**
A non-empty string with the outfit ideas. If the wardrobe has items it names specific pieces from it; if the wardrobe is empty it gives general styling advice for the item on its own. When trends are passed in, the suggestion explicitly calls out which trend it's leaning into.

**What happens if it fails or returns nothing:**
Empty wardrobe doesn't break it. It switches to the general-advice prompt instead of raising or returning an empty string.

### Tool 3: create_fit_card

**What it does:**
Writes a short, shareable caption for the find. Takes the outfit suggestion and the listing dict and asks the LLM for a casual OOTD post.

**Input parameters:**
- `outfit` (str): the suggestion string from suggest_outfit.
- `new_item` (dict): the listing dict for the item.

**What it returns:**
A one-sentence caption (≤25 words) that mentions the item title, price, and platform once each. It runs at a high temperature (1.2) so calling it twice on the same input gives you different captions.

**What happens if it fails or returns nothing:**
If `outfit` is empty or just whitespace, it returns the string `"Unable to create fit card: no outfit suggestion was provided."` instead of calling the LLM. It does NOT raise.

### Tool 4: compare_price *(stretch: price comparison)*

**What it does:**
Estimates whether the selected item's price is fair by comparing it to similar listings in the dataset. It builds a pool of comparable listings — every listing in the same `category` that shares at least one `style_tag` with the item (and isn't the item itself) — averages their prices, and compares the item against that average: more than 10% below → **Great deal**, within 10% either way → **Fair price**, more than 10% above → **Above average**. No LLM call — it's plain arithmetic over the data.

**Input parameters:**
- `item` (dict): the listing being evaluated (`session["selected_item"]`).
- `listings` (list[dict]): all listings to compare against, from `load_listings()`.

**What it returns:**
A string with the verdict and the reasoning behind it — the item price, the average of the comparable listings, how many comparables were used, and a verdict label. Example: `"At $18.00, this is $4.00 below the average for comparable tops (14 similar listings average $22.00). Verdict: Great deal."`

**What happens if it fails or returns nothing:**
If fewer than 2 comparable listings exist, it returns `"Not enough comparable listings to evaluate pricing because there are fewer than 2 similar items in the dataset."` instead of a verdict. It does NOT raise.

### Tool 5: get_trends *(stretch: trend awareness)*

**What it does:**
Surfaces what styles are currently trending for the user's size range, read from `data/trends.json` — a static mock snapshot of trending tags from a public fashion platform (Depop), standing in for a live posts/tags feed. There's no external API here, so it's a committed file and honestly mock, not a live source; the tags are drawn from the same vocabulary as listings.json so they line up with what's actually in the dataset. Its output feeds into suggest_outfit so the outfit recommendation leans into a current trend.

**Input parameters:**
- `size` (str or None): the size parsed from the query (e.g. "M"). It's normalized into a bucket (S / M / L / XL); waist sizes, shoe sizes, "One Size", and None all fall back to the platform-wide `overall` trends.

**What it returns:**
A dict: `{"size_range": str, "platform": str, "trending_styles": list[str], "summary": str}`. The `trending_styles` are style tags drawn from the same vocabulary as the listings, so they pair coherently with what's actually in the dataset.

**What happens if it fails or returns nothing:**
If `trends.json` is missing/corrupt or has no entry for the bucket, it returns the same dict shape with `trending_styles: []` and a `"Trend data is unavailable right now."` summary. It does NOT raise, and suggest_outfit just omits the trend line in that case.

The helpers in `utils/data_loader.py` (load_listings, get_example_wardrobe, get_empty_wardrobe) and `utils/profile.py` aren't agent tools, they just load/persist data. `utils/profile.py` is the **style profile memory** stretch feature: `save_profile(wardrobe)` writes the wardrobe dict (same schema as `get_example_wardrobe()`) to a single JSON file, `wardrobe_profile.json`, in the project root with `json.dump`, and `load_profile()` reads it back with `json.load` and a quick shape check, falling back to `get_empty_wardrobe()` if the file is missing or corrupt. Because it's just a file on disk the profile survives across sessions and restarts, so the user saves their closet once (the "Save as my profile" button in the app) and reloads it next time by picking "My saved profile" in the wardrobe selector — no re-entry. You can also see the roundtrip from the CLI: `python -m utils.profile` runs two interactions where the first saves and the second loads without re-entering anything. The file is gitignored as per-user local state. `_get_groq_client()` in tools.py builds the Groq client and raises a ValueError if GROQ_API_KEY isn't set.

## The Planning Loop

This is run_agent(query, wardrobe) in agent.py. The order of the tools is fixed, the only
real decision the loop makes is what to do when the search comes back empty (the
retry-with-fallback stretch feature).

**Step 1 -- Initialize.** _new_session(query, wardrobe) builds the session dict that holds everything for the run.

**Step 2 -- Parse the query.** Send the raw query to the LLM with a system prompt that forces JSON: `{"description": str, "size": str|null, "max_price": float|null}`. Store it in session["parsed"] and turn max_price into a float.

**Step 3 -- Search, and relax the filters if nothing comes back.** This is the branching:
- Call search_listings(description, size, max_price). If it returns results, use them.
- If it's empty AND a size was set, search again with size dropped.
- If it's STILL empty AND a max_price was set, search again with both size and price dropped.
- If after all that there are still no results, set session["error"] and return right there — suggest_outfit never runs.

**Step 4 -- Pick the item, and note how it differs from the query.** session["selected_item"] = session["search_results"][0] (the top-scored listing). Then it checks the chosen item against the original filters and, if a constraint was relaxed to find it, sets session["loosened"] to describe *the actual gap* — e.g. "no exact match — closest is size M/L instead of M" or "$45, over your $30 budget". This only flags constraints the chosen item really misses, so it never claims a filter was relaxed when the item already fits.

**Step 4.5 -- Price check (stretch).** compare_price(selected_item, load_listings()) -> session["price_verdict"]. Always returns a string, so there's no branch or early exit.

**Step 4.6 -- Trends (stretch).** get_trends(parsed size) -> session["trends"]. Always returns a dict, so no branch or early exit. Its trending_styles get passed into the next step.

**Step 5 -- Suggest an outfit.** suggest_outfit(selected_item, wardrobe, trends) -> session["outfit_suggestion"]. No branch here — the tool handles the empty wardrobe itself, and folds the trends into the prompt when they're present.

**Step 6 -- Make the fit card.** create_fit_card(outfit_suggestion, selected_item) -> session["fit_card"].

**Step 7 -- Return the session.**

The whole point of step 3 is that the agent never calls suggest_outfit with empty input.
Any path that can't find a listing sets session["error"] and returns before steps 4–6, so
the LLM tools always get a real item.

## State Management

Everything lives in one session dict that _new_session() makes at the start of the run.
There are no globals. The loop reads and writes this dict at each step, and the caller
checks it when the run is done.

```
session["query"]             -> the original query; sent to the LLM to be parsed
session["parsed"]            -> {description, size, max_price}; feeds search_listings AND get_trends (size)
session["wardrobe"]          -> set at init; passed into suggest_outfit unchanged
session["search_results"]    -> the list of listing dicts from search_listings
session["selected_item"]     -> search_results[0]; goes into compare_price, suggest_outfit, AND create_fit_card
session["price_verdict"]     -> the string from compare_price (stretch); shown next to the listing
session["trends"]            -> the dict from get_trends (stretch); its trending_styles flow into suggest_outfit, its summary is shown next to the listing
session["outfit_suggestion"] -> the string from suggest_outfit; goes into create_fit_card
session["fit_card"]          -> the string from create_fit_card; the final output
session["error"]             -> None on success, a message if it stopped early. The caller checks this first.
session["loosened"]          -> None if the chosen item matched the filters, otherwise describes the gap (e.g. "no exact match — closest is size M/L instead of M") so the UI can warn the user
```

The data flows one way (query -> parsed -> search_results -> selected_item -> price_verdict
/ trends -> outfit_suggestion -> fit_card) and the user never re-enters anything between
steps. The parsed size also flows into get_trends, whose trending_styles then flow into
suggest_outfit. The UI (handle_query in app.py) shows five panels: the three core ones — listing
(search_listings), outfit (suggest_outfit), and fit card (create_fit_card) — plus two extra
panels for the stretch tools, a "Price check" (session["price_verdict"]) and a "Trending now"
panel (session["trends"]["summary"]). If session["error"] is set it shows the message in the
listing panel and blanks the other four; otherwise it fills all five, with the loosened note
appended to the listing panel when present. The wardrobe selector has three options — Example,
Empty, and "My saved profile" — and a "Save as my profile" button persists the current
wardrobe (Style Profile Memory). The trend influence is also visible right in the outfit panel
(the suggestion names the trend it leaned into).

## Error Handling

Every tool fails quietly. It returns a value instead of raising, so one bad step doesn't
crash the whole run.

| Tool | Failure mode | What it does |
|------|-------------|----------------|
| search_listings | Nothing matches the keywords/filters | Returns `[]`. No exception. |
| run_agent (the loop) | Search is still empty after relaxing filters | Sets session["error"] to a helpful message and returns early. suggest_outfit and create_fit_card never run. |
| suggest_outfit | Wardrobe is empty | Doesn't raise. Uses a general styling-advice prompt and still returns a non-empty string. |
| create_fit_card | outfit is empty / whitespace | Returns "Unable to create fit card: no outfit suggestion was provided." No exception. |
| compare_price | Fewer than 2 comparable listings | Returns the "Not enough comparable listings..." string instead of a verdict. No exception, and the loop keeps going (the verdict is advisory). |
| get_trends | trends.json missing/corrupt or no entry for the bucket | Returns the dict shape with `trending_styles: []` and a "Trend data is unavailable right now." summary. No exception; suggest_outfit just drops the trend line. |
| load_profile / save_profile | wardrobe_profile.json missing, corrupt, or unwritable | load_profile() returns get_empty_wardrobe(); save_profile() returns without writing. Neither raises. |
| _get_groq_client | GROQ_API_KEY isn't set | Raises a ValueError. This is the one thing meant to hard-fail, since nothing LLM-based can run without a key. |
| handle_query (UI) | Empty query box | Returns "Please enter a search query." before the agent even runs. |

**A real example from testing.** The no-results query "designer ballgown size XXS under
$5" parses to description="designer ballgown", size="XXS", max_price=5.0. The loop tries
the full filters, then drops the size, then drops the price, and every search comes back
empty. I checked it directly:

```text
>>> search_listings('designer ballgown', size='XXS', max_price=5)
[]
```

So run_agent sets session["error"] = "No listings found for 'designer ballgown'. Try
different keywords." and returns without ever calling the LLM tools. test_search_empty_results
checks the empty list, test_create_fit_card_empty_outfit checks the fit-card error string,
and the three search tests all pass with `pytest -k search`.

## Spec Reflection

The spec helped me most with state management. I wrote out every session key and what it
held before I touched run_agent, so when I got to coding with Claude I had to just
fill in the steps the plan already had. There wasn't any friction in figuring out how the data moved.

Where it diverged: the early plan basically did one search and then errored out if nothing
matched. In the code I added the filter-relaxation retry instead, so the agent tries to
recover before giving up — and I refined how the relaxation is *reported*, so session["loosened"]
describes the real gap on the chosen item ("size M/L instead of M") rather than just naming
which filter was dropped. The planning specs for the stretch tools also drifted a little from
the final code (for instance compare_price compares against the whole dataset via
load_listings() rather than the search results), so I kept planning.md and the function
signatures in sync as I built.

## AI Usage

**1. The retry logic.** I gave Claude my Tool 1 spec and the load_listings signature and
asked for the keyword scoring search. For the loop I first told it to just set an error if
the search came back empty, which is what the starter said to do. I didn't like that it
gave up the second the first search was empty, so I had it change to retry with the size
filter dropped first, then the price, before showing the no-results message, and to record
what got dropped in session["loosened"] so the user knows the match isn't exact. Its first
version relaxed both filters at once and I changed it to do them one at a time, so a strict
size doesn't throw away the price filter too.

**2. The fit card temperature.** I asked Claude to write the create_fit_card prompt so it
mentions the title, price, and platform once each. The first version used the default
settings, and when I ran it twice on the same outfit I got almost the same caption both
times, which failed test_create_fit_card_varies. I bumped the temperature up to 1.2 so the
captions actually come out different, and kept the empty-outfit check returning the fixed
error string instead of calling the LLM on nothing.
