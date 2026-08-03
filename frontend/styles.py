"""Shared color palette, CSS, and stage-status styling for the Streamlit UI."""

PALETTE = {
    "green": "#1E4D2B",
    "green_light": "#D8ECD9",
    "gold": "#B8860B",
    "gold_light": "#FDECC8",
    "brown": "#7B4B2A",
    "bg": "#F3F4EF",
    "text": "#1F2A1D",
    "gray": "#E5E7EB",
    "gray_text": "#6B7280",
    "red": "#B91C1C",
    "red_light": "#FBD5D5",
}

CUSTOM_CSS = f"""
<style>
.stApp {{ background-color: {PALETTE['bg']}; }}
h1, h2, h3 {{ color: {PALETTE['green']}; }}
.hero-banner {{
    background: linear-gradient(120deg, {PALETTE['green']} 0%, #2E6B3E 100%);
    padding: 22px 30px;
    border-radius: 14px;
    color: white;
    margin-bottom: 18px;
}}
.hero-banner p {{ color: #EAF3EA; margin: 4px 0 0 0; font-size: 15px; }}
.stage-card-v {{
    border-radius: 10px;
    padding: 8px 12px;
    margin-bottom: 2px;
}}
.stage-row {{ display: flex; align-items: center; gap: 8px; }}
.stage-icon-v {{ font-size: 18px; line-height: 1; }}
.stage-name-v {{ font-weight: 700; font-size: 12.5px; color: {PALETTE['text']}; line-height: 1.3; }}
.stage-badge-v {{ font-size: 9px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; }}
.stage-detail-v {{ font-size: 10.5px; color: {PALETTE['text']}; opacity: 0.75; margin-top: 2px; padding-left: 26px; }}
.arrow-v {{ text-align: center; font-size: 13px; color: {PALETTE['gray_text']}; margin: -2px 0; }}
.source-chip {{
    display: inline-block;
    background: {PALETTE['gold_light']};
    color: {PALETTE['brown']};
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    margin: 2px 4px 2px 0;
    font-weight: 600;
}}
</style>
"""

STATUS_STYLE = {
    "pending": {"bg": PALETTE["gray"], "text": PALETTE["gray_text"], "badge": "WAITING"},
    "active": {"bg": PALETTE["gold_light"], "text": PALETTE["gold"], "badge": "RUNNING…"},
    "done": {"bg": PALETTE["green_light"], "text": PALETTE["green"], "badge": "COMPLETE"},
    "error": {"bg": PALETTE["red_light"], "text": PALETTE["red"], "badge": "ERROR"},
}
