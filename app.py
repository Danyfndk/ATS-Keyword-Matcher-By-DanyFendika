import streamlit as st
import pdfplumber
import re
import nltk
import plotly.graph_objects as go
import time
from collections import Counter
from datetime import datetime
from fpdf import FPDF

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="CV Auditor & ATS Readiness (Admin)", page_icon="💼", layout="wide")

# --- INISIALISASI DATA NLP ---
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
    return set(action_verbs)

ACTION_VERBS = setup_nlp()

# --- FUNGSI EKSTRAKSI KATA KUNCI ---
def get_top_keywords(text):
    stop_words = {'yang', 'dan', 'di', 'dari', 'untuk', 'pada', 'dengan', 'ini', 'itu', 'sebagai', 'dalam', 'of', 'and', 'to', 'in', 'for', 'with', 'on', 'at', 'by', 'an', 'the', 'is', 'are', 'was', 'were', 'saya', 'kami', 'akan', 'bisa', 'dapat', 'tidak', 'ke', 'ada', 'atau', 'have', 'has', 'had', 'been', 'will', 'can', 'not', 'or', 'about', 'your', 'my', 'we', 'they', 'experience', 'pengalaman', 'education', 'pendidikan', 'skills', 'keahlian', 'summary', 'profile', 'work', 'kerja'}
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    filtered = [w for w in words if w not in stop_words]
    counts = Counter(filtered)
    return [word.title() for word, _ in counts.most_common(8)]

# --- FUNGSI UTAMA AUDITOR ---
def calculate_tenure(text):
    # Regex yang sudah disempurnakan untuk membaca format penanggalan CV Indonesia
    year_patterns = re.findall(r'(\b20\d{2}\b).{1,20}?(\b20\d{2}\b|present|now|current|saat\s*ini|sekarang)', text.lower())
    total_years = 0
    current_year = datetime.now().year
    
    for start, end in year_patterns:
        start_yr = int(start)
        if 'saat' in end or 'sekarang' in end or end in ['present', 'now', 'current']:
            end_yr = current_year
        else:
            end_yr = int(end)
            
        diff = end_yr - start_yr
        if 0 < diff < 40:
            total_years += diff
            
    return total_years

def audit_cv_final(text, num_pages):
    text_clean = text.lower()
    lines = text.split('\n')
    report = {}

    # 1. Parsability
    special_chars = len(re.findall(r'[^\w\s\.\,\@\+\-\(\)\/\:\&\|\%\•\▪\●\*]', text))
    parsability = ((len(text) - special_chars) / len(text)) * 100 if len(text) > 0 else 0
    report['parsability_score'] = min(max(round(parsability, 1), 0), 100)

    # 2. Sections Header
    sections = {'Experience': r'\b(experience|pengalaman)\b', 'Education': r'\b(education|pendidikan)\b', 
                'Skills': r'\b(skills|keahlian)\b', 'Summary': r'\b(summary|profile|overview)\b'}
    found_sec = [s for s, p in sections.items() if re.search(p, text_clean)]
    missing_sec = [s for s in sections.keys() if s not in found_sec]
    report['section_score'] = (len(found_sec) / len(sections)) * 100
    report['missing_sections'] = missing_sec

    # 3. XYZ & Metrics + Verb Extraction
    valid_lines = 0
    score_per_line = 0
    global_metrics = re.findall(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', text)
    found_action_verbs = set() 
    
    for line in lines:
        clean_line = line.strip().lower()
        if len(clean_line) > 30: 
            valid_lines += 1
            words_in_line = set(re.findall(r'\b\w+\b', clean_line))
            
            line_verbs = words_in_line.intersection(ACTION_VERBS)
            if line_verbs:
                found_action_verbs.update(line_verbs)
                
            has_verb = bool(line_verbs)
            has_metric = bool(re.search(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', clean_line))
            
            if has_verb and has_metric: 
                score_per_line += 1.0
            elif has_verb: 
                score_per_line += 0.5
            elif has_metric: 
                score_per_line += 0.5
                
    report['xyz_score'] = min(max(round((score_per_line / valid_lines * 100) if valid_lines > 0 else 0, 1), 0), 100)
    report['metrics_count'] = len(global_metrics)
    report['total_tenure'] = calculate_tenure(text)
    report['extracted_verbs'] = list(found_action_verbs)[:8] 

    # 4. Page Length
    report['pages'] = num_pages

    # 5. Contact Info Parsing
    email_found = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    phone_found = re.search(r'(\+?([0-9]{1,3})?[ \-\.]?)?(\(0?[0-9]{2,4}\)|0?[0-9]{2,4})[ \-\.]?[0-9]{3,4}[ \-\.]?[0-9]{3,4}', text)
    linkedin_found = re.search(r'linkedin\.com/in/[a-zA-Z0-9_-]+', text_clean)
    
    report['contact_info'] = {
        'Email': bool(email_found),
        'Phone': bool(phone_found),
        'LinkedIn': bool(linkedin_found)
    }

    # Final Score Weighting
    final_score = (
        (report['parsability_score'] * 0.4) + 
        (min(report['xyz_score'] * 1.5, 100) * 0.3) + 
        (min(len(global_metrics) * 10, 100) * 0.2) + 
        (report['section_score'] * 0.1)
    )
    
    if report['pages'] > 2:
        final_score -= 10  
    if not report['contact_info']['Email'] or not report['contact_info']['Phone']:
        final_score -= 15  
        
    report['final_score'] = min(max(round(final_score, 1), 0), 100)
    report['top_keywords'] = get_top_keywords(text)
    
    return report

# --- FUNGSI GENERATOR PDF (PREMIUM CONSULTING LAYOUT) ---
class PDFReport(FPDF):
    def header(self):
        # Premium Confidential Tag
        self.set_font('Arial', 'B', 8)
        self.set_text_color(192, 57, 43) 
        self.cell(180, 4, 'CONFIDENTIAL REPORT - FOR CANDIDATE EVALUATION ONLY', 0, 1, 'C')
        self.ln(2)

        self.set_font('Arial', 'B', 18) 
        self.set_text_color(44, 62, 80) 
        self.cell(180, 8, 'CV AUDIT & ATS READINESS REPORT', 0, 1, 'C')
        
        doc_name = getattr(self, 'doc_name', 'Evaluated Document')
        self.set_font('Arial', 'B', 11)
        self.set_text_color(41, 128, 185) 
        self.cell(180, 6, f'Document: {doc_name}', 0, 1, 'C')

        self.set_font('Arial', 'I', 10)
        self.set_text_color(127, 140, 141) 
        self.cell(180, 5, f'Generated on: {datetime.now().strftime("%d %B %Y")}', 0, 1, 'C')
        
        self.ln(4) 
        self.set_draw_color(189, 195, 199)
        y_position = self.get_y() 
        self.line(15, y_position, 195, y_position) 
        self.ln(6) 

    def footer(self):
        self.set_y(-25)
        self.set_draw_color(189, 195, 199)
        self.line(15, 272, 195, 272)
        self.set_y(-22)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(127, 140, 141)
        self.cell(180, 4, 'System Algorithm based on Global Enterprise ATS Standards & Google XYZ Formula.', 0, 1, 'C')
        self.set_font('Arial', 'B', 9)
        self.set_text_color(44, 62, 80)
        self.cell(180, 5, 'Audit Conducted by: Dany Fendika - ATS Readiness Specialist & HR Data Analyst', 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.set_text_color(127, 140, 141)
        self.cell(180, 4, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(report_data, raw_text, doc_name):
    pdf = PDFReport(orientation='P', unit='mm', format='A4')
    pdf.doc_name = doc_name 
    pdf.set_margins(15, 20, 15) 
    pdf.set_auto_page_break(auto=True, margin=25) 
    pdf.add_page()

    def safe_page_break(required_space):
        if pdf.get_y() > (297 - 25 - required_space):
            pdf.add_page()
    
    # --- 1. SCORECARD DASHBOARD ---
    pdf.set_fill_color(236, 240, 241) 
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 1. OVERALL ATS READINESS SCORE', 0, 1, 'L', fill=True)
    pdf.ln(5)
    
    if report_data['final_score'] >= 80: 
        pdf.set_text_color(39, 174, 96)
        status_text = "EXCELLENT"
        exec_summary = "Laporan ini menunjukkan bahwa CV Anda berada di level EXCELLENT. Struktur dan format dapat dibaca sempurna oleh mesin ATS. Anda juga memiliki kekuatan narasi metrik yang solid. Peluang dokumen Anda lolos screening otomatis sangat tinggi."
    elif report_data['final_score'] >= 50: 
        pdf.set_text_color(230, 126, 34) 
        status_text = "FAIR / NEEDS OPTIMIZATION"
        exec_summary = "Laporan ini menunjukkan bahwa CV Anda berada di level FAIR. Mesin ATS berhasil mendeteksi format Anda, namun narasi pengalaman kerja Anda masih terlalu pasif. Anda kehilangan poin penting pada aspek kuantifikasi data."
    else: 
        pdf.set_text_color(192, 57, 43) 
        status_text = "POOR / HIGH RISK"
        exec_summary = "Laporan ini menunjukkan status POOR (Risiko Tinggi). Terdapat kesalahan fatal pada format atau struktur CV Anda yang membuat mesin ATS gagal mengekstrak informasi penting. Perbaikan menyeluruh sangat direkomendasikan."
        
    pdf.set_font('Arial', 'B', 34)
    pdf.cell(180, 12, f"{report_data['final_score']} / 100", 0, 1, 'C')
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(180, 6, f"STATUS: {status_text}", 0, 1, 'C')
    pdf.ln(4)

    # Executive Summary (Nilai Jual Consulting)
    pdf.set_font('Arial', 'I', 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(180, 5, f"Executive Summary: {exec_summary}")
    pdf.ln(6)
    
    # --- 2. DETAILED METRICS ---
    safe_page_break(50) 
    pdf.set_fill_color(236, 240, 241)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 2. PERFORMANCE METRICS & ANALYSIS', 0, 1, 'L', fill=True)
    pdf.ln(4)

    # Metrik dipecah menjadi desain garis bawah yang elegan
    metrics_data = [
        ("A. ATS Parsability (Text Readability)", f"{report_data['parsability_score']}%", "Semakin tinggi skor, semakin aman CV dari risiko 'rusak' saat diekstrak ATS. Hindari tabel/2 kolom."),
        ("B. Kualitas Kalimat (Google XYZ Score)", f"{int(report_data['xyz_score'])}%", "Standar XYZ: [Action Verb] + [Konteks] + [Metrik]. Skor 0% terjadi jika kalimat naratif pasif murni."),
        ("C. Quantifiable Metrics", f"{report_data['metrics_count']} Data Points", "Bukti pencapaian nyata. Contoh ideal: 'Memimpin 15 staf', 'Efisiensi 20%', atau 'Budget Rp500 juta'."),
        ("D. Est. Career Tenure", f"{report_data['total_tenure']} Years", "Masa kerja yang berhasil dikalkulasi otomatis oleh mesin dari format riwayat kerja Anda."),
        ("E. Document Format", f"{report_data['pages']} Pages", "Standar panjang dokumen resume profesional global adalah 1 hingga maksimal 2 halaman.")
    ]

    for title, score, note in metrics_data:
        pdf.set_font('Arial', 'B', 10)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(130, 5, title, 0, 0, 'L')
        pdf.cell(50, 5, score, 0, 1, 'R')
        pdf.set_font('Arial', 'I', 9)
        pdf.set_text_color(127, 140, 141)
        pdf.multi_cell(180, 4.5, f"Note: {note}")
        pdf.set_draw_color(236, 240, 241)
        pdf.line(15, pdf.get_y()+1, 195, pdf.get_y()+1)
        pdf.ln(3)

    pdf.ln(4)

    # --- 3. DIAGNOSTIC RESULTS (CARD UI DESIGN) ---
    safe_page_break(40)
    pdf.set_fill_color(236, 240, 241)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 3. DIAGNOSTIC RESULTS & FEEDBACK', 0, 1, 'L', fill=True)
    pdf.ln(4)
    
    # [1] Pilar Struktur
    safe_page_break(25)
    if report_data['missing_sections']:
        pdf.set_fill_color(253, 237, 236) # Soft Red Background
        pdf.set_text_color(192, 57, 43) 
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(180, 6, " [ACTION NEEDED] - Document Structure", 0, 1, 'L', fill=True)
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(180, 5.5, f"ATS gagal mendeteksi bagian: {', '.join(report_data['missing_sections']).title()}. Standar global mewajibkan 4 pilar utama: Summary, Experience, Education, dan Skills.", fill=True)
    else:
        pdf.set_fill_color(234, 250, 241) # Soft Green Background
        pdf.set_text_color(39, 174, 96) 
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(180, 6, " [EXCELLENT] - Document Structure", 0, 1, 'L', fill=True)
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(180, 5.5, "Sangat baik. Seluruh 4 pilar wajib (Summary, Experience, Education, Skills) telah terdeteksi sempurna oleh sistem.", fill=True)
    pdf.ln(4)

    # [2] Kualitas Konten
    safe_page_break(25)
    verb_text = f" (Kata kerja Anda yang terdeteksi: {', '.join(report_data['extracted_verbs']).title()})" if report_data['extracted_verbs'] else ""
    if report_data['xyz_score'] < 50:
        pdf.set_fill_color(253, 237, 236)
        pdf.set_text_color(192, 57, 43)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(180, 6, " [ACTION NEEDED] - Content Quality & Impact", 0, 1, 'L', fill=True)
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(180, 5.5, f"Kalimat pengalaman kerja kurang berdampak. Gunakan format Action Verb + Konteks + Metrik (Angka) untuk mendeskripsikan hasil kerja.{verb_text}", fill=True)
    else:
        pdf.set_fill_color(234, 250, 241)
        pdf.set_text_color(39, 174, 96)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(180, 6, " [EXCELLENT] - Content Quality & Impact", 0, 1, 'L', fill=True)
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(180, 5.5, f"Penggunaan Action Verbs dan metrik kuantitatif pada pengalaman kerja sudah sangat tangguh.{verb_text}", fill=True)
    pdf.ln(4)

    # [3] ATS Keyword Mapping (Insight Eksklusif)
    safe_page_break(25)
    pdf.set_fill_color(235, 245, 251) # Soft Blue Background
    pdf.set_text_color(41, 128, 185) 
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(180, 6, " [INSIGHT] - Top ATS Keyword Mapping", 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(40, 40, 40)
    kw_str = ", ".join(report_data['top_keywords']).title() if report_data['top_keywords'] else "Tidak cukup data."
    pdf.multi_cell(180, 5.5, f"Kata kunci dominan yang diekstrak mesin dari CV Anda: {kw_str}. Pastikan kata kunci ini relevan dengan kualifikasi loker incaran Anda.", fill=True)
    pdf.ln(4)

    # [4] Informasi Kontak & Halaman
    safe_page_break(25)
    missing_contacts = [k for k, v in report_data['contact_info'].items() if not v]
    page_warning = f" CV Anda melebihi batas (Miliki {report_data['pages']} halaman, direkomendasikan maksimal 2)." if report_data['pages'] > 2 else ""
    
    if missing_contacts or page_warning:
        pdf.set_fill_color(254, 245, 231) # Soft Orange
        pdf.set_text_color(211, 84, 0)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(180, 6, " [WARNING] - Formatting & Contact Details", 0, 1, 'L', fill=True)
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(40, 40, 40)
        warn_text = ""
        if missing_contacts: warn_text += f"ATS gagal membaca kontak: {', '.join(missing_contacts)}. Gunakan teks standar tanpa menyematkan teks di dalam icon gambar. "
        warn_text += page_warning
        pdf.multi_cell(180, 5.5, warn_text, fill=True)
    else:
        pdf.set_fill_color(234, 250, 241)
        pdf.set_text_color(39, 174, 96)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(180, 6, " [EXCELLENT] - Formatting & Contact Details", 0, 1, 'L', fill=True)
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(40, 40, 40)
        pdf.multi_cell(180, 5.5, "Sangat baik. Detail kontak berhasil diekstrak dan panjang halaman memenuhi standar optimal.", fill=True)
    pdf.ln(8)

    # --- 4. RECOMMENDED ACTION PLAN ---
    safe_page_break(40)
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 6, "NEXT STEPS (Tindak Lanjut):", 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(180, 5, "1. Perbaiki temuan yang berstatus 'Action Needed' atau 'Warning' di atas.\n2. Pastikan CV Anda disimpan murni dalam format PDF standar (bukan gambar/scan yang diubah ke PDF).\n3. Lihat lampiran 'X-Ray Vision' di halaman berikutnya untuk memastikan tidak ada teks yang menempel/hilang.")

    # --- HALAMAN LAMPIRAN: X-RAY VISION ---
    pdf.add_page() 
    pdf.set_fill_color(44, 62, 80) 
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(255, 255, 255) 
    pdf.cell(180, 10, ' X-RAY VISION: RAW DATA EXTRACTION (SYSTEM VIEW)', 0, 1, 'C', fill=True)
    pdf.ln(6)

    pdf.set_font('Arial', 'B', 9)
    pdf.set_text_color(192, 57, 43) 
    xray_warning = (
        "WARNING: Teks di bawah ini adalah tampilan MENTAH (Raw Text) bagaimana sistem ATS membaca CV Anda. "
        "Jika teks terlihat berantakan, melompat, atau menyatu tanpa spasi (biasa terjadi pada CV desain 2 kolom/tabel), "
        "maka data Anda dipastikan GAGAL tersimpan dengan baik di database HR perusahaan."
    )
    pdf.multi_cell(180, 5, xray_warning)
    pdf.ln(4)

    safe_raw_text = raw_text.encode('latin-1', 'replace').decode('latin-1')
    safe_raw_text = re.sub(r'\n{3,}', '\n\n', safe_raw_text) 
    
    pdf.set_font('Courier', '', 8.5)
    pdf.set_text_color(50, 50, 50)
    pdf.set_fill_color(248, 249, 249) 
    pdf.multi_cell(180, 4.5, safe_raw_text[:3500] + ("\n\n[...TEXT TRUNCATED...]" if len(safe_raw_text) > 3500 else ""), fill=True)

    return bytes(pdf.output(dest='S'))

# --- UI STREAMLIT (ADMIN DASHBOARD) ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>⚙️ Admin Panel</h2>", unsafe_allow_html=True)
    st.info("💡 **Dapur Internal Konsultan HR**\n\nSistem evaluasi komersial ini hanya dapat diakses oleh Admin. Laporan PDF yang dihasilkan bersifat **Confidential**.")
    st.divider()
    st.markdown("### 🚦 System Status")
    st.markdown("🟢 **Engine:** Online & Stable\n\n🟢 **NLP Model:** Loaded\n\n🟢 **PDF Gen:** Ready")
    st.divider()
    st.markdown("<small>v. Enterprise 2.5.0</small>", unsafe_allow_html=True)

st.title("💼 Dashboard: CV Auditor & ATS Analyzer")
st.markdown("Platform pemrosesan **Curriculum Vitae** untuk *Generate* PDF Report Klien secara otomatis.")

with st.container(border=True):
    uploaded_file = st.file_uploader("Upload Dokumen CV Klien (Format PDF)", type=["pdf"])

if uploaded_file:
    MAX_FILE_SIZE = 200 * 1024 * 1024 
    
    if uploaded_file.size > MAX_FILE_SIZE:
        st.error("⚠️ Ukuran file terlalu besar! Batas maksimal ukuran dokumen CV adalah 200MB.")
    else:
        with st.status("🔍 Menginisialisasi Mesin ATS...", expanded=True) as status:
            try:
                progress_bar = st.progress(0)
                
                st.write("📄 Mengekstrak teks dari dokumen PDF...")
                progress_bar.progress(25)
                time.sleep(0.5) 
                
                with pdfplumber.open(uploaded_file) as pdf:
                    num_pages = len(pdf.pages) 
                    raw_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
                
                st.write("🧬 Menganalisis struktur dan anatomi CV...")
                progress_bar.progress(50)
                time.sleep(0.5)
                
                if raw_text.strip():
                    st.write("🧮 Menghitung metrik dan Google XYZ Score...")
                    progress_bar.progress(80)
                    time.sleep(0.5)
                    
                    res = audit_cv_final(raw_text, num_pages) 
                    nama_file_asli = uploaded_file.name.rsplit('.', 1)[0]
                    
                    st.write("📝 Menyusun Laporan Diagnostik Klien...")
                    progress_bar.progress(100)
                    time.sleep(0.4)
                    
                    status.update(label="✅ Audit Selesai! Data siap diekspor.", state="complete", expanded=False)
                    st.toast('Sistem berhasil mengaudit CV Klien!', icon='🎉') 
                    
                    st.write("") 
                    
                    # --- ROW 1: CHARTS (OVERALL & RADAR) ---
                    col_gauge, col_radar = st.columns([1, 1.2])
                    
                    with col_gauge:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #2C3E50;'>Overall ATS Score</h4>", unsafe_allow_html=True)
                            fig_gauge = go.Figure(go.Indicator(
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
                            fig_gauge.update_layout(height=260, margin=dict(l=20, r=20, t=20, b=20))
                            st.plotly_chart(fig_gauge, use_container_width=True)

                    with col_radar:
                        with st.container(border=True):
                            st.markdown("<h4 style='text-align: center; color: #2C3E50;'>CV Anatomy Balance</h4>", unsafe_allow_html=True)
                            missing_c_count = sum(value == False for value in res['contact_info'].values())
                            contact_format_score = ((3 - missing_c_count) / 3 * 50) + (50 if res['pages'] <= 2 else 0)
                            
                            fig_radar = go.Figure(data=go.Scatterpolar(
                              r=[res['parsability_score'], res['section_score'], res['xyz_score'], contact_format_score],
                              theta=['Keterbacaan Teks', 'Pilar Struktur', 'Kualitas Konten', 'Format & Kontak'],
                              fill='toself',
                              line_color='#2980b9'
                            ))
                            fig_radar.update_layout(
                              polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                              showlegend=False,
                              height=260, margin=dict(l=40, r=40, t=30, b=30)
                            )
                            st.plotly_chart(fig_radar, use_container_width=True)

                    # --- ROW 2: SCORECARDS (5 METRIK) ---
                    with st.container(border=True):
                        m1, m2, m3, m4, m5 = st.columns(5)
                        m1.metric("Keterbacaan", f"{res['parsability_score']}%")
                        m2.metric("Skor XYZ", f"{int(res['xyz_score'])}%")
                        m3.metric("Kontak", f"{3 - missing_c_count}/3")
                        m4.metric("Masa Kerja", f"±{res['total_tenure']} Thn")
                        m5.metric("Halaman", f"{res['pages']} Hal")

                    # --- ROW 3: SAAS DASHBOARD TABS ---
                    st.write("")
                    tab1, tab2, tab3 = st.tabs(["📊 Diagnostic Overview", "📄 Export Report", "🛠️ Raw Extraction"])
                    
                    with tab1:
                        st.markdown("### Temuan Audit Internal")
                        
                        with st.container(border=True):
                            if res['final_score'] >= 80: st.success("**Status: EXCELLENT.** Format ideal, data kuat. Probabilitas tinggi lolos mesin ATS.")
                            elif res['final_score'] >= 50: st.warning("**Status: FAIR.** Berisiko. Strukturnya baik namun minim penggunaan kalimat ber-metrik.")
                            else: st.error("**Status: POOR.** Risiko tinggi auto-reject. Mesin gagal membaca data atau format rusak.")
                        
                        with st.container(border=True):
                            st.markdown("##### 📌 Top 8 ATS Keywords (Extracted)")
                            if res['top_keywords']:
                                html_keywords = " ".join([f"<span style='background-color: #e8f4f8; color: #2980b9; padding: 5px 15px; border-radius: 20px; font-size: 14px; font-weight: bold; margin-right: 8px; border: 1px solid #b3d7ff; display: inline-block; margin-bottom: 8px;'>{k}</span>" for k in res['top_keywords']])
                                st.markdown(html_keywords, unsafe_allow_html=True)
                            else:
                                st.write("*Tidak cukup kata kunci yang dapat dideteksi.*")
                        
                        with st.container(border=True):
                            st.markdown("##### 🔎 Issue Detection")
                            if res['missing_sections']: st.error(f"**[-] Missing Sections:** ATS gagal mendeteksi bagian: {', '.join(res['missing_sections']).title()}.")
                            else: st.info("**[+] Structure:** Sangat baik. Seluruh 4 pilar wajib telah terdeteksi.")
                            
                            if res['xyz_score'] < 50: st.error("**[-] Content Quality:** Kalimat pengalaman kerja pasif/kurang metrik (angka).")
                            else: st.info(f"**[+] Content Quality:** Action Verbs & Metrik sangat baik. (Kata kerja ditemukan: *{', '.join(res['extracted_verbs']).title()}*)")
                        
                    with tab2:
                        st.markdown("### 📤 Laporan PDF Klien")
                        st.write("Sistem telah menyusun laporan PDF berstandar *Enterprise Consulting* yang siap Anda berikan kepada Klien.")
                        
                        pdf_bytes = create_pdf(res, raw_text, nama_file_asli)
                        tanggal_sekarang = datetime.now().strftime('%d-%m-%Y')
                        nama_file_download = f"{nama_file_asli}-{tanggal_sekarang}.pdf"
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.download_button(
                            label="⬇️ GENERATE & DOWNLOAD CLIENT REPORT",
                            data=pdf_bytes,
                            file_name=nama_file_download,
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                    with tab3:
                        st.markdown("### X-Ray Vision (Admin Only)")
                        st.info("Ini adalah tampilan mentah (*Raw Text*) yang dibaca oleh ATS. Gunakan untuk mengecek jika PDF Klien corrupt.")
                        clean_display_text = re.sub(r'\n{3,}', '\n\n', raw_text)
                        st.code(clean_display_text, language="text")

                else:
                    status.update(label="❌ Audit Gagal", state="error", expanded=True)
                    st.warning("⚠️ Dokumen kosong atau berisi gambar/scan yang tidak dapat dibaca oleh mesin ATS. Pastikan Anda mengunggah CV format PDF teks (Text-based).")
            
            except Exception as e:
                status.update(label="❌ Terjadi Kesalahan", state="error", expanded=True)
                st.error("⚠️ Sistem gagal membaca dokumen. Pastikan file PDF tidak rusak dan tidak diproteksi oleh password.")
