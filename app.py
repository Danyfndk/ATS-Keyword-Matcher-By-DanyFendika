import streamlit as st
import pdfplumber
import re
import nltk
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Professional CV Auditor V4", layout="wide")

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

    special_chars = len(re.findall(r'[^a-zA-Z0-9\s\.\,\@\+\-\(\)]', text))
    parsability = ((len(text) - special_chars) / len(text)) * 100 if len(text) > 0 else 0
    report['parsability_score'] = round(parsability, 1)

    sections = {'Experience': r'experience|pengalaman', 'Education': r'education|pendidikan', 
                'Skills': r'skills|keahlian', 'Summary': r'summary|profile|overview'}
    found_sec = [s for s, p in sections.items() if re.search(p, text_clean)]
    missing_sec = [s for s in sections.keys() if s not in found_sec]
    report['section_score'] = (len(found_sec) / len(sections)) * 100
    report['missing_sections'] = missing_sec

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

    final_score = (
        (report['parsability_score'] * 0.4) + 
        (min(report['xyz_score'] * 1.5, 100) * 0.3) + 
        (min(len(metrics) * 10, 100) * 0.2) + 
        (report['section_score'] * 0.1)
    )
    report['final_score'] = round(final_score, 1)
    return report

# --- FUNGSI GENERATOR PDF (DASHBOARD LAYOUT) ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18)
        self.set_text_color(41, 128, 185) 
        self.cell(190, 8, 'ATS READINESS & CV AUDIT REPORT', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.cell(190, 5, f'Generated on: {datetime.now().strftime("%d %B %Y")}', 0, 1, 'C')
        self.line(10, 25, 200, 25)
        self.ln(8)

    def footer(self):
        # PERBAIKAN Y-COORDINATE AGAR TIDAK BERTUMPUK
        self.set_y(-22)
        self.line(10, 275, 200, 275)
        self.set_y(-20)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(190, 4, 'This automated audit report is strictly evaluated based on enterprise ATS standards.', 0, 1, 'C')
        self.set_font('Arial', 'B', 9)
        self.set_text_color(44, 62, 80)
        self.cell(190, 5, 'Audit Conducted by: Dany Fendika - ATS Readiness Specialist & HR Data Analyst', 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.cell(190, 4, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(report_data, raw_text):
    pdf = PDFReport(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()
    
    # --- SECTION 1: OVERALL SCORE ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(190, 10, ' 1. OVERALL EVALUATION', 0, 1, 'L', fill=True)
    pdf.ln(3)
    
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(50, 8, 'Final ATS Score:', 0, 0)
    
    if report_data['final_score'] >= 80: pdf.set_text_color(39, 174, 96)
    elif report_data['final_score'] >= 50: pdf.set_text_color(241, 196, 15)
    else: pdf.set_text_color(192, 57, 43)
    
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(140, 8, f"{report_data['final_score']} / 100", 0, 1)
    pdf.ln(5)
    
    # --- SECTION 2: DETAILED METRICS & INLINE EXPLANATION ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(190, 10, ' 2. METRICS ANALYSIS & HOW TO READ', 0, 1, 'L', fill=True)
    pdf.ln(3)
    
    # A. ATS Parsability
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 6, f"A. ATS Parsability (Text Readability) : {report_data['parsability_score']}%", 0, 1)
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(190, 5, "Note: Menunjukkan seberapa baik mesin membaca karakter di CV Anda. Semakin tinggi skor, semakin aman CV Anda dari risiko 'rusak' saat di-parsing oleh sistem perusahaan. Hindari kolom ganda, tabel rumit, atau font tidak standar.")
    pdf.ln(4)

    # B. Sentence Quality (XYZ Score)
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 6, f"B. Kualitas Kalimat (Google XYZ Score) : {int(report_data['xyz_score'])}%", 0, 1)
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(80, 80, 80)
    xyz_note = (
        "Note: Standar 'Formula XYZ Google' memadukan [Action Verb] + [Konteks Pekerjaan] + [Metrik/Angka]. "
        "Sistem menerapkan Penilaian Parsial (50% Poin) apabila dalam satu kalimat deskripsi kerja Anda "
        "sudah menggunakan Action Verb (contoh: 'Manage', 'Develop') TETAPI tidak menyertakan "
        "angka/metrik pencapaian sama sekali. Skor 0% pada suatu baris terjadi jika kalimat berbentuk pasif tanpa Action Verb dan tanpa Angka."
    )
    pdf.multi_cell(190, 5, xyz_note)
    pdf.ln(4)

    # C. Data & Tenure
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(95, 6, f"C. Quantifiable Metrics: {report_data['metrics_count']} Data Points", 0, 0)
    pdf.cell(95, 6, f"D. Est. Career Tenure: {report_data['total_tenure']} Years", 0, 1)
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(190, 5, "Note: Metrik adalah jumlah angka/persentase yang ditemukan sebagai bukti kinerja. Tenure adalah total jam terbang (masa kerja) yang berhasil dikalkulasi mesin dari format tanggal di CV Anda.")
    pdf.ln(5)

    # --- SECTION 3: RECOMMENDATIONS ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(190, 10, ' 3. STRATEGIC RECOMMENDATIONS', 0, 1, 'L', fill=True)
    pdf.ln(3)
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(50, 50, 50)
    if report_data['missing_sections']:
        pdf.multi_cell(190, 6, f"[!] Missing Sections: Tambahkan header standar berikut ke CV Anda agar mesin mudah melakukan pemetaan data: {', '.join(report_data['missing_sections'])}.")
    else:
        pdf.multi_cell(190, 6, "[+] Structure: Sangat baik. Seluruh header wajib (Experience, Education, Skills, Summary) telah terdeteksi.")
        
    if report_data['xyz_score'] < 50:
        pdf.multi_cell(190, 6, "[!] Content: Kalimat di pengalaman kerja Anda masih kurang kuat/kurang data. Ubah format menjadi poin-poin terukur.")

    # --- HALAMAN BARU: X-RAY VISION ---
    pdf.add_page()
    pdf.set_fill_color(41, 128, 185) # Biru Gelap
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(255, 255, 255) # Putih
    pdf.cell(190, 10, ' X-RAY VISION: APA YANG DIBACA MESIN (RAW TEXT)', 0, 1, 'C', fill=True)
    pdf.ln(5)

    pdf.set_font('Arial', 'I', 10)
    pdf.set_text_color(192, 57, 43) # Merah Peringatan
    xray_warning = (
        "PERHATIAN: Berikut adalah teks mentah (raw text) persis seperti yang diekstrak oleh sistem ATS "
        "dari file PDF Anda. Jika teks di bawah ini terlihat berantakan, menyatu tanpa spasi yang jelas, "
        "atau bagian kiri dan kanan saling menabrak, maka seperti itulah rekruter/sistem ATS melihat CV Anda "
        "di dalam database mereka. Hal ini biasanya disebabkan oleh penggunaan desain 2 kolom (seperti Canva) atau tabel."
    )
    pdf.multi_cell(190, 5, xray_warning)
    pdf.ln(5)

    # Kotak Teks Mentah (Menggunakan encode untuk mencegah Error Karakter Unik)
    safe_raw_text = raw_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.set_font('Courier', '', 9)
    pdf.set_text_color(50, 50, 50)
    # Membatasi teks agar tidak membuat PDF berpuluh-puluh halaman jika CV error
    pdf.multi_cell(190, 4, safe_raw_text[:3000] + ("\n\n[...TEXT TRUNCATED...]" if len(safe_raw_text) > 3000 else ""))

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

            st.subheader("📄 Ekspor Laporan Audit")
            st.markdown("Unduh hasil audit ini dalam format PDF resmi sebagai referensi perbaikan CV Anda.")
            
            try:
                # Mengirimkan raw_text ke fungsi pembuat PDF
                pdf_bytes = create_pdf(res, raw_text)
                st.download_button(
                    label="⬇️ Download Premium PDF Report",
                    data=pdf_bytes,
                    file_name=f"CV_Audit_Report_{datetime.now().strftime('%d%b')}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            except Exception as e:
                st.error(f"Gagal membuat PDF. Detail teknis: {e}")
            
            st.divider()
            
            st.subheader("🛠️ X-Ray Vision (Teks Mentah)")
            with st.expander("Lihat bagaimana mesin ATS membaca CV Anda"):
                st.code(raw_text, language="text")

        else:
            st.error("Gagal membaca teks. Pastikan dokumen bukan hasil scan atau berbentuk gambar.")
