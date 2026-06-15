"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe
from utils.profile import load_profile, save_profile


# ── wardrobe selection ────────────────────────────────────────────────────────

def _resolve_wardrobe(wardrobe_choice: str) -> dict:
    """Map a radio choice to an actual wardrobe dict."""
    if wardrobe_choice == "Example wardrobe":
        return get_example_wardrobe()
    if wardrobe_choice == "My saved profile":
        # Style Profile Memory: reload the wardrobe saved in a previous session,
        # no re-entry needed.
        return load_profile()
    return get_empty_wardrobe()


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Returns five strings, mapped to the UI panels:
        (listing_text, outfit_suggestion, fit_card,   # core — the 3 required tools
         price_check, trends)                          # extras — stretch tools
    """
    # 1. Guard against an empty / whitespace-only query.
    if not user_query or not user_query.strip():
        return ("Please enter a search query.", "", "", "", "")

    # 2. Select the wardrobe based on the radio choice.
    wardrobe = _resolve_wardrobe(wardrobe_choice)

    # 3. Run the agent.
    session = run_agent(user_query, wardrobe)

    # 4. Error path — surface the message in the first panel only.
    if session["error"]:
        return (session["error"], "", "", "", "")

    # 5. Happy path — core output first: the listing chosen by search_listings.
    item = session["selected_item"]
    listing_text = (
        f"{item['title']}\n"
        f"Price: ${item['price']:g} — {item['platform']}\n"
        f"Size: {item['size']} | Condition: {item['condition']}\n"
        f"{item['description']}"
    )
    if session["loosened"]:
        listing_text += f"\n⚠️ {session['loosened']}"

    # 6. Extras (stretch tools) — shown in their own panels below the core ones.
    price_check = session.get("price_verdict") or "—"
    trends = session.get("trends") or {}
    if trends.get("trending_styles"):
        trends_text = trends["summary"]
    else:
        trends_text = "No trend data available for this size."

    return (
        listing_text,
        session["outfit_suggestion"],
        session["fit_card"],
        price_check,
        trends_text,
    )


# ── save-profile handler (Style Profile Memory) ───────────────────────────────

def handle_save_profile(wardrobe_choice: str) -> str:
    """
    Save the currently-selected wardrobe to disk so it can be reloaded as
    "My saved profile" in a future session without re-entering anything.
    """
    wardrobe = _resolve_wardrobe(wardrobe_choice)
    save_profile(wardrobe)
    count = len(wardrobe.get("items", []))
    return (
        f"✅ Saved {count} wardrobe item(s) to your profile. "
        f"Pick \"My saved profile\" next time to reuse them — no re-entry."
    )


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=[
                    "Example wardrobe",
                    "Empty wardrobe (new user)",
                    "My saved profile",
                ],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        with gr.Row():
            submit_btn = gr.Button("Find it", variant="primary")
            save_btn = gr.Button("💾 Save as my profile")

        save_status = gr.Markdown("")

        # ── CORE OUTPUT — the 3 required tools, shown first ───────────────────
        gr.Markdown("## Result")
        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found  (search_listings)",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea  (suggest_outfit)",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card  (create_fit_card)",
                lines=8,
                interactive=False,
            )

        # ── EXTRAS — stretch features, shown below the core output ────────────
        gr.Markdown("## Extras (bonus features)")
        with gr.Row():
            price_output = gr.Textbox(
                label="💰 Price check  (compare_price)",
                lines=4,
                interactive=False,
            )
            trends_output = gr.Textbox(
                label="📈 Trending now  (get_trends)",
                lines=4,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        outputs = [
            listing_output,
            outfit_output,
            fitcard_output,
            price_output,
            trends_output,
        ]
        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=outputs,
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=outputs,
        )
        save_btn.click(
            fn=handle_save_profile,
            inputs=[wardrobe_choice],
            outputs=[save_status],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
