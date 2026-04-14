import streamlit as st
import pdfplumber
import re
import nltk
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import io

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Professional CV Auditor V4", layout="wide")

# --- INISIALISASI DATA ---
@st.cache_resource
def setup_nlp():
    nltk.download('punkt', quiet=True)
    action_verbs = [
        'managed', 'developed', 'spearheaded', 'implemented', 'analyzed', 'led', 
        'increased', 'decreased', 'optimized', 'created', 'designed', 'built',
        'negotiated', 'coordinated', 'achieved', 'initiated', 'organized', 'transformed',
        'membangun', 'memimpin', 'mengelola', 'mengembangkan', 'meningkatkan', 'menganalisis'
    ]
    return action_verbs

ACTION_VERBS = setup_nlp()

# --- FUNGSI UTAMA AUDITOR ---
def calculate_tenure(text):
    year_patterns = re.findall(r'(\b20\d{2}\b)\s*[\-\–]\s*(\b20\d{2}\b|present|now|current)', text.lower())
    total_years = 0
    current_year = datetime.now().year
    
    for start, end in year_patterns:
        start_yr = int(start)
        end_yr = current_year if end in ['present', 'now', 'current'] else int(end)
        diff = end_yr - start_yr
        if 0 < diff < 40:
            total_years += diff
    return total_years

def audit_cv_final(text):
    text_clean = text.lower()
    lines = text.split('\n')
    report = {}

    # 1. ATS Parsability
    special_chars = len(re.findall(r'[^a-zA-Z0-9\s\.\,\@\+\-\(\)]', text))
    parsability = ((len(text) - special_chars) / len(text)) * 100 if len(text) > 0 else 0
    report['parsability_score'] = round(parsability, 1)

    # 2. Section Analysis
    sections = {'Experience': r'experience|pengalaman', 'Education': r'education|pendidikan', 
                'Skills': r'skills|keahlian', 'Summary': r'summary|profile|overview'}
    found_sec = [s for s, p in sections.items() if re.search(p, text_clean)]
    missing_sec = [s for s in sections.keys() if s not in found_sec]
    report['section_score'] = (len(found_sec) / len(sections)) * 100
    report['missing_sections'] = missing_sec

    # 3. Formula XYZ
    bullet_count = 0
    xyz_compliant = 0
    metrics = re.findall(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', text)
    
    for line in lines:
        clean_line = line.strip().lower()
        if re.match(r'^[\-\•\-\*]\s+', line.strip()) or len(line.strip()) > 20:
            if len(line.strip()) > 5: bullet_count += 1
            has_verb = any(verb in clean_line for verb in ACTION_VERBS)
            has_metric = any(m in clean_line for m in metrics)
            if has_verb and has_metric:
                xyz_compliant += 1
    
    report['bullet_count'] = bullet_count
    report['xyz_score'] = (xyz_compliant / bullet_count * 100) if bullet_count > 0 else 0
    report['metrics_count'] = len(metrics)

    # 4. Total Tenure
    report['total_tenure'] = calculate_tenure(text)

    # 5. Final Score
    final_score = (
        (report['parsability_score'] * 0.4) + 
        (min(report['xyz_score'] * 1.5, 100) * 0.3) + 
        (min(len(metrics) * 10, 100) * 0.2) + 
        (report['section_score'] * 0.1)
    )
    report['final_score'] = round(final_score, 1)
    
    return report

# --- FUNGSI GENERATOR PDF (A4 PROFESSIONAL LAYOUT) ---
class PDFReport(FPDF):
    def header(self):
        # Header Laporan
        self.set_font('Arial', 'B', 18)
        self.set_text_color(41, 128, 185) # Warna Biru Profesional
        self.cell(0, 10, 'ATS READINESS & CV AUDIT REPORT', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, f'Generated on: {datetime.now().strftime("%d %B %Y")}', 0, 1, 'C')
        self.line(10, 28, 200, 28)
        self.ln(10)

    def footer(self):
        # Footer Profesional dengan Gelar Baru Anda
        self.set_y(-25)
        self.line(10, 275, 200, 275)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 5, 'This automated audit report is strictly evaluated based on enterprise ATS standards.', 0, 1, 'C')
        self.set_font('Arial', 'B', 9)
        self.set_text_color(44, 62, 80)
        # --- PERUBAHAN GELAR ADA DI BARIS BAWAH INI ---
        self.cell(0, 5, 'Audit Conducted by: Dany Fendika - ATS Readiness Specialist & HR Data Analyst', 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.cell(0, 5, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(report_data):
    pdf = PDFReport(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    
    # Skor Utama
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, '1. OVERALL EVALUATION', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(50, 8, 'Final ATS Score:', 0, 0)
    
    # Warna skor berdasarkan nilai
    if report_data['final_score'] >= 80: pdf.set_text_color(39, 174, 96) # Hijau
    elif report_data['final_score'] >= 50: pdf.set_text_color(241, 196, 15) # Kuning
    else: pdf.set_text_color(192, 57, 43) # Merah
    
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 8, f"{report_data['final_score']} / 100", 0, 1)
    
    pdf.ln(5)
    
    # Analisis Metrik
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, '2. DETAILED METRICS', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(80, 8, f"- ATS Parsability (Text Readability):", 0, 0)
    pdf.cell(0, 8, f"{report_data['parsability_score']}%", 0, 1)
    
    pdf.cell(80, 8, f"- Quantifiable Metrics Found:", 0, 0)
    pdf.cell(0, 8, f"{report_data['metrics_count']} Data Points", 0, 1)
    
    pdf.cell(80, 8, f"- Est. Career Tenure Detected:", 0, 0)
    pdf.cell(0, 8, f"{report_data['total_tenure']} Years", 0, 1)
    
    pdf.cell(80, 8, f"- Sentence Quality (Google XYZ):", 0, 0)
    pdf.cell(0, 8, f"{int(report_data['xyz_score'])}% Strong", 0, 1)
    
    pdf.ln(5)
    
    # Rekomendasi
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, '3. STRATEGIC RECOMMENDATIONS', 0, 1, 'L')
    
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(50, 50, 50)
    
    if report_data['missing_sections']:
        pdf.multi_cell(0, 6, f"[!] Missing Sections: Please add the following standard headers to your CV: {', '.join(report_data['missing_sections'])}.")
    else:
        pdf.multi_cell(0, 6, "[+] Structure: Excellent. All standard sections are present.")
        
    if report_data['xyz_score'] < 40:
        pdf.multi_cell(0, 6, "[!] Content: Your bullet points are weak. Use the format: [Action Verb] + [Task Context] + [Metric/Number] to stand out.")
        
    if report_data['parsability_score'] < 85:
        pdf.multi_cell(0, 6, "[!] Formatting: The system struggled to read some text. Avoid 2-column designs, tables, or non-standard fonts.")
    elif report_data['parsability_score'] >= 85:
        pdf.multi_cell(0, 6, "[+] Formatting: Good text extraction. Your layout is ATS-friendly.")

    # Output to Bytes
    return bytes(pdf.output(dest='S'))

# --- UI STREAMLIT ---
st.title("🚀 Professional CV Auditor & Dashboard V4")
st.markdown("Sistem audit CV independen. Evaluasi anatomi dokumen Anda berdasarkan standar *Human Capital*.")

uploaded_file = st.file_uploader("Upload CV PDF Anda di sini", type=["pdf"])

if uploaded_file:
    with st.spinner("Mengaudit dokumen..."):
        with pdfplumber.open(uploaded_file) as pdf:
            raw_text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        
        if raw_text:
            res = audit_cv_final(raw_text)
            
            # Tampilan Dashboard
            col_chart, col_stats = st.columns([2, 1])
            with col_chart:
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = res['final_score'],
                    title = {'text': "Overall ATS Readiness Score"},
                    gauge = {
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "#2ecc71"},
                        'steps': [
                            {'range': [0, 50], 'color': "#e74c3c"},
                            {'range': [50, 80], 'color': "#f1c40f"},
                            {'range': [80, 100], 'color': "#2ecc71"}]
                    }
                ))
                st.plotly_chart(fig, use_container_width=True)

            with col_stats:
                st.write("### 📊 Quick Stats")
                st.metric("Estimasi Pengalaman", f"± {res['total_tenure']} Tahun")
                st.metric("Metrik (Angka)", f"{res['metrics_count']} Data")
                st.metric("Kualitas Kalimat", f"{int(res['xyz_score'])}%")

            st.divider()

            # --- FITUR DOWNLOAD PDF ---
            st.subheader("📄 Ekspor Laporan Audit")
            st.markdown("Unduh hasil audit ini dalam format PDF resmi sebagai referensi perbaikan CV Anda.")
            
            # Generate PDF di latar belakang
            pdf_bytes = create_pdf(res)
            
            st.download_button(
                label="⬇️ Download PDF Audit Report",
                data=pdf_bytes,
                file_name=f"CV_Audit_Report_by_DanyFendika.pdf",
                mime="application/pdf",
                type="primary"
            )
            
            st.divider()
            
            st.subheader("🛠️ X-Ray Vision (Teks Mentah)")
            with st.expander("Lihat bagaimana mesin ATS membaca CV Anda"):
                st.code(raw_text, language="text")

        else:
            st.error("Gagal membaca teks. Pastikan dokumen bukan hasil scan atau berbentuk gambar.")
