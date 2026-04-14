import streamlit as st
import pdfplumber
import re
import nltk
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="CV Auditor & ATS Readiness", page_icon="📑", layout="wide")

# --- INISIALISASI DATA ---
@st.cache_resource
def setup_nlp():
    nltk.download('punkt', quiet=True)
    action_verbs = [
        'manage', 'managed', 'develop', 'developed', 'spearhead', 'spearheaded', 
        'implement', 'implemented', 'analyze', 'analyzed', 'lead', 'led', 
        'increase', 'increased', 'decrease', 'decreased', 'optimize', 'optimized', 
        'create', 'created', 'design', 'designed', 'build', 'built',
        'negotiate', 'negotiated', 'coordinate', 'coordinated', 'achieve', 'achieved', 
        'initiate', 'initiated', 'organize', 'organized', 'transform', 'transformed',
        'assist', 'assisted', 'monitor', 'monitored', 'oversee', 'oversaw', 'maintain', 'maintained',
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

    # Parsability
    special_chars = len(re.findall(r'[^a-zA-Z0-9\s\.\,\@\+\-\(\)]', text))
    parsability = ((len(text) - special_chars) / len(text)) * 100 if len(text) > 0 else 0
    report['parsability_score'] = round(parsability, 1)

    # Sections
    sections = {'Experience': r'experience|pengalaman', 'Education': r'education|pendidikan', 
                'Skills': r'skills|keahlian', 'Summary': r'summary|profile|overview'}
    found_sec = [s for s, p in sections.items() if re.search(p, text_clean)]
    missing_sec = [s for s in sections.keys() if s not in found_sec]
    report['section_score'] = (len(found_sec) / len(sections)) * 100
    report['missing_sections'] = missing_sec

    # XYZ & Metrics
    valid_lines = 0
    score_per_line = 0
    metrics = re.findall(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', text)
    
    for line in lines:
        clean_line = line.strip().lower()
        if len(clean_line) > 30: 
            valid_lines += 1
            words_in_line = set(re.findall(r'\b\w+\b', clean_line))
            has_verb = any(verb in words_in_line for verb in ACTION_VERBS)
            has_metric = any(m in clean_line for m in metrics)
            
            if has_verb and has_metric: score_per_line += 1.0
            elif has_verb: score_per_line += 0.5
            elif has_metric: score_per_line += 0.5
                
    report['xyz_score'] = (score_per_line / valid_lines * 100) if valid_lines > 0 else 0
    report['metrics_count'] = len(metrics)
    report['total_tenure'] = calculate_tenure(text)

    # Final Score Weighting
    final_score = (
        (report['parsability_score'] * 0.4) + 
        (min(report['xyz_score'] * 1.5, 100) * 0.3) + 
        (min(len(metrics) * 10, 100) * 0.2) + 
        (report['section_score'] * 0.1)
    )
    report['final_score'] = round(final_score, 1)
    return report

# --- FUNGSI GENERATOR PDF (ENTERPRISE LAYOUT) ---
class PDFReport(FPDF):
    def header(self):
        # Margin Kiri 15, Kanan 15. Usable width = 180
        self.set_font('Arial', 'B', 20)
        self.set_text_color(44, 62, 80) # Navy Blue
        self.cell(180, 10, 'CV AUDIT & ATS READINESS REPORT', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.set_text_color(127, 140, 141) # Gray
        self.cell(180, 5, f'Generated on: {datetime.now().strftime("%d %B %Y")}', 0, 1, 'C')
        self.set_draw_color(189, 195, 199)
        self.line(15, 28, 195, 28) # Garis rapi sesuai margin
        self.ln(10)

    def footer(self):
        self.set_y(-25)
        self.set_draw_color(189, 195, 199)
        self.line(15, 272, 195, 272)
        self.set_y(-22)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(127, 140, 141)
        self.cell(180, 4, 'Strictly evaluated based on enterprise ATS standards and Google XYZ Formula.', 0, 1, 'C')
        self.set_font('Arial', 'B', 9)
        self.set_text_color(44, 62, 80)
        self.cell(180, 5, 'Audit Conducted by: Dany Fendika - ATS Readiness Specialist & HR Data Analyst', 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.set_text_color(127, 140, 141)
        self.cell(180, 4, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(report_data, raw_text):
    pdf = PDFReport(orientation='P', unit='mm', format='A4')
    pdf.set_margins(15, 20, 15) # Set Margin RAPI & PRESISI
    pdf.set_auto_page_break(auto=True, margin=28)
    pdf.add_page()
    
    # --- 1. SCORECARD DASHBOARD ---
    pdf.set_fill_color(236, 240, 241) # Light Cloud Gray
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 1. OVERALL ATS READINESS SCORE', 0, 1, 'L', fill=True)
    pdf.ln(5)
    
    if report_data['final_score'] >= 80: 
        pdf.set_text_color(39, 174, 96) # Green
    elif report_data['final_score'] >= 50: 
        pdf.set_text_color(230, 126, 34) # Orange/Yellow
    else: 
        pdf.set_text_color(192, 57, 43) # Red
        
    pdf.set_font('Arial', 'B', 34)
    pdf.cell(180, 15, f"{report_data['final_score']} / 100", 0, 1, 'C')
    pdf.ln(6)
    
    # --- 2. GLOBAL BENCHMARK MATRIX ---
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 6, 'GLOBAL ATS BENCHMARK MATRIX:', 0, 1, 'L')
    pdf.ln(1)
    
    pdf.set_font('Arial', 'B', 9)
    pdf.set_draw_color(200, 200, 200) # Subtle border
    # Row 1
    pdf.set_fill_color(233, 247, 239) # Soft Green
    pdf.cell(35, 7, ' 80% - 100%', border=1, align='C', fill=True)
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(145, 7, ' EXCELLENT: Probabilitas tinggi lolos ATS. Format & struktur sangat ideal.', border=1, ln=1)
    # Row 2
    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(253, 242, 233) # Soft Orange
    pdf.cell(35, 7, ' 50% - 79%', border=1, align='C', fill=True)
    pdf.set_font('Arial', '', 9)
    pdf.cell(145, 7, ' FAIR: Berisiko. Perlu perbaikan kualitas kalimat dan metrik data.', border=1, ln=1)
    # Row 3
    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(250, 224, 228) # Soft Red
    pdf.cell(35, 7, ' 0% - 49%', border=1, align='C', fill=True)
    pdf.set_font('Arial', '', 9)
    pdf.cell(145, 7, ' POOR: Risiko tinggi auto-reject. Format rusak atau minim data.', border=1, ln=1)
    pdf.ln(8)
    
    # --- 3. DETAILED METRICS ---
    pdf.set_fill_color(236, 240, 241)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 2. PERFORMANCE METRICS & ANALYSIS', 0, 1, 'L', fill=True)
    pdf.ln(4)
    
    # A. Parsability
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 5, f"A. ATS Parsability (Text Readability) : {report_data['parsability_score']}%", 0, 1)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(127, 140, 141)
    pdf.multi_cell(180, 4.5, "Note: Semakin tinggi skor, semakin aman CV dari risiko 'rusak' saat diekstrak ATS. Hindari desain 2 kolom atau penggunaan tabel.")
    pdf.ln(4)

    # B. XYZ Score
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 5, f"B. Kualitas Kalimat (Google XYZ Score) : {int(report_data['xyz_score'])}%", 0, 1)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(127, 140, 141)
    xyz_note = (
        "Note: Standar XYZ memadukan [Action Verb] + [Konteks] + [Metrik]. Sistem memberikan Poin Parsial (50%) "
        "jika kalimat Anda memiliki Action Verb namun tanpa angka. Skor 0% terjadi jika kalimat naratif pasif murni."
    )
    pdf.multi_cell(180, 4.5, xyz_note)
    pdf.ln(4)

    # C. Metrik 
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 5, f"C. Quantifiable Metrics: {report_data['metrics_count']} Data Points Found", 0, 1)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(127, 140, 141)
    pdf.multi_cell(180, 4.5, "Note: Jumlah metrik (angka/persentase) di CV Anda sebagai bukti pencapaian kerja yang nyata.")
    pdf.ln(4)

    # D. Tenure
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 5, f"D. Est. Career Tenure: {report_data['total_tenure']} Years", 0, 1)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(127, 140, 141)
    pdf.multi_cell(180, 4.5, "Note: Masa kerja yang berhasil dikalkulasi otomatis oleh mesin dari format tanggal riwayat kerja Anda.")
    pdf.ln(6)

    # --- 4. RECOMMENDATIONS ---
    pdf.set_fill_color(236, 240, 241)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 3. STRATEGIC RECOMMENDATIONS', 0, 1, 'L', fill=True)
    pdf.ln(4)
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(20, 20, 20)
    if report_data['missing_sections']:
        pdf.multi_cell(180, 5.5, f"[-] MISSING SECTIONS: Tambahkan header standar berikut agar mesin mudah memetakan data Anda: {', '.join(report_data['missing_sections'])}.")
    else:
        pdf.multi_cell(180, 5.5, "[+] STRUCTURE: Sangat baik. Seluruh header wajib telah terdeteksi oleh sistem.")
        
    pdf.ln(2)
    if report_data['xyz_score'] < 50:
        pdf.multi_cell(180, 5.5, "[-] CONTENT: Kalimat di pengalaman kerja Anda kurang kuat. Masukkan lebih banyak angka/persentase untuk menjelaskan dampak pekerjaan Anda.")
    else:
        pdf.multi_cell(180, 5.5, "[+] CONTENT: Penggunaan Action Verbs dan Metrik kuantitatif sudah cukup baik.")

    # --- HALAMAN 2: X-RAY VISION ---
    pdf.add_page()
    pdf.set_fill_color(44, 62, 80) # Navy Blue for X-Ray
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(255, 255, 255) # White
    pdf.cell(180, 10, ' X-RAY VISION: RAW DATA EXTRACTION (SYSTEM VIEW)', 0, 1, 'C', fill=True)
    pdf.ln(6)

    pdf.set_font('Arial', 'B', 9)
    pdf.set_text_color(192, 57, 43) # Red Warning
    xray_warning = (
        "WARNING: Teks di bawah ini adalah tampilan MENTAH (Raw Text) bagaimana sistem ATS membaca CV Anda. "
        "Jika teks terlihat berantakan, melompat, atau menyatu tanpa spasi (biasa terjadi pada CV desain 2 kolom/tabel), "
        "maka data Anda dipastikan GAGAL tersimpan dengan baik di database HR perusahaan."
    )
    pdf.multi_cell(180, 5, xray_warning)
    pdf.ln(4)

    # Kotak Teks Mentah
    safe_raw_text = raw_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.set_font('Courier', '', 8.5)
    pdf.set_text_color(50, 50, 50)
    pdf.set_fill_color(248, 249, 249) # Sangat abu-abu muda
    pdf.multi_cell(180, 4.5, safe_raw_text[:3500] + ("\n\n[...TEXT TRUNCATED...]" if len(safe_raw_text) > 3500 else ""), fill=True)

    return bytes(pdf.output(dest='S'))

# --- UI STREAMLIT (ENTERPRISE DASHBOARD STYLE) ---
st.title("💼 CV Auditor & ATS Readiness")
st.markdown("Evaluasi anatomi dokumen CV Anda berdasarkan standar global **Human Capital** dan **Mesin ATS**.")

with st.container(border=True):
    uploaded_file = st.file_uploader("Upload Dokumen CV (Hanya format PDF)", type=["pdf"])

if uploaded_file:
    with st.spinner("Mesin sedang mengekstrak dan mengaudit dokumen..."):
        with pdfplumber.open(uploaded_file) as pdf:
            raw_text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        
        if raw_text:
            res = audit_cv_final(raw_text)
            
            st.write("") # Spacing
            
            # --- ROW 1: SCORE & MATRIX (DENGAN PERBAIKAN TINGGI PRESISI) ---
            col_chart, col_matrix = st.columns([1.2, 1])
            
            with col_chart:
                with st.container(border=True):
                    st.markdown("<h4 style='text-align: center; color: #2C3E50;'>Overall ATS Score</h4>", unsafe_allow_html=True)
                    fig = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = res['final_score'],
                        gauge = {
                            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                            'bar': {'color': "#27ae60" if res['final_score'] >= 80 else "#f39c12" if res['final_score'] >= 50 else "#c0392b"},
                            'bgcolor': "white",
                            'borderwidth': 2,
                            'bordercolor': "gray",
                            'steps': [
                                {'range': [0, 49], 'color': "#fadbd8"},
                                {'range': [50, 79], 'color': "#fdebd0"},
                                {'range': [80, 100], 'color': "#d5f5e3"}]
                        }
                    ))
                    # --- PERBAIKAN: Tinggi gauge dikurangi (dari 250 ke 230) agar kontainer sejajar sempurna ---
                    fig.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig, use_container_width=True)

            with col_matrix:
                with st.container(border=True):
                    st.markdown("<h4 style='color: #2C3E50;'>Global Benchmark Matrix</h4>", unsafe_allow_html=True)
                    st.success("**80% - 100% (Excellent)**\n\nFormat ideal, data kuat. Probabilitas tinggi lolos mesin ATS.")
                    st.warning("**50% - 79% (Fair / Needs Optimization)**\n\nBerisiko. Strukturnya baik namun minim penggunaan kalimat ber-metrik.")
                    st.error("**0% - 49% (Poor / High Risk)**\n\nRisiko tinggi auto-reject. Mesin gagal membaca data atau format rusak.")

            # --- ROW 2: DETAILED SCORECARDS ---
            st.markdown("<h4 style='color: #2C3E50; margin-top: 15px;'>Metrics Scorecards</h4>", unsafe_allow_html=True)
            with st.container(border=True):
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Keterbacaan Teks", f"{res['parsability_score']}%", help="Persentase teks yang berhasil diekstrak tanpa simbol rusak.")
                m2.metric("Kualitas Kalimat (XYZ)", f"{int(res['xyz_score'])}%", help="Rasio penggunaan Action Verb & Angka pada pengalaman kerja.")
                m3.metric("Data/Metrik Ditemukan", f"{res['metrics_count']}", help="Jumlah angka/persentase yang valid di dalam CV.")
                m4.metric("Estimasi Masa Kerja", f"± {res['total_tenure']} Thn", help="Perhitungan otomatis dari format tanggal di CV.")

            # --- ROW 3: REPORT & X-RAY (DENGAN PERBAIKAN TINGGI PRESISI) ---
            st.write("")
            col_dl, col_xray = st.columns([1, 1])
            
            with col_dl:
                with st.container(border=True):
                    st.subheader("📄 Ekspor Laporan")
                    st.markdown("Unduh hasil audit resmi (PDF) berisi rekomendasi dan tampilan X-Ray Vision.")
                    
                    # --- PERBAIKAN: Menambahkan spasi kosong untuk menambah tinggi alami kontainer kiri agar sejajar dengan kontainer kanan ---
                    st.write("") # Spasi kosong 1
                    st.write("") # Spasi kosong 2

                    pdf_bytes = create_pdf(res, raw_text)
                    st.download_button(
                        label="⬇️ Download Enterprise PDF Report",
                        data=pdf_bytes,
                        file_name=f"CV_Audit_Report_{datetime.now().strftime('%d%b')}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )
            
            with col_xray:
                with st.container(border=True):
                    st.subheader("🛠️ X-Ray Vision")
                    with st.expander("Klik untuk melihat teks CV yang dibaca mesin", expanded=False):
                        st.info("Jika teks di bawah berantakan atau menyatu antar kolom, sistem ATS juga akan membacanya demikian.")
                        st.code(raw_text, language="text")

        else:
            st.error("Gagal membaca teks. Pastikan dokumen bukan hasil scan atau berbentuk gambar.")
