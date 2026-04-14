import streamlit as st
import pdfplumber
import re
import nltk
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="CV Auditor & ATS Readiness", page_icon="📑", layout="wide")

@st.cache_resource
def setup_nlp():
    nltk.download('punkt', quiet=True)
    return [
        'manage', 'managed', 'develop', 'developed', 'spearhead', 'spearheaded', 
        'implement', 'implemented', 'analyze', 'analyzed', 'lead', 'led', 
        'increase', 'increased', 'decrease', 'decreased', 'optimize', 'optimized', 
        'create', 'created', 'design', 'designed', 'build', 'built',
        'negotiate', 'negotiated', 'coordinate', 'coordinated', 'achieve', 'achieved', 
        'initiate', 'initiated', 'organize', 'organized', 'transform', 'transformed',
        'assist', 'assisted', 'monitor', 'monitored', 'oversee', 'oversaw', 'maintain', 'maintained'
    ]

ACTION_VERBS = setup_nlp()

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
    special_chars = len(re.findall(r'[^a-zA-Z0-9\s\.\,\@\+\-\(\)]', text))
    parsability = ((len(text) - special_chars) / len(text)) * 100 if len(text) > 0 else 0
    report['parsability_score'] = round(parsability, 1)
    sections = {'Experience': r'experience|pengalaman', 'Education': r'education|pendidikan', 
                'Skills': r'skills|keahlian', 'Summary': r'summary|profile|overview'}
    found_sec = [s for s, p in sections.items() if re.search(p, text_clean)]
    report['section_score'] = (len(found_sec) / len(sections)) * 100
    report['missing_sections'] = [s for s in sections.keys() if s not in found_sec]
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
    final_score = (report['parsability_score']*0.4) + (min(report['xyz_score']*1.5, 100)*0.3) + (min(len(metrics)*10, 100)*0.2) + (report['section_score']*0.1)
    report['final_score'] = round(final_score, 1)
    return report

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18)
        self.set_text_color(41, 128, 185)
        self.cell(180, 12, 'ATS READINESS & CV AUDIT REPORT', 0, 1, 'C')
        self.set_font('Arial', 'I', 9)
        self.set_text_color(100, 100, 100)
        self.cell(180, 5, f'Generated on: {datetime.now().strftime("%d %B %Y")}', 0, 1, 'C')
        # Line dengan padding lebih presisi
        self.set_draw_color(41, 128, 185)
        self.set_line_width(0.5)
        self.line(15, 32, 195, 32) 
        self.ln(12)

    def footer(self):
        self.set_y(-25)
        self.set_draw_color(189, 195, 199)
        self.line(15, 275, 195, 275)
        self.set_y(-20)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(127, 140, 141)
        self.cell(180, 4, 'Strictly evaluated based on enterprise ATS standards and Google XYZ Formula.', 0, 1, 'C')
        self.set_font('Arial', 'B', 9)
        self.set_text_color(44, 62, 80)
        self.cell(180, 5, 'Audit Conducted by: Dany Fendika - ATS Readiness Specialist & HR Data Analyst', 0, 1, 'C')
        self.cell(180, 4, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(report_data, raw_text):
    pdf = PDFReport(orientation='P', unit='mm', format='A4')
    pdf.set_margins(15, 20, 15)
    pdf.set_auto_page_break(auto=True, margin=30)
    pdf.add_page()
    
    # --- 1. OVERALL SCORE ---
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(180, 10, ' 1. OVERALL ATS READINESS SCORE', 0, 1, 'L', fill=True)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 32)
    score = report_data['final_score']
    color = (39, 174, 96) if score >= 80 else (230, 126, 34) if score >= 50 else (192, 57, 43)
    pdf.set_text_color(*color)
    pdf.cell(180, 15, f"{score} / 100", 0, 1, 'C')
    pdf.ln(10)
    
    # --- 2. GLOBAL MATRIX ---
    pdf.set_text_color(44, 62, 80)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(180, 8, 'GLOBAL ATS BENCHMARK MATRIX:', 0, 1, 'L')
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(0, 0, 0)
    data = [
        (233, 247, 239, "80-100%", "EXCELLENT: Ideal & High Probability."),
        (253, 242, 233, "50-79%", "FAIR: Optimization Recommended."),
        (250, 224, 228, "0-49%", "POOR: High Risk of Rejection.")
    ]
    for r,g,b, rng, txt in data:
        pdf.set_fill_color(r,g,b)
        pdf.cell(30, 7, rng, 1, 0, 'C', fill=True)
        pdf.cell(150, 7, txt, 1, 1, 'L')
    pdf.ln(10)

    # --- 3. METRICS ANALYSIS ---
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(180, 10, ' 2. PERFORMANCE METRICS & ANALYSIS', 0, 1, 'L', fill=True)
    pdf.ln(4)
    
    metrics_info = [
        (f"A. ATS Parsability: {report_data['parsability_score']}%", "Note: Semakin tinggi, semakin aman CV dari risiko 'rusak' saat diekstrak mesin."),
        (f"B. Kualitas Kalimat (XYZ): {int(report_data['xyz_score'])}%", "Note: Rasio penggunaan Action Verb & Metrik. Skor 50% diberikan jika hanya salah satu yang ada."),
        (f"C. Quantifiable Metrics: {report_data['metrics_count']} Data Points", "Note: Jumlah angka/persentase pencapaian. Idealnya 10-20+ poin data."),
        (f"D. Est. Career Tenure: {report_data['total_tenure']} Years", "Note: Total masa kerja yang berhasil divalidasi sistem dari format tanggal.")
    ]
    for title, note in metrics_info:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(180, 6, title, 0, 1)
        pdf.set_font('Arial', 'I', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(180, 5, note)
        pdf.ln(3)
        pdf.set_text_color(0, 0, 0)

    # --- 4. STANDARDS ---
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(180, 10, ' 3. DIAGNOSTIC FINDINGS & INDUSTRY STANDARDS', 0, 1, 'L', fill=True)
    pdf.ln(4)
    
    # Struktur
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(180, 6, "I. KELENGKAPAN STRUKTUR", 0, 1)
    pdf.set_font('Arial', '', 10)
    if report_data['missing_sections']:
        pdf.set_text_color(192, 57, 43)
        pdf.multi_cell(180, 5, f"[-] MISSING: Tambahkan header {', '.join(report_data['missing_sections'])}.")
    else:
        pdf.set_text_color(39, 174, 96)
        pdf.multi_cell(180, 5, "[+] STRUCTURE: Seluruh header wajib terdeteksi.")
    
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(180, 4.5, "INFO ATS: CV wajib memiliki 4 pilar utama: Summary, Experience, Education, dan Skills.")
    pdf.ln(4)
    
    # XYZ
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(180, 6, "II. KUALITAS KONTEN", 0, 1)
    pdf.set_font('Arial', '', 10)
    color = (39, 174, 96) if report_data['xyz_score'] >= 50 else (192, 57, 43)
    pdf.set_text_color(*color)
    status = "[+] CONTENT: Kalimat sudah cukup baik." if report_data['xyz_score'] >= 50 else "[-] CONTENT: Kalimat kurang kuat, tambahkan angka."
    pdf.multi_cell(180, 5, status)
    
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(180, 4.5, "INFO ATS: Kalimat pasif tanpa data pencapaian akan menurunkan skor kredibilitas profesional.")

    # --- X-RAY ---
    pdf.add_page()
    pdf.set_fill_color(44, 62, 80)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(180, 10, ' X-RAY VISION: RAW DATA EXTRACTION', 0, 1, 'C', fill=True)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 9)
    pdf.set_text_color(192, 57, 43)
    pdf.multi_cell(180, 5, "WARNING: Jika teks di bawah berantakan, maka sistem ATS gagal membaca data Anda secara akurat.")
    pdf.ln(5)
    pdf.set_font('Courier', '', 8)
    pdf.set_text_color(50, 50, 50)
    pdf.set_fill_color(250, 250, 250)
    safe_text = raw_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(180, 4, safe_text[:4000], fill=True)

    return bytes(pdf.output(dest='S'))

# --- WEB UI ---
st.title("💼 CV Auditor & ATS Readiness")
uploaded_file = st.file_uploader("Upload CV (PDF)", type=["pdf"])

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        raw_text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    
    if raw_text:
        res = audit_cv_final(raw_text)
        
        # Dashboard Presisi
        c_score, c_matrix = st.columns([1.2, 1])
        with c_score:
            with st.container(border=True):
                st.markdown("<h4 style='text-align: center;'>Overall ATS Score</h4>", unsafe_allow_html=True)
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number", value = res['final_score'],
                    gauge = {'axis': {'range': [0, 100]},
                             'bar': {'color': "#27ae60" if res['final_score']>=80 else "#f39c12"},
                             'steps': [{'range': [0, 49], 'color': "#fadbd8"}, {'range': [80, 100], 'color': "#d5f5e3"}]}
                ))
                fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
        
        with c_matrix:
            with st.container(border=True):
                st.markdown("<h4>Benchmark Matrix</h4>", unsafe_allow_html=True)
                st.success("80-100%: Excellent")
                st.warning("50-79%: Fair")
                st.error("0-49%: High Risk")
        
        st.markdown("<h4>Metrics Scorecards</h4>", unsafe_allow_html=True)
        with st.container(border=True):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Parsability", f"{res['parsability_score']}%")
            m2.metric("XYZ Score", f"{int(res['xyz_score'])}%")
            m3.metric("Metrics", f"{res['metrics_count']}")
            m4.metric("Tenure", f"± {res['total_tenure']} Thn")

        c_dl, c_xray = st.columns(2)
        with c_dl:
            with st.container(border=True):
                st.subheader("📄 Ekspor Laporan")
                st.write("")
                st.write("")
                pdf_bytes = create_pdf(res, raw_text)
                st.download_button("⬇️ Download PDF", data=pdf_bytes, file_name="CV_Audit.pdf", type="primary", use_container_width=True)
        
        with c_xray:
            with st.container(border=True):
                st.subheader("🛠️ X-Ray Vision")
                with st.expander("Lihat Teks Mentah"):
                    st.code(raw_text)
