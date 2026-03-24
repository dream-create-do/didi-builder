"""
dede_app.py — DiDi Course Builder v1.0
Optimized pipeline: REPLACE/WITH string ops before LLM calls.
"""

import streamlit as st
import os
import sys
import traceback

st.set_page_config(page_title="DiDi Course Builder", page_icon="⚡", layout="centered")

try:
    from dede_engine import run_dede, read_imscc, parse_gmo, LLM_ACTIONS
    from style_templates import STYLES
except Exception as e:
    st.error(f"Import failed: {e}")
    st.code(traceback.format_exc())
    st.stop()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Lexend:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Lexend', sans-serif !important; }
    .header-bar { background: linear-gradient(135deg, #f59e0b, #f97316, #ef4444); border-radius: 16px; padding: 2rem; margin-bottom: 1.5rem; text-align: center; color: white; }
    .header-bar h1 { font-size: 2.2rem; font-weight: 700; margin: 0; letter-spacing: 2px; }
    .header-bar p { margin: 0.25rem 0 0 0; opacity: 0.85; font-size: 0.9rem; font-weight: 300; letter-spacing: 1.5px; text-transform: uppercase; }
    .stat-card { background: #f8f9fa; border-radius: 8px; padding: 10px; text-align: center; }
    .stat-number { font-size: 22px; font-weight: 700; color: #f59e0b; line-height: 1; }
    .stat-label { font-size: 11px; color: #888; margin-top: 4px; }
    .section-header { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1.2px; color: #888; margin: 1.5rem 0 0.5rem 0; }
    .stButton > button[kind="primary"], .stDownloadButton > button {
        background: linear-gradient(135deg, #f59e0b, #f97316) !important; color: white !important;
        border: none !important; border-radius: 10px !important; font-family: 'Lexend', sans-serif !important;
        font-weight: 600 !important; padding: 0.75rem 2rem !important; font-size: 15px !important; width: 100%; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-bar">
    <h1>⚡ DiDi</h1>
    <p>Course Builder Agent · Optimized Pipeline</p>
</div>
""", unsafe_allow_html=True)

st.markdown(
    "Upload your Canvas course export and MeMe's GMO document. DiDi will apply "
    "structural changes, content rewrites, new pages, new assignments, and "
    "design styling — then give you an updated `.imscc` to import back into Canvas."
)

# ── Step 1: Upload IMSCC ────────────────────────────────────────
st.markdown('<p class="section-header">Step 1 — Upload your course export</p>', unsafe_allow_html=True)

imscc_file = st.file_uploader("Upload Canvas .imscc export", type=["imscc", "zip"], label_visibility="collapsed")

if imscc_file is None:
    st.info("Upload a .imscc file to get started.")
    st.stop()

# ── Step 2: GMO ─────────────────────────────────────────────────
st.markdown('<p class="section-header">Step 2 — MeMe\'s GMO document (optional)</p>', unsafe_allow_html=True)
st.markdown("Paste the GMO or upload the `.md` file MeMe generated.")

gmo_text = st.text_area("Paste GMO text", height=200, placeholder="# FINAL CONSOLIDATED GMO...", label_visibility="collapsed")

gmo_file = st.file_uploader("Or upload GMO (.md or .txt)", type=["md", "txt"], label_visibility="collapsed")
if gmo_file is not None:
    try:
        gmo_text = gmo_file.read().decode("utf-8", errors="ignore")
        st.success(f"Loaded GMO: {len(gmo_text):,} characters")
    except Exception as e:
        st.error(f"Could not read GMO file: {e}")

# ── Step 3: Style ───────────────────────────────────────────────
st.markdown('<p class="section-header">Step 3 — Design style</p>', unsafe_allow_html=True)

style_options = {v: k for k, v in STYLES.items()}
selected_label = st.selectbox("Choose a design style", options=list(style_options.keys()), index=0, label_visibility="collapsed")
selected_style = style_options[selected_label]

if selected_style != "none":
    st.info(f"🎨 **{selected_label}** will be applied to homepage, overview, and assignment pages.")

# ── Step 4: API Key ─────────────────────────────────────────────
api_key = None
has_content_changes = False
if gmo_text:
    has_content_changes = any(a in gmo_text.upper() for a in ["CREATE_PAGE", "REWRITE_CONTENT", "CREATE_ASSIGNMENT", "CREATE_SECTION"])

if has_content_changes:
    st.markdown('<p class="section-header">Step 4 — API key (required for content changes)</p>', unsafe_allow_html=True)

    try:
        if hasattr(st, "secrets") and "ANTHROPIC_API_KEY" in st.secrets:
            api_key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        api_key = None

    if api_key:
        st.success("API key loaded from Streamlit secrets.")
    else:
        api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...", label_visibility="collapsed")
        if not api_key:
            st.warning("Content changes will be skipped without an API key. Structural changes and restyling will still apply.")

# ── Preview ─────────────────────────────────────────────────────
imscc_bytes = imscc_file.read()
try:
    preview = read_imscc(imscc_bytes)
    st.markdown('<p class="section-header">Original course</p>', unsafe_allow_html=True)
    identity = preview["identity"]
    st.markdown(f"### {identity.get('title', 'Unknown')} — {identity.get('code', '')}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{len(preview["modules"])}</div><div class="stat-label">Modules</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{len(preview["assignments"])}</div><div class="stat-label">Assignments</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{len(preview["wiki_pages"])}</div><div class="stat-label">Pages</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{len(preview["grading_groups"])}</div><div class="stat-label">Grade Groups</div></div>', unsafe_allow_html=True)

    if gmo_text:
        changes, _ = parse_gmo(gmo_text)
        structural = [c for c in changes if c["action"] not in LLM_ACTIONS]
        content = [c for c in changes if c["action"] in LLM_ACTIONS]
        st.markdown("")
        if structural:
            st.markdown(f"🔧 **{len(structural)}** structural change(s) (no AI needed)")
        if content:
            st.markdown(f"🧠 **{len(content)}** content change(s) (AI-powered)")
        if selected_style != "none":
            restyle_count = sum(1 for t in preview["page_types"].values() if t in ("homepage", "overview")) + len(preview["assignments"])
            st.markdown(f"🎨 **{restyle_count}** pages to restyle")

except Exception as e:
    st.error(f"Could not read IMSCC: {e}")
    with st.expander("Error details"):
        st.code(traceback.format_exc())
    st.stop()

# ── Build ────────────────────────────────────────────────────────
st.markdown('<p class="section-header">Build</p>', unsafe_allow_html=True)
build_button = st.button("⚡  Build Modified Course", type="primary", use_container_width=True)

if not build_button and "last_build" not in st.session_state:
    st.stop()

cache_key = f"{imscc_file.name}_{imscc_file.size}_{selected_style}_{len(gmo_text or '')}"
if build_button or st.session_state.get("last_build_key") != cache_key:
    progress = st.progress(0, text="Starting...")
    step_count = [0]

    def progress_cb(msg):
        step_count[0] += 1
        progress.progress(min(step_count[0] / 15, 0.99), text=msg)

    try:
        output_bytes, log_lines = run_dede(
            imscc_bytes=imscc_bytes,
            gmo_text=gmo_text or "",
            style=selected_style,
            api_key=api_key if api_key else None,
            progress_callback=progress_cb,
        )
        progress.progress(1.0, text="✅ Build complete!")
        st.session_state["last_build"] = {
            "output_bytes": output_bytes, "log": log_lines,
            "filename": imscc_file.name, "style": selected_style,
        }
        st.session_state["last_build_key"] = cache_key
    except Exception as e:
        st.error(f"Build failed: {e}")
        with st.expander("Error details"):
            st.code(traceback.format_exc())
        st.stop()

# ── Results ──────────────────────────────────────────────────────
result = st.session_state.get("last_build")
if not result:
    st.stop()

st.success("✅ Build complete!")
base_name = os.path.splitext(result["filename"])[0]
style_suffix = f"_{result['style']}" if result["style"] != "none" else ""
kb = len(result["output_bytes"]) / 1024

st.download_button(
    label=f"⬇  Download Modified Course ({kb:.1f} KB)",
    data=result["output_bytes"],
    file_name=f"{base_name}_modified{style_suffix}.imscc",
    mime="application/zip",
    use_container_width=True,
)

st.markdown("""
**To import into Canvas:**
1. Open your course → **Settings** → **Import Course Content**
2. Select **Canvas Course Export Package**
3. Upload the `.imscc` file → **Import**
""")

with st.expander("📋 Build log"):
    for line in result["log"]:
        st.text(line)

st.markdown("---")
st.caption("DiDi v1 · Optimized Course Builder · CeCe / MeMe / DiDi Suite · TOPkit / Florida SUS")
