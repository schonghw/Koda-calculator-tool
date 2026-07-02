import streamlit as st
import yfinance as yf
import requests
import json

# Page configuration
st.set_page_config(page_title="Team Structured Product Pricer", layout="centered")

# --- VISUAL & STRUCTURE LAYER (CSS INJECTION) ---
st.markdown("""
<style>
    /* 1. Scale up all font properties for visibility */
    html, body, p, .stMarkdown p, [data-testid="stWidgetLabel"] p {
        font-size: 1.25rem !important;
        line-height: 1.6 !important;
    }
    input, div[data-testid="stMarkdownContainer"] {
        font-size: 1.2rem !important;
    }
    h1 { font-size: 2.5rem !important; }
    h3 { font-size: 1.75rem !important; }

    /* 2. Completely hide Streamlit's step-up (+) and step-down (-) buttons */
    button.step-up, button.step-down {
        display: none !important;
    }
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { 
        -webkit-appearance: none !important; 
        margin: 0 !important; 
    }
    input[type=number] {
        -moz-appearance: textfield !important;
    }
</style>
""", unsafe_allow_html=True)

# --- BACKEND SECRETS LOADER & PASSWORD GATE ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    correct_password = st.secrets["DESK_PASSWORD"]
except Exception:
    gemini_api_key = None
    correct_password = None

# Halt application if the password variable isn't configured in the settings
if not correct_password:
    st.error("🔑 Security Key Error: 'DESK_PASSWORD' is missing from secrets configuration.")
    st.stop()

# Initialize session state tracking
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Render the security gate if locked
if not st.session_state["authenticated"]:
    st.title("🔒 Internal Desk Gate")
    user_entry = st.text_input("Enter Desk Access Password to unlock pricer variables:", type="password")
    
    if user_entry:
        if user_entry == correct_password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ Incorrect desk password. Access denied.")
            
    st.stop()

# --- CORE APPLICATION RUNNER (ONLY ACCESSIBLE IF AUTHENTICATED) ---
st.title("📊 Equity Structured Product Calculator")
st.write("Internal team tool for pricing Accumulators, Decumulators, and FCN underlyings.")

selected_ticker = None

# --- STEP 1: IDENTIFY UNDERLYING ASSET ---
st.markdown("### 1. Identify Underlying Asset")

if gemini_api_key:
    # --- GOOGLE GEMINI AI RESOLVER ACTIVE ---
    search_query = st.text_input("Type Company Name + Optional Region (e.g., TSMC US, Tencent, Alibaba HK):", value="")
    
    if search_query:
        with st.spinner("Gemini AI is analyzing requested exchange listings..."):
            
            clean_key = gemini_api_key.strip()
            api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": clean_key
            }
            
            system_instruction = (
                "You are an expert financial data routing engineer with comprehensive, native knowledge "
                "of global equity markets and Yahoo Finance ticker suffix conventions.\n\n"
                "Your objective is to output the exact Yahoo Finance ticker symbol for the requested asset "
                "by applying this strict global routing logic:\n\n"
                "1. GEOGRAPHIC SPECIFICITY:\n"
                "   If the user query includes an explicit country, city, or exchange hint (e.g., 'Germany', 'Amsterdam', 'JP', 'London', 'HK'), "
                "   you must strictly target that specific market using its proper Yahoo Finance suffix extension "
                "   (e.g., '.DE' for XETRA/Germany, '.AS' for Amsterdam, '.L' for London, '.SW' for Switzerland, '.MI' for Milan, '.T' for Tokyo, '.HK' for Hong Kong, '.KL' for Malaysia, '.AX' for Australia).\n\n"
                "2. INTUITIVE FALLBACK (NO SUFFIX GIVEN):\n"
                "   If the user does NOT provide any country name or region hint, you MUST locate the company's absolute primary "
                "   domestic home exchange listing. You are strictly forbidden from defaulting to low-volume US Over-The-Counter (OTC), "
                "   Pink Sheets, or secondary ADR listings unless the primary home listing *is* in the US (like Apple or Microsoft).\n"
                "   - Example: 'LVMH' must resolve to 'MC.PA' (Paris primary home exchange, not LVMHF US OTC).\n"
                "   - Example: 'ASML' must resolve to 'ASML.AS' (Amsterdam primary home exchange).\n"
                "   - Example: 'SAP' must resolve to 'SAP.DE' (Frankfurt primary home exchange).\n"
                "   - Example: 'Novartis' must resolve to 'NOVN.SW' (Swiss SIX primary home exchange).\n\n"
                "3. NUMERIC TICKER EXCHANGES:\n"
                "   Remember that certain major markets use purely numeric codes on Yahoo Finance (Hong Kong uses 4-digits like '0700.HK', "
                "   Japan uses 4-digits like '7203.T', Malaysia uses 4-digits like '8583.KL'). You must perform this conversion perfectly.\n\n"
                "CRITICAL OUTPUT RULE:\n"
                "Output ONLY the raw ticker symbol string. Do not include any punctuation, markdown formatting, backticks, "
                "or conversational explanations. Your output must be instantly readable by a Python database query engine."
            )
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": f"{system_instruction}\n\nUser Query: {search_query}"
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.0 
                }
            }
            
            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=7)
                
                if response.status_code == 200:
                    response_data = response.json()
                    raw_text = response_data['candidates'][0]['content']['parts'][0]['text']
                    selected_ticker = raw_text.strip().replace("`", "").replace("'", "").upper()
                    st.caption(f"🤖 Gemini AI Resolved Search to Ticker: **{selected_ticker}**")
                else:
                    st.error(f"Google API rejected request (Status {response.status_code}). Setup backend secrets properly.")
            except Exception as e:
                st.error(f"AI connection error: {e}")
else:
    # --- FALLBACK MODE IF NO KEY IS INSTALLED ---
    st.warning("⚠️ Central AI Key missing. Please type the exact ticker manually below.")
    manual_input = st.text_input("Enter Exact Yahoo Ticker (e.g., WBC.AX, TSM, 0700.HK):", value="")
    if manual_input:
        selected_ticker = manual_input.strip().upper()

# --- STEP 2: USER TRANSACTION CONFIGURATION ---
st.markdown("---")
st.markdown("### 2. Transaction Parameters")

notional_usd = st.number_input("Notional to Invest (USD)", value=500000, step=None, format="%d")
st.markdown(f"Confirming Notional: **${notional_usd:,} USD**")

st.write("") 

col1, col2 = st.columns(2)
with col1:
    strike_pct = st.number_input("Strike %", min_value=60.00, max_value=100.00, value=90.00, step=None, format="%.2f")

with col2:
    num_days = st.number_input("Number of business days", min_value=0, max_value=262, value=251, step=None, format="%d")

st.write("") 
gearing = st.selectbox("Contract Gearing Level", options=[1, 2], format_func=lambda x: f"{x}x")

# --- STEP 3: FINANCIAL MATH ENGINE ---
if selected_ticker:
    try:
        asset = yf.Ticker(selected_ticker)
        spot_price = asset.fast_info['last_price']
        native_currency = asset.fast_info['currency'].upper()
        
        # 🛡️ THE SHIELD LAYER: Insulate the heavy company name scraper
        try:
            company_name = asset.info.get('longName', selected_ticker)
        except Exception:
            company_name = selected_ticker  # Safe fallback if Yahoo blocks the server
        
        st.success(f"Active Ticker: **{selected_ticker}** ({company_name}) | Current Spot: **{spot_price:,.2f} {native_currency}**")
        
        # Handle FX conversion layer if asset is traded outside the US
        fx_rate = 1.0
        if native_currency != "USD":
            fx_ticker_str = f"USD{native_currency}=X"
            try:
                fx_pair = yf.Ticker(fx_ticker_str)
                fx_rate = fx_pair.fast_info['last_price']
                st.caption(f"Live USD/{native_currency} rate: **{fx_rate:.4f}**")
            except Exception:
                fx_rate = st.number_input(f"FX fetch failed. Enter USD/{native_currency} rate manually:", value=1.0, format="%.4f")
        
        strike_price = spot_price * (strike_pct / 100.0)
        notional_native = notional_usd * fx_rate
        
        if num_days > 0 and strike_price > 0:
            base_shares_per_day = (notional_native / strike_price) / num_days
        else:
            base_shares_per_day = 0.0
            
        geared_shares_per_day = base_shares_per_day * gearing
        
        # --- STEP 4: DISPLAY SUMMARY ---
        st.markdown("---")
        st.markdown("### 3. Pricing & Allocation Summary")
        
        m_col1, m_col2 = st.columns(2)
        m_col1.metric(label=f"Current Spot Price ({native_currency})", value=f"{spot_price:,.2f}")
        m_col2.metric(label=f"Absolute Strike Price ({native_currency})", value=f"{strike_price:,.4f}")
        
        st.markdown("#### Execution Order Quantities")
        out_col1, out_col2 = st.columns(2)
        out_col1.metric(label="Base Allocation (1x)", value=f"{base_shares_per_day:,.2f} / day")
        out_col2.metric(label=f"Geared Allocation ({gearing}x)", value=f"{geared_shares_per_day:,.2f} / day")
        
        st.caption(f"**Audit Trail Logic:** ({notional_usd:,.2f} USD Notional × {fx_rate:.4f} FX = {notional_native:,.2f} {native_currency} Notional) ÷ {strike_price:,.4f} Strike ÷ {num_days} Days")
        
    except Exception as e:
        st.error(f"Error loading details for asset string '{selected_ticker}'. Verify the ticker symbol format matches Yahoo Finance syntax.")
else:
    st.info("Awaiting ticker identification or entry above to begin financial calculations.")
