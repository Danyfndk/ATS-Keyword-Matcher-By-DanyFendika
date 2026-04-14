import streamlit as st
import pdfplumber
import re
import nltk
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import io

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Professional CV Auditor V7", page_icon="📑", layout="wide")

# --- INISIALISASI DATA ---
@st.cache_resource
def setup_nlp():
    nltk.download('punkt', quiet=True)
    # Kamus Action Verbs Komprehensif (EN & ID)
    return [
        'manage', 'managed', 'develop', 'developed', 'spearhead', 'spearheaded', 
        'implement', 'implemented', 'analyze', 'analyzed', 'lead', 'led', 
        'increase', 'increased', 'decrease', 'decreased', 'optimize', 'optimized', 
        'create', 'created', 'design', 'designed', 'build', 'built',
        'negotiate', 'negotiated', 'coordinate', 'coordinated', 'achieve', 'achieved', 
        'initiate', 'initiated', 'organize', 'organized', 'transform', 'transformed',
        'assist', 'assisted', 'monitor', 'monitored', 'oversee', 'oversaw', 'maintain', 'maintained',
        'membangun', 'memimpin', 'mengelola', 'mengembangkan', 'meningkatkan', 'menganalisis'
    ]

ACTION_VERBS = setup_nlp()

# --- FUNGSI LOGIKA (BACKEND) ---

def calculate_tenure(text):
    year_patterns = re.findall(r'(\b20\d{2}\b)\s*[\-\–]\s*(\b20\d{2}\b|present|now|current)', text.lower())
    total_years = 0
    current_year = datetime.now().year
    for start, end in year_patterns:
        start_yr = int(start)
        end_yr = current_year if end in ['present', 'now', 'current'] else int(end)
        diff = end_yr - start_yr
        if 0 < diff < 40: total_years += diff
    return total_years

def audit_cv_final(text):
    text_clean = text.lower()
    lines = text.split('\n')
    report = {}

    # 1. Parsability
    special_chars = len(re.findall(r'[^a-zA-Z0-9\s\.\,\@\+\-\(\)]', text))
    parsability = ((len(text) - special_chars) / len(text)) * 100 if len(text) > 0 else 0
    report['parsability_score'] = round(parsability, 1)

    # 2. Sections
    sections = {'Experience': r'experience|pengalaman', 'Education': r'education|pendidikan', 
                'Skills': r'skills|keahlian', 'Summary': r'summary|profile|overview'}
    found_sec = [s for s, p in sections.items() if re.search(p, text_clean)]
    report['section_score'] = (len(found_sec) / len(sections)) * 100
    report['missing_sections'] = [s for s in sections.keys() if s not in found_sec]

    # 3. XYZ Logic (Partial Scoring 50%)
    valid_lines = 0
    score_per_line = 0
    metrics = re.findall(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', text)
    for line in lines:
        if len(line.strip()) > 30: 
            valid_lines += 1
            words = set(re.findall(r'\b\w+\b', line.lower()))
            has_verb = any(v in words for v in ACTION_VERBS)
            has_metric = any(m in line for m in metrics)
            if has_verb and has_metric: score_per_line += 1.0
            elif has_verb or has_metric: score_per_line += 0.5
                
    report['xyz_score'] = (score_per_line / valid_lines * 100) if valid_lines > 0 else 0
    report['metrics_count'] = len(metrics)
    report['total_tenure'] = calculate_tenure(text)

    # Final Weighted Score
    final_score = (report['parsability_score']*0.4) + (min(report['xyz_score']*1.5, 100)*0.3) + (min(len(metrics)*10, 100)*0.2) + (report['section_score']*0.1)
    report['final_score'] = round(final_score, 1)
    return report

# --- FUNGSI PDF GENERATOR (A4 ENTERPRISE) ---

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18)
        self.set_text_color(41, 128, 185)
        self.cell(180, 10, 'ATS READINESS & CV AUDIT REPORT', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(180, 5, f'Generated on: {datetime.now().strftime("%d %B %Y")}', 0, 1, 'C')
        self.set_draw_color(41, 128, 185)
        self.set_line_width(0.5)
        # Garis presisi di bawah header (Padding 5mm)
        self.line(15, 30, 195, 30) 
        self.ln(10)

    def footer(self):
        self.set_y(-25)
        self.set_draw_color(189, 195, 199)
        self.line(15, 275, 195, 275) # Garis Footer
        self.set_y(-21)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(180, 4, 'Evaluated based on Global Enterprise ATS Standards and Google XYZ Formula.', 0, 1, 'C')
        self.set_font('Arial', 'B', 9)
        self.set_text_color(44, 62, 80)
        self.cell(180, 5, 'Audit Conducted by: Dany Fendika - ATS Readiness Specialist & HR Data Analyst', 0, 1, 'C')
        self.cell(180, 4, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(report_data, raw_text):
    pdf = PDFReport(orientation='P', unit='mm', format='A4')
    pdf.set_margins(15, 20, 15)
    pdf.set_auto_page_break(auto=True, margin=30)
    pdf.add_page()
    
    # --- SECTION 1: OVERALL SCORECARD ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 13)
    pdf.cell(180, 10, ' 1. OVERALL EVALUATION', 0, 1, 'L', fill=True)
    pdf.ln(5)
    
    score = report_data['final_score']
    color = (39, 174, 96) if score >= 80 else (230, 126, 34) if score >= 50 else (192, 57, 43)
    pdf.set_text_color(*color)
    pdf.set_font('Arial', 'B', 32)
    pdf.cell(180, 15, f"{score} / 100", 0, 1, 'C')
    pdf.ln(8)
    
    # Global Benchmark Matrix
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(180, 8, 'GLOBAL ATS BENCHMARK REFERENCE:', 0, 1, 'L')
    pdf.set_font('Arial', '', 9)
    matrix = [
        (233, 247, 239, "80-100%", "EXCELLENT: Ideal & High Probability."),
        (253, 242, 233, "50-79%", "FAIR: Optimization Recommended."),
        (250, 224, 228, "0-49%", "POOR: High Risk of Rejection.")
    ]
    for r,g,b, rng, txt in matrix:
        pdf.set_fill_color(r,g,b)
        pdf.cell(35, 7, rng, 1, 0, 'C', fill=True)
        pdf.cell(145, 7, f" {txt}", 1, 1, 'L')
    pdf.ln(8)

    # --- SECTION 2: PERFORMANCE METRICS & NOTES ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 13)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 10, ' 2. PERFORMANCE METRICS & ANALYSIS', 0, 1, 'L', fill=True)
    pdf.ln(4)
    
    metrics_info = [
        (f"A. ATS Parsability: {report_data['parsability_score']}%", "Note: Semakin tinggi skor, semakin aman CV dari risiko 'rusak' saat diekstrak ATS."),
        (f"B. Kualitas Kalimat (XYZ): {int(report_data['xyz_score'])}%", f"Note: Rasio penggunaan Action Verb & Metrik. Skor {int(report_data['xyz_score'])}% berarti hanya sebagian kalimat memenuhi formula. Poin 50% diberikan jika baris hanya mengandung Action Verb tanpa angka."),
        (f"C. Quantifiable Metrics: {report_data['metrics_count']} Data Points", f"Note: Ditemukan {report_data['metrics_count']} angka/persentase. Idealnya CV memiliki 10-20+ metrik pencapaian (contoh: 'Meningkatkan penjualan 20%')."),
        (f"D. Est. Career Tenure: {report_data['total_tenure']} Years", "Note: Total masa kerja yang berhasil dikalkulasi sistem secara otomatis dari format tanggal di CV.")
    ]
    for title, note in metrics_info:
        pdf.set_font('Arial', 'B', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(180, 6, title, 0, 1)
        pdf.set_font('Arial', 'I', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(180, 5, note)
        pdf.ln(3)

    # --- SECTION 3: DIAGNOSTIC ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 13)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 10, ' 3. DIAGNOSTIC FINDINGS & STANDARDS', 0, 1, 'L', fill=True)
    pdf.ln(4)
    
    # Pilar Header
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(0,0,0)
    pdf.cell(180, 6, "I. KELENGKAPAN STRUKTUR (4 PILAR HEADER)", 0, 1)
    pdf.set_font('Arial', '', 10)
    if report_data['missing_sections']:
        pdf.set_text_color(192, 57, 43)
        pdf.multi_cell(180, 5, f"[-] MISSING: Tambahkan header {', '.join(report_data['missing_sections'])}.")
    else:
        pdf.set_text_color(39, 174, 96)
        pdf.multi_cell(180, 5, "[+] STRUCTURE: Seluruh header wajib (Summary, Experience, Education, Skills) terdeteksi.")
    
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(180, 4.5, "INFO: Berdasarkan standar global Human Capital, CV wajib memiliki 4 pilar di atas sebagai 'peta' data bagi mesin ATS.")
    pdf.ln(5)

    # --- PAGE 2: X-RAY VISION ---
    pdf.add_page()
    pdf.set_fill_color(44, 62, 80)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(180, 10, ' X-RAY VISION: RAW DATA EXTRACTION', 0, 1, 'C', fill=True)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(192, 57, 43)
    pdf.multi_cell(180, 5, "WARNING: Teks di bawah adalah tampilan murni sistem. Jika berantakan/menyatu antar kolom, data Anda GAGAL tersimpan dengan benar di database perusahaan.")
    pdf.ln(5)
    pdf.set_font('Courier', '', 8)
    pdf.set_text_color(50, 50, 50)
    pdf.set_fill_color(250, 250, 250)
    # Proteksi karakter encoding
    safe_text = raw_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(180, 4, safe_text[:4000], fill=True)

    return bytes(pdf.output(dest='S'))

# --- WEB INTERFACE (STREAMLIT) ---

st.title("💼 Professional CV Auditor & Dashboard V7")
st.markdown("Evaluasi anatomi dokumen CV Anda berdasarkan standar global **Human Capital**.")

with st.container(border=True):
    uploaded_file = st.file_uploader("Upload CV PDF", type=["pdf"])

if uploaded_file:
    with st.spinner("Menganalisis dokumen..."):
        with pdfplumber.open(uploaded_file) as pdf:
            raw_text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        
        if raw_text:
            res = audit_cv_final(raw_text)
            
            # --- ROW 1: SCORES ---
            c_score, c_matrix = st.columns([1.2, 1])
            with c_score:
                with st.container(border=True):
                    st.markdown("<h4 style='text-align: center;'>Overall ATS Score</h4>", unsafe_allow_html=True)
                    fig = go.Figure(go.Indicator(
                        mode = "gauge+number", value = res['final_score'],
                        gauge = {'axis': {'range': [0, 100]},
                                 'bar': {'color': "#27ae60" if res['final_score']>=80 else "#f39c12" if res['final_score']>=50 else "#c0392b"},
                                 'steps': [{'range': [0, 49], 'color': "#fadbd8"}, {'range': [80, 100], 'color': "#d5f5e3"}]}
                    ))
                    # Presisi Tinggi 230
                    fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig, use_container_width=True)
            
            with c_matrix:
                with st.container(border=True):
                    st.markdown("<h4>Benchmark Matrix</h4>", unsafe_allow_html=True)
                    st.success("**80-100%:** Excellent")
                    st.warning("**50-79%:** Fair")
                    st.error("**0-49%:** High Risk")
                    st.write("") # Padding tambahan

            # --- ROW 2: SCORECARDS ---
            st.markdown("<h4>Metrics Scorecards</h4>", unsafe_allow_html=True)
            with st.container(border=True):
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Parsability", f"{res['parsability_score']}%")
                m2.metric("XYZ Score", f"{int(res['xyz_score'])}%")
                m3.metric("Metrics", f"{res['metrics_count']}")
                m4.metric("Tenure", f"± {res['total_tenure']} Thn")

            # --- ROW 3: DIAGNOSTIC ---
            st.markdown("<h4>Diagnostic Findings</h4>", unsafe_allow_html=True)
            with st.container(border=True):
                d1, d2 = st.columns(2)
                with d1:
                    st.write("**Struktur 4 Pilar Header**")
                    if res['missing_sections']: st.error(f"Missing: {', '.join(res['missing_sections'])}")
                    else: st.success("Struktur Lengkap")
                    st.info("💡 CV wajib memiliki: Summary, Experience, Education, Skills.")
                with d2:
                    st.write("**Kualitas Konten (XYZ Formula)**")
                    if res['xyz_score'] < 50: st.error("Kalimat kurang kuat (Action Verb + Angka)")
                    else: st.success("Kalimat sudah cukup kuat")
                    st.info("💡 Masukkan lebih banyak metrik hasil kerja.")

            # --- ROW 4: EXPORT & XRAY ---
            st.write("")
            c_dl, c_xray = st.columns(2)
            with c_dl:
                with st.container(border=True):
                    st.subheader("📄 Ekspor Laporan")
                    st.write("") # Whitespace untuk presisi tinggi
                    st.write("") 
                    pdf_bytes = create_pdf(res, raw_text)
                    st.download_button("⬇️ Download PDF Report", data=pdf_bytes, file_name="CV_Audit_Premium.pdf", type="primary", use_container_width=True)
            with c_xray:
                with st.container(border=True):
                    st.subheader("🛠️ X-Ray Vision")
                    with st.expander("Teks CV yang Dibaca Mesin"):
                        st.code(raw_text)

        else:
            st.error("Teks tidak dapat diekstrak.")
