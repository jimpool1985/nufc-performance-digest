"""
NUFC Performance Department — Weekly Research Digest Automation
Runs every Monday via GitHub Actions.
Searches for the latest football science research, generates summaries
and staff takeaways, then updates the dashboard HTML automatically.
"""

import os
import json
import re
import datetime
import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
HTML_PATH = "NUFC - Performance Department Research Dashboard.html"

DATA_BLOCK_START = "// ── DATA BLOCK START"
DATA_BLOCK_END   = "// ── DATA BLOCK END"

DISCIPLINES = [
    {"id": "medicine",    "label": "Sports Medicine",           "query": "football soccer sports medicine injury prevention rehabilitation 2026"},
    {"id": "performance", "label": "Performance & S&C",         "query": "football soccer strength conditioning performance S&C training 2026"},
    {"id": "science",     "label": "Sport Science & Technology", "query": "football soccer sport science GPS load monitoring technology 2026"},
    {"id": "psychology",  "label": "Sport Psychology",          "query": "football soccer sport psychology mental performance wellbeing 2026"},
    {"id": "nutrition",   "label": "Nutrition",                 "query": "football soccer nutrition diet carbohydrate hydration athlete 2026"},
    {"id": "women",       "label": "Women's Football",          "query": "women female football soccer research performance science 2026"},
    {"id": "academy",     "label": "Academy & Youth Development","query": "youth academy football development talent young players 2026"},
]

def get_week_info():
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    week_number = monday.isocalendar()[1]
    week_label = f"Week {week_number}"
    date_label = monday.strftime("%-d %B %Y")
    return week_label, date_label

def search_research_for_discipline(client, discipline):
    """Use Claude with web search to find latest research for a discipline."""
    print(f"  Searching: {discipline['label']}...")

    prompt = f"""You are a sport science researcher working for Newcastle United FC Performance Department.

Search for the LATEST published research (past 7 days) in: {discipline['label']}

Search query focus: {discipline['query']}

Search sources including: PubMed, footballscience.net, BJSM, Science and Medicine in Football, Loughborough University, UEFA research.

Find 2-3 NEW studies published this week. For each study return ONLY a JSON array (no other text) in this exact format:

[
  {{
    "section": "{discipline['id']}",
    "badge": "New study",
    "title": "Clear, specific title of the study",
    "summary": "2-3 sentence plain English summary of what the study found, written for a Premier League performance director. Be specific about numbers, populations and findings.",
    "takeaway": "1-2 sentence direct staff takeaway — what should the performance department DO with this information? Make it actionable and specific to an elite football club.",
    "source": "Authors · Journal, Month Year",
    "link": "https://actual-url-to-the-study-or-summary"
  }}
]

IMPORTANT:
- Only include studies actually published or newly available in the past 7 days
- If fewer than 2 genuinely new studies exist this week for this discipline, return only what you find — do not fabricate
- Badge options: "New study", "Systematic review", "RCT", "Case report", "Perspective", "Open access", "Framework", "Prospective study", "Opinion", "Meta-analysis"
- Return ONLY the JSON array, no other text, no markdown code blocks"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    full_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            full_text += block.text

    try:
        clean = full_text.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```[a-z]*\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean)
        cards = json.loads(clean)
        if isinstance(cards, list):
            return cards
    except Exception as e:
        print(f"    Warning: Could not parse JSON for {discipline['label']}: {e}")
        print(f"    Raw response: {full_text[:200]}")

    return []

def load_current_html():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()

def extract_current_data(html):
    """Extract THIS_WEEK and ARCHIVE from existing HTML."""
    this_match = re.search(r"const THIS_WEEK=(\{.*?\});", html, re.DOTALL)
    arch_match  = re.search(r"const ARCHIVE=(\[.*?\]);",   html, re.DOTALL)

    this_week = json.loads(this_match.group(1)) if this_match else None
    archive   = json.loads(arch_match.group(1))  if arch_match  else []

    return this_week, archive

def build_new_html(html, new_this_week, new_archive):
    """Replace the DATA BLOCK in the HTML with new data."""
    start = html.index(DATA_BLOCK_START)
    end   = html.index(DATA_BLOCK_END) + len(DATA_BLOCK_END)

    this_json    = json.dumps(new_this_week, ensure_ascii=False)
    archive_json = json.dumps(new_archive,   ensure_ascii=False)

    new_block = (
        f"{DATA_BLOCK_START} — replaced automatically on each weekly update ——\n"
        f"// {'═' * 76}\n"
        f"const THIS_WEEK={this_json};\n"
        f"const ARCHIVE={archive_json};\n"
        f"// {'═' * 76}\n"
        f"{DATA_BLOCK_END}"
    )

    return html[:start] + new_block + html[end:]

def main():
    print("=" * 60)
    print("NUFC Performance Department — Weekly Digest Automation")
    print("=" * 60)

    week_label, date_label = get_week_info()
    print(f"\nGenerating: {week_label} — {date_label}\n")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    all_cards = []
    for discipline in DISCIPLINES:
        cards = search_research_for_discipline(client, discipline)
        print(f"    Found {len(cards)} studies for {discipline['label']}")
        all_cards.extend(cards)

    if not all_cards:
        print("\nNo studies found this week. Aborting update.")
        return

    print(f"\nTotal studies found: {len(all_cards)}")

    html = load_current_html()
    current_this_week, current_archive = extract_current_data(html)

    new_archive = current_archive
    if current_this_week and current_this_week.get("cards"):
        new_archive = [current_this_week] + current_archive
        print(f"Moved {current_this_week['week']} to archive ({len(current_this_week['cards'])} studies)")

    new_this_week = {
        "week":  week_label,
        "date":  date_label,
        "cards": all_cards
    }

    updated_html = build_new_html(html, new_this_week, new_archive)

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(updated_html)

    print(f"\n✓ Dashboard updated: {week_label} — {date_label}")
    print(f"  Studies this week : {len(all_cards)}")
    print(f"  Weeks in archive  : {len(new_archive)}")
    print("\nDone. GitHub Actions will commit and publish automatically.")

if __name__ == "__main__":
    main()
