import os, textwrap
from io import BytesIO
from datetime import datetime
import streamlit as st
import google.generativeai as genai
from google.cloud import translate_v2 as translate
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from google.cloud import translate_v2 as translate
# ===============================
# CONFIGURATION
# ===============================
genai.configure(api_key=os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE"))
translate_client = translate.Client()


from google.cloud import translate_v2 as translate
from google.oauth2 import service_account

TRANSLATE_KEY_PATH = r"delta-smile-472720-v5-f858d3ff2adf.json"  # <-- your real path
credentials = service_account.Credentials.from_service_account_file(TRANSLATE_KEY_PATH)
translate_client = translate.Client(credentials=credentials)


# ---- Language list (ISO code : native name) ----
LANG_OPTIONS = {
    "en": "English",
    "hi": "हिन्दी",
    "bn": "বাংলা",
    "te": "తెలుగు",
    "mr": "मराठी",
    "ta": "தமிழ்",
    "gu": "ગુજરાતી",
    "kn": "ಕನ್ನಡ",
    "ml": "മലയാളം",
    "pa": "ਪੰਜਾਬੀ",
    "or": "ଓଡ଼ିଆ",
    "as": "অসমীয়া",
    "ur": "اردو",
    "ne": "नेपाली",
    "kok": "कोंकणी",
    "mai": "मैथिली",
    "bho": "भोजपुरी",
    "brx": "बड़ो / बोरोक",
    "mni": "মৈতৈলোন্ / ꯃꯩꯇꯩꯂꯣꯟ",
    "sd": "सिन्धी / سنڌي",
    "ks": "कॉशुर / كٲشُر",
}

def tr(text: str, lang: str) -> str:
    """Translate text if target is not English."""
    if lang == "en" or not text:
        return text
    try:
        res = translate_client.translate(text, target_language=lang)
        return res["translatedText"]
    except Exception:
        return text  # fallback if unsupported

SOIL_ICONS = {
    "Black": "⚫", "Red": "🟥", "Alluvial": "🟦",
    "Laterite": "🟧", "Sandy": "🏖️", "Clayey": "🟤", "": ""
}
SEASON_ICONS = {
    "Kharif (Monsoon)": "🌧️",
    "Rabi (Winter)": "❄️",
    "Zaid (Summer)": "🌞",
    "": ""
}
STATE_LIST = sorted([
    "Andaman and Nicobar Islands","Andhra Pradesh","Arunachal Pradesh","Assam","Bihar",
    "Chandigarh","Chhattisgarh","Dadra and Nagar Haveli and Daman and Diu","Delhi","Goa",
    "Gujarat","Haryana","Himachal Pradesh","Jammu and Kashmir","Jharkhand","Karnataka",
    "Kerala","Ladakh","Lakshadweep","Madhya Pradesh","Maharashtra","Manipur","Meghalaya",
    "Mizoram","Nagaland","Odisha","Puducherry","Punjab","Rajasthan","Sikkim","Tamil Nadu",
    "Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal"
])

# ===============================
# STREAMLIT UI
# ===============================
st.set_page_config(page_title="AgriGPT Crop Recommender", page_icon="🌱", layout="wide")

# Language selector
selected_lang = st.selectbox(
    "🌐 भाषा / Language",
    options=list(LANG_OPTIONS.keys()),
    format_func=lambda c: LANG_OPTIONS[c]
)

st.title(tr("AgriGPT – Intelligent Crop Recommendation", selected_lang))
st.markdown(tr(
    "Enter any details you know (leave blanks if unsure). "
    "Gemini will infer missing info and recommend suitable crops.",
    selected_lang
))

# ---- User Inputs ----
state  = st.selectbox(tr("State", selected_lang),
                      [""] + [tr(s, selected_lang) for s in STATE_LIST])
soil   = st.selectbox(tr("Soil Type", selected_lang),
                      [""] + [tr(s, selected_lang) for s in ["Black","Red","Alluvial","Laterite","Sandy","Clayey"]])
season = st.selectbox(tr("Season", selected_lang),
                      [""] + [tr(s, selected_lang) for s in ["Kharif (Monsoon)","Rabi (Winter)","Zaid (Summer)"]])
notes  = st.text_area(tr("Additional Context (optional)", selected_lang),
                      placeholder=tr("e.g., irrigation, altitude, etc.", selected_lang))
priority = st.slider(
    tr("Focus Preference (0 = Low Water Use, 100 = High Water Use)", selected_lang),
    0, 100, 50
)

# ---- Live Summary ----
st.markdown("### " + tr("Your Current Inputs", selected_lang))
summary = f"""
**{tr('State',selected_lang)}:** {state or tr('Not specified',selected_lang)}
**{tr('Soil',selected_lang)}:** {SOIL_ICONS.get(soil,'')} {soil or tr('Not specified',selected_lang)}
**{tr('Season',selected_lang)}:** {SEASON_ICONS.get(season,'')} {season or tr('Not specified',selected_lang)}
**{tr('Priority',selected_lang)}:** {tr('Low Water Use',selected_lang) if priority<50 else tr('Balanced',selected_lang) if priority==50 else tr('High Water Use',selected_lang)}
"""
st.info(summary)

# ===============================
# GEMINI CALL
# ===============================
if st.button(tr("Recommend Crops", selected_lang)):
    with st.spinner(tr("Analyzing with Gemini...", selected_lang)):
        prompt = f"""
        You are an agriculture planning assistant.
        User provided:
        State: {state if state else "Not specified"}
        Soil Type: {soil if soil else "Not specified"}
        Season: {season if season else "Not specified"}
        Extra Notes: {notes if notes else "None"}
        User priority: {'minimize water usage' if priority < 50 else 'balanced' if priority == 50 else 'maximize water usage'}

        Tasks:
        1. If any field is missing, make reasonable assumptions based on Indian farming patterns.
        2. Recommend 3–5 suitable crops.
        3. For each crop, give:
           - Crop Name
           - Key reason (one line)
           - Ideal sowing months
           - Approx water requirement (low/medium/high)
        4. List any assumptions made.
        Return ONLY crop rows in the format:
        Crop Name | Reason | Sowing Time | Water Requirement
        (then assumptions as separate bullet points).
        """
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        result_text = response.text

    st.markdown("### " + tr("Recommended Crops", selected_lang))

    # --- Parse Gemini output ---
    lines = [ln.strip("-• ").strip() for ln in result_text.split("\n") if ln.strip()]
    
    def is_valid_crop(line: str) -> bool:
        if "|" not in line:
            return False
        parts = [p.strip() for p in line.split("|")]
        # filter out header rows explicitly
        first_col = parts[0].lower()

        return (
            len(parts) >= 2
            and not first_col.startswith("crop name")
            and not first_col.startswith("name")
        )
    crop_lines  = [ln for ln in lines if is_valid_crop(ln)]
    extra_lines = [ln for ln in lines if not is_valid_crop(ln)]

    if not crop_lines:
        st.warning(tr("Gemini did not return structured crop details. Showing raw response:", selected_lang))
        st.markdown(tr(result_text, selected_lang))
    else:
        for i, crop in enumerate(crop_lines, 1):
            parts = [p.strip("* ") for p in crop.split("|")]
            if len(parts) >= 4:
                name, reason, sowing, water = parts[:4]
                with st.expander(f"{i}. {tr(name,selected_lang)}"):
                    st.markdown(f"**{tr('Reason',selected_lang)}:** {tr(reason,selected_lang)}")
                    st.markdown(f"**{tr('Sowing Time',selected_lang)}:** {tr(sowing,selected_lang)}")
                    st.markdown(f"**{tr('Water Requirement',selected_lang)}:** {tr(water,selected_lang)}")
            else:
                st.write(tr(crop, selected_lang))

    st.markdown("---")
    st.subheader(tr("Additional Notes / Assumptions", selected_lang))
    if extra_lines:
        for ln in extra_lines:
            st.markdown(tr(ln, selected_lang))
    else:
        st.write(tr("No explicit assumptions mentioned.", selected_lang))

    # ---- Download TXT ----
    txt_data = f"AgriGPT Crop Recommendation ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n{result_text}"
    st.download_button(
        label=tr("Download Recommendation Report (TXT)", selected_lang),
        data=txt_data,
        file_name="AgriGPT_Crop_Recommendation.txt",
        mime="text/plain"
    )

    # ---- Download PDF ----
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)
    width, height = letter
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 40, "AgriGPT Crop Recommendation")
    text_obj = c.beginText(40, height - 70)
    text_obj.setFont("Helvetica", 11)
    for line in result_text.split("\n"):
        for wrap in textwrap.wrap(line, width=90):
            text_obj.textLine(wrap)
    c.drawText(text_obj)
    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    st.download_button(
        label=tr("Download Recommendation Report (PDF)", selected_lang),
        data=pdf_buffer,
        file_name="AgriGPT_Crop_Recommendation.pdf",
        mime="application/pdf"
    )

st.markdown("---")
