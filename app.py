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
st.set_page_config(page_title="CV Auditor & ATS Analyzer (Admin)", page_icon="💼", layout="wide")

# --- INISIALISASI DATA NLP & KAMUS ---
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

# KAMUS CLICHÉ & BUZZWORDS
CLICHE_WORDS = [
    'team player', 'hard worker', 'pekerja keras', 'jujur', 'disiplin', 
    'bertanggung jawab', 'fast learner', 'cepat belajar', 'detail oriented', 
    'perfeksionis', 'pekerja tim', 'multitasking', 'inovatif', 'kreatif', 
    'berdedikasi', 'highly motivated', 'results-driven'
]

# --- FUNGSI EKSTRAKSI KATA KUNCI (Super Filtered) ---
def get_top_keywords(text):
    # Menyuntikkan kata "sampah" CV Bahasa Inggris & Indonesia agar Keywords murni berisi Hard Skills
    stop_words = {
        'yang', 'dan', 'di', 'dari', 'untuk', 'pada', 'dengan', 'ini', 'itu', 'sebagai', 'dalam', 
        'of', 'and', 'to', 'in', 'for', 'with', 'on', 'at', 'by', 'an', 'the', 'is', 'are', 'was', 'were', 
        'saya', 'kami', 'akan', 'bisa', 'dapat', 'tidak', 'ke', 'ada', 'atau', 'have', 'has', 'had', 
        'been', 'will', 'can', 'not', 'or', 'about', 'your', 'my', 'we', 'they', 'experience', 'pengalaman', 
        'education', 'pendidikan', 'skills', 'keahlian', 'summary', 'profile', 'work', 'kerja',
        'januari', 'februari', 'maret', 'april', 'mei', 'juni', 'juli', 'agustus', 'september', 'oktober', 
        'november', 'desember', 'january', 'february', 'march', 'may', 'june', 'july', 'august', 'october', 
        'december', 'pt', 'cv', 'tbk', 'tahun', 'bulan', 'hari', 'saat', 'sekarang', 'present', 'current',
        'sampai', 'hingga', 'memiliki', 'menggunakan', 'berbagai', 'sangat', 'baik',
        'from', 'test', 'level', 'description', 'process', 'employee', 'responsibility', 'responsibilities', 
        'project', 'projects', 'job', 'role', 'based', 'using', 'detail', 'details', 'include', 'including',
        'ensure', 'ensuring', 'activities', 'activity'
    }
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    filtered = [w for w in words if w not in stop_words]
    counts = Counter(filtered)
    return [word.title() for word, _ in counts.most_common(8)]

# --- FUNGSI UTAMA AUDITOR ---
def calculate_tenure(text):
    year_patterns = re.findall(r'(\b20\d{2}\b).{1,20}?(\b20\d{2}\b|present|now|current|saat\s*ini|sekarang)', text.lower())
    total_years = 0
    current_year = datetime.now().year
    for start, end in year_patterns:
        start_yr = int(start)
        end_yr = current_year if any(x in end for x in ['present', 'now', 'current', 'saat', 'sekarang']) else int(end)
        diff = end_yr - start_yr
        if 0 < diff < 40: total_years += diff
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
    report['section_score'] = (len(found_sec) / len(sections)) * 100
    report['missing_sections'] = [s for s in sections.keys() if s not in found_sec]

    # 3. XYZ & Metrics
    valid_lines, score_per_line = 0, 0
    found_action_verbs = set()
    for line in lines:
        clean_line = line.strip().lower()
        if len(clean_line) > 30: 
            valid_lines += 1
            words = set(re.findall(r'\b\w+\b', clean_line))
            line_verbs = words.intersection(ACTION_VERBS)
            found_action_verbs.update(line_verbs)
            has_verb, has_metric = bool(line_verbs), bool(re.search(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', clean_line))
            score_per_line += 1.0 if (has_verb and has_metric) else (0.5 if (has_verb or has_metric) else 0)
                
    report['xyz_score'] = min(max(round((score_per_line / valid_lines * 100) if valid_lines > 0 else 0, 1), 0), 100)
    report['metrics_count'] = len(re.findall(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', text))
    report['total_tenure'] = calculate_tenure(text)
    report['extracted_verbs'] = list(found_action_verbs)[:8] 

    # 4. Deteksi Buzzword & Klise
    found_cliches = [word for word in CLICHE_WORDS if re.search(r'\b' + re.escape(word) + r'\b', text_clean)]
    report['cliche_words'] = found_cliches

    # 5. Contact Info & Location Parsing
    email_found = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    phone_found = re.search(r'(\+?([0-9]{1,3})?[ \-\.]?)?(\(0?[0-9]{2,4}\)|0?[0-9]{2,4})[ \-\.]?[0-9]{3,4}[ \-\.]?[0-9]{3,4}', text)
    linkedin_found = re.search(r'linkedin\.com/in/[a-zA-Z0-9_-]+', text_clean)
    loc_found = re.search(r'\b(jakarta|bogor|depok|tangerang|bekasi|bandung|surabaya|semarang|medan|makassar|yogyakarta|sleman|bantul|bali|denpasar|kota\s+\w+|kab\.\s+\w+|kabupaten\s+\w+|kecamatan\s+\w+|provinsi\s+\w+|jl\.?|jalan\s+)\b', text_clean)
    
    report['contact_info'] = {'Email': bool(email_found), 'Telepon': bool(phone_found), 'LinkedIn': bool(linkedin_found), 'Domisili': bool(loc_found)}
    report['pages'] = num_pages

    # Scoring Weight
    final_score = (report['parsability_score'] * 0.4) + (min(report['xyz_score'] * 1.5, 100) * 0.3) + (min(report['metrics_count'] * 10, 100) * 0.2) + (report['section_score'] * 0.1)
    if report['pages'] > 2: final_score -= 10  
    if not report['contact_info']['Email'] or not report['contact_info']['Telepon']: final_score -= 15  
    if len(found_cliches) >= 3: final_score -= 5 
        
    report['final_score'] = min(max(round(final_score, 1), 0), 100)
    report['top_keywords'] = get_top_keywords(text)
    return report

# --- FUNGSI GENERATOR PDF (PREMIUM CONSULTING LAYOUT) ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 8); self.set_text_color(192, 57, 43)
        self.cell(180, 4, 'CONFIDENTIAL REPORT - CANDIDATE EVALUATION ONLY', 0, 1, 'C')
        self.ln(2); self.set_font('Arial', 'B', 18); self.set_text_color(44, 62, 80)
        self.cell(180, 8, 'CV AUDIT & ATS READINESS REPORT', 0, 1, 'C')
        self.set_font('Arial', 'B', 11); self.set_text_color(41, 128, 185)
        self.cell(180, 6, f'Document: {getattr(self, "doc_name", "CV")}', 0, 1, 'C')
        self.set_font('Arial', 'I', 10); self.set_text_color(127, 140, 141)
        self.cell(180, 5, f'Generated on: {datetime.now().strftime("%d %B %Y")}', 0, 1, 'C')
        self.ln(4); self.set_draw_color(189, 195, 199); self.line(15, self.get_y(), 195, self.get_y()); self.ln(6)

    def footer(self):
        self.set_y(-25); self.set_draw_color(189, 195, 199); self.line(15, 272, 195, 272)
        self.set_y(-22); self.set_font('Arial', 'I', 8); self.set_text_color(127, 140, 141)
        self.cell(180, 4, 'System Algorithm based on Global Enterprise ATS Standards & Google XYZ Formula.', 0, 1, 'C')
        self.set_font('Arial', 'B', 9); self.set_text_color(44, 62, 80)
        self.cell(180, 5, 'Audit Conducted by: Dany Fendika - ATS Readiness Specialist & HR Data Analyst', 0, 1, 'C')
        self.set_font('Arial', 'I', 8); self.set_text_color(127, 140, 141)
        self.cell(180, 4, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(report_data, raw_text, doc_name):
    pdf = PDFReport('P', 'mm', 'A4')
    pdf.doc_name = doc_name 
    pdf.set_margins(15, 20, 15) 
    pdf.set_auto_page_break(auto=True, margin=25) 
    pdf.add_page()

    def safe_page_break(required_space):
        if pdf.get_y() > (297 - 25 - required_space):
            pdf.add_page()
    
    # --- 1. SCORECARD DASHBOARD ---
    pdf.set_fill_color(236, 240, 241); pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 1. OVERALL ATS READINESS SCORE', 0, 1, 'L', fill=True); pdf.ln(5)
    
    color = (39, 174, 96) if report_data['final_score'] >= 80 else (230, 126, 34) if report_data['final_score'] >= 50 else (192, 57, 43)
    pdf.set_text_color(*color); pdf.set_font('Arial', 'B', 34); pdf.cell(180, 12, f"{report_data['final_score']} / 100", 0, 1, 'C')
    pdf.set_font('Arial', 'B', 12)
    status_text = "EXCELLENT" if report_data['final_score'] >= 80 else "FAIR / NEEDS OPTIMIZATION" if report_data['final_score'] >= 50 else "POOR / HIGH RISK"
    pdf.cell(180, 6, f"STATUS: {status_text}", 0, 1, 'C'); pdf.ln(4)

    exec_summary = "Laporan ini menunjukkan bahwa CV Anda berada di level EXCELLENT. Struktur dan format dapat dibaca sempurna oleh mesin ATS. Anda juga memiliki kekuatan narasi metrik yang solid. Peluang dokumen Anda lolos screening otomatis sangat tinggi." if report_data['final_score'] >= 80 else "Laporan ini menunjukkan bahwa CV Anda berada di level FAIR. Mesin ATS berhasil mendeteksi format Anda, namun narasi pengalaman kerja Anda masih terlalu pasif. Anda kehilangan poin penting pada aspek kuantifikasi data." if report_data['final_score'] >= 50 else "Laporan ini menunjukkan status POOR (Risiko Tinggi). Terdapat kesalahan fatal pada format atau struktur CV Anda yang membuat mesin ATS gagal mengekstrak informasi penting. Perbaikan menyeluruh sangat direkomendasikan."
    pdf.set_font('Arial', 'I', 10); pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(180, 5, f"Executive Summary: {exec_summary}"); pdf.ln(6)
    
    # --- 2. DETAILED METRICS ---
    safe_page_break(50) 
    pdf.set_fill_color(236, 240, 241); pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 2. PERFORMANCE METRICS & ANALYSIS', 0, 1, 'L', fill=True); pdf.ln(4)

    metrics_data = [
        ("A. ATS Parsability (Text Readability)", f"{report_data['parsability_score']}%", "Semakin tinggi skor, semakin aman CV dari risiko 'rusak' saat diekstrak ATS. Hindari tabel/2 kolom."),
        ("B. Kualitas Kalimat (Google XYZ Score)", f"{int(report_data['xyz_score'])}%", "Standar XYZ: [Action Verb] + [Konteks] + [Metrik]. Skor 0% terjadi jika kalimat naratif pasif murni."),
        ("C. Quantifiable Metrics", f"{report_data['metrics_count']} Data Points", "Bukti pencapaian nyata. Contoh ideal: 'Memimpin 15 staf', 'Efisiensi 20%', atau 'Budget Rp500 juta'."),
        ("D. Est. Career Tenure", f"{report_data['total_tenure']} Years", "Masa kerja yang berhasil dikalkulasi otomatis oleh mesin dari format riwayat kerja Anda."),
        ("E. Document Format", f"{report_data['pages']} Pages", "Standar panjang dokumen resume profesional global adalah 1 hingga maksimal 2 halaman.")
    ]

    for title, score, note in metrics_data:
        pdf.set_font('Arial', 'B', 10); pdf.set_text_color(44, 62, 80)
        pdf.cell(130, 5, title, 0, 0, 'L'); pdf.cell(50, 5, score, 0, 1, 'R')
        pdf.set_font('Arial', 'I', 9); pdf.set_text_color(127, 140, 141)
        pdf.multi_cell(180, 4.5, f"Note: {note}")
        pdf.set_draw_color(240, 240, 240); pdf.line(15, pdf.get_y()+1, 195, pdf.get_y()+1); pdf.ln(3)

    # --- 3. DIAGNOSTIC RESULTS ---
    safe_page_break(40)
    pdf.ln(2); pdf.set_fill_color(236, 240, 241); pdf.set_font('Arial', 'B', 12); pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 3. DIAGNOSTIC RESULTS & EXPERT INSIGHTS', 0, 1, 'L', fill=True); pdf.ln(4)
    
    # 3.1 Content Quality & XYZ Impact (DIAMANKAN DENGAN LOCK KOORDINAT X)
    # Memperbesar safe_page_break menjadi 45 agar "Before-After" tidak terpotong ke halaman baru
    safe_page_break(45)
    is_content_ok = report_data['xyz_score'] >= 50
    bg = (234, 250, 241) if is_content_ok else (253, 237, 236)
    text_c = (39, 174, 96) if is_content_ok else (192, 57, 43)
    status_tag = "[EXCELLENT]" if is_content_ok else "[ACTION NEEDED]"
    
    # FIX BUG PDF: Memaksa set_x(15) di setiap baris agar text tidak melompat ke margin kanan!
    pdf.set_fill_color(*bg); pdf.set_text_color(*text_c); pdf.set_font('Arial', 'B', 10)
    pdf.set_x(15)
    pdf.cell(180, 6, f" {status_tag} - Content Quality & Impact", 0, 1, 'L', fill=True)
    pdf.set_text_color(40, 40, 40); pdf.set_font('Arial', '', 10)
    
    if is_content_ok:
        pdf.set_x(15)
        pdf.multi_cell(180, 5.5, "Penggunaan Action Verbs dan metrik kuantitatif pada pengalaman kerja Anda sudah sangat tangguh.", fill=True)
    else:
        pdf.set_x(15)
        pdf.multi_cell(180, 5.5, "Kalimat pengalaman kerja kurang berdampak. Gunakan format Action Verb + Konteks + Metrik (Angka).", fill=True)
        pdf.set_font('Arial', 'B', 9); pdf.set_text_color(41, 128, 185)
        pdf.set_x(15)
        pdf.cell(180, 5, " >> CONSULTANT ADVICE (Contoh Perbaikan):", 0, 1, 'L', fill=True)
        pdf.set_font('Arial', 'I', 9); pdf.set_text_color(192, 57, 43)
        pdf.set_x(15)
        pdf.multi_cell(180, 5, " [Salah] Bertanggung jawab mengurus komplain pelanggan setiap hari.", fill=True)
        pdf.set_text_color(39, 174, 96)
        pdf.set_x(15)
        pdf.multi_cell(180, 5, " [Benar] Menyelesaikan 50+ komplain pelanggan per hari dengan tingkat kepuasan 98%.", fill=True)
    pdf.ln(4)

    # 3.2 ATS Keyword Mapping
    safe_page_break(25)
    pdf.set_fill_color(235, 245, 251); pdf.set_text_color(41, 128, 185); pdf.set_font('Arial', 'B', 10)
    pdf.set_x(15)
    pdf.cell(180, 6, " [INSIGHT] - Industry Keyword Extraction", 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 10); pdf.set_text_color(40, 40, 40)
    kw_str = ", ".join(report_data['top_keywords']).title() if report_data['top_keywords'] else "Tidak terdeteksi."
    pdf.set_x(15)
    pdf.multi_cell(180, 5.5, f"Sistem berhasil menyaring kata kunci spesifik dari CV Anda: {kw_str}. Pastikan kata kunci ini relevan dengan Loker (Job Description) yang dituju.", fill=True)
    pdf.ln(4)

    # 3.3 Toxic Buzzword Detection
    safe_page_break(25)
    has_cliche = len(report_data['cliche_words']) > 0
    bg_cliche = (254, 245, 231) if has_cliche else (234, 250, 241) 
    txt_cliche = (211, 84, 0) if has_cliche else (39, 174, 96)
    tag_cliche = "[WARNING]" if has_cliche else "[EXCELLENT]"
    
    pdf.set_fill_color(*bg_cliche); pdf.set_text_color(*txt_cliche); pdf.set_font('Arial', 'B', 10)
    pdf.set_x(15)
    pdf.cell(180, 6, f" {tag_cliche} - Cliché & Buzzword Scanner", 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 10); pdf.set_text_color(40, 40, 40)
    pdf.set_x(15)
    if has_cliche:
        cliche_str = ", ".join(report_data['cliche_words']).title()
        pdf.multi_cell(180, 5.5, f"CV Anda mengandung kata klise/pasif ({cliche_str}). Rekruter modern menganggap kata ini sebagai 'red flag'. Ganti dengan bukti spesifik/metrik.", fill=True)
    else:
        pdf.multi_cell(180, 5.5, "CV Anda bersih dari kata sifat klise (buzzwords usang). Ini menunjukkan profesionalisme tinggi.", fill=True)
    pdf.ln(4)

    # 3.4 Format & Contact
    safe_page_break(25)
    missing_c = sum(v == False for v in report_data['contact_info'].values())
    if missing_c > 0 or report_data['pages'] > 2:
        pdf.set_fill_color(253, 237, 236); pdf.set_text_color(192, 57, 43); pdf.set_font('Arial', 'B', 10)
        pdf.set_x(15)
        pdf.cell(180, 6, " [ACTION NEEDED] - Structure & Contacts", 0, 1, 'L', fill=True)
        pdf.set_font('Arial', '', 10); pdf.set_text_color(40, 40, 40)
        warn_text = ""
        if missing_c > 0: warn_text += f"Item kontak kurang ({missing_c}/4 hilang). Pastikan Email, Phone, LinkedIn, & Domisili ada. "
        if report_data['pages'] > 2: warn_text += f"Halaman CV Anda melebihi batas ideal 1-2 Halaman."
        pdf.set_x(15)
        pdf.multi_cell(180, 5.5, warn_text, fill=True)
    else:
        pdf.set_fill_color(234, 250, 241); pdf.set_text_color(39, 174, 96); pdf.set_font('Arial', 'B', 10)
        pdf.set_x(15)
        pdf.cell(180, 6, " [EXCELLENT] - Structure & Contacts", 0, 1, 'L', fill=True)
        pdf.set_font('Arial', '', 10); pdf.set_text_color(40, 40, 40)
        pdf.set_x(15)
        pdf.multi_cell(180, 5.5, "Struktur dokumen, detail kontak, domisili, dan jumlah halaman memenuhi standar ATS.", fill=True)
    pdf.ln(8)

    # --- 4. RECOMMENDED ACTION PLAN ---
    safe_page_break(40)
    pdf.set_font('Arial', 'B', 11); pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 6, "NEXT STEPS (Tindak Lanjut):", 0, 1, 'L')
    pdf.set_font('Arial', '', 10); pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(180, 5, "1. Perbaiki temuan yang berstatus 'Action Needed' atau 'Warning' di atas.\n2. Pastikan CV Anda disimpan murni dalam format PDF standar (bukan gambar/scan yang diubah ke PDF).\n3. Lihat lampiran 'X-Ray Vision' di halaman berikutnya untuk memastikan tidak ada teks yang menempel/hilang.")

    # --- HALAMAN LAMPIRAN: X-RAY VISION ---
    pdf.add_page() 
    pdf.set_fill_color(44, 62, 80); pdf.set_font('Arial', 'B', 12); pdf.set_text_color(255, 255, 255) 
    pdf.cell(180, 10, ' X-RAY VISION: RAW DATA EXTRACTION (SYSTEM VIEW)', 0, 1, 'C', fill=True); pdf.ln(6)

    pdf.set_font('Arial', 'B', 9); pdf.set_text_color(192, 57, 43) 
    xray_warning = "WARNING: Teks di bawah ini adalah tampilan MENTAH (Raw Text) bagaimana sistem ATS membaca CV Anda. Jika teks terlihat berantakan, melompat, atau menyatu tanpa spasi (biasa terjadi pada CV desain 2 kolom/tabel), maka data Anda dipastikan GAGAL tersimpan dengan baik di database HR perusahaan."
    pdf.multi_cell(180, 5, xray_warning); pdf.ln(4)

    safe_raw_text = raw_text.encode('latin-1', 'replace').decode('latin-1')
    safe_raw_text = re.sub(r'\n{3,}', '\n\n', safe_raw_text) 
    
    pdf.set_font('Courier', '', 8.5); pdf.set_text_color(50, 50, 50); pdf.set_fill_color(248, 249, 249) 
    pdf.multi_cell(180, 4.5, safe_raw_text[:3500] + ("\n\n[...TEXT TRUNCATED...]" if len(safe_raw_text) > 3500 else ""), fill=True)

    return bytes(pdf.output(dest='S'))

# --- UI ADMIN WEB (MODERN SaaS CSS) ---
st.markdown("""
<style>
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 25px; }
    .m-card { background: white; border-radius: 12px; padding: 15px; border: 1px solid #eef2f6; box-shadow: 0 4px 6px rgba(0,0,0,0.02); position: relative; transition: transform 0.2s; }
    .m-card:hover { transform: translateY(-3px); box-shadow: 0 10px 15px rgba(0,0,0,0.05); }
    .m-title { font-size: 0.8rem; color: #64748b; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }
    .m-val { font-size: 1.6rem; font-weight: 800; color: #1e293b; margin: 5px 0; }
    .m-status { font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 10px; display: inline-block; }
    .st-good { background: #dcfce7; color: #15803d; } .st-warn { background: #fef9c3; color: #a16207; } .st-crit { background: #fee2e2; color: #b91c1c; }
    .p-bar-bg { background: #f1f5f9; height: 6px; border-radius: 3px; margin-top: 10px; overflow: hidden; }
    .p-bar-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ⚙️ Admin Console"); st.info("Dapur Internal Reviewer CV"); st.divider()
    st.markdown("### 🚦 System: **Online**"); st.divider(); st.markdown("<small>v4.0.5 Premium - Layout Fixed</small>", unsafe_allow_html=True)

st.title("💼 CV Audit SaaS Dashboard")
uploaded_file = st.file_uploader("Drop CV PDF Client di sini", type=["pdf"])

if uploaded_file:
    MAX_FILE_SIZE = 200 * 1024 * 1024 
    if uploaded_file.size > MAX_FILE_SIZE:
        st.error("⚠️ Ukuran file terlalu besar! Batas maksimal ukuran dokumen CV adalah 200MB.")
    else:
        with st.status("🔍 Menganalisis Dokumen...", expanded=True) as status:
            try:
                p = st.progress(0); time.sleep(0.3); p.progress(30)
                with pdfplumber.open(uploaded_file) as pdf:
                    raw_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
                    num_pages = len(pdf.pages)
                p.progress(70); res = audit_cv_final(raw_text, num_pages); p.progress(100)
                status.update(label="✅ Audit Selesai", state="complete", expanded=False)
                
                # --- UPDATE STATUS LOGIC KONTAK (Presisi) ---
                missing_c = sum(v == False for v in res['contact_info'].values())
                contact_count = 4 - missing_c
                
                def get_ui_meta(val, type='perc'):
                    if type == 'perc': 
                        if val >= 80: return "SANGAT BAIK", "st-good", "#22c55e"
                        if val >= 50: return "BUTUH PERBAIKAN", "st-warn", "#eab308"
                        return "KRITIS", "st-crit", "#ef4444"
                    elif type == 'contact':
                        if val == 4: return "LENGKAP", "st-good", "100%"
                        if val == 3: return "CUKUP", "st-warn", "75%"
                        if val == 2: return "MINIM", "st-warn", "50%"
                        return "KRITIS", "st-crit", "25%"
                    return "", "", ""

                st.markdown(f"""
                <div class="metric-grid">
                    <div class="m-card">
                        <div class="m-title">📖 Keterbacaan</div>
                        <div class="m-val">{res['parsability_score']}%</div>
                        <div class="m-status {get_ui_meta(res['parsability_score'])[1]}">{get_ui_meta(res['parsability_score'])[0]}</div>
                        <div class="p-bar-bg"><div class="p-bar-fill" style="width:{res['parsability_score']}%; background:{get_ui_meta(res['parsability_score'])[2]}"></div></div>
                    </div>
                    <div class="m-card">
                        <div class="m-title">⚡ Skor XYZ</div>
                        <div class="m-val">{int(res['xyz_score'])}%</div>
                        <div class="m-status {get_ui_meta(res['xyz_score'])[1]}">{get_ui_meta(res['xyz_score'])[0]}</div>
                        <div class="p-bar-bg"><div class="p-bar-fill" style="width:{res['xyz_score']}%; background:{get_ui_meta(res['xyz_score'])[2]}"></div></div>
                    </div>
                    <div class="m-card">
                        <div class="m-title">📞 Kontak & Domisili</div>
                        <div class="m-val">{contact_count}/4</div>
                        <div class="m-status {get_ui_meta(contact_count, 'contact')[1]}">{get_ui_meta(contact_count, 'contact')[0]}</div>
                        <div class="p-bar-bg"><div class="p-bar-fill" style="width:{get_ui_meta(contact_count, 'contact')[2]}; background:{'#22c55e' if contact_count==4 else ('#ef4444' if contact_count<=1 else '#eab308')}"></div></div>
                    </div>
                    <div class="m-card">
                        <div class="m-title">⏳ Masa Kerja</div>
                        <div class="m-val">{res['total_tenure']} Thn</div>
                        <div class="m-status st-good">VERIFIED</div>
                        <div class="p-bar-bg"><div class="p-bar-fill" style="width:100%; background:#2980b9"></div></div>
                    </div>
                    <div class="m-card">
                        <div class="m-title">📄 Halaman</div>
                        <div class="m-val">{res['pages']} Hal</div>
                        <div class="m-status {'st-good' if res['pages']<=2 else 'st-crit'}">{'IDEAL' if res['pages']<=2 else 'OVERLIMIT'}</div>
                        <div class="p-bar-bg"><div class="p-bar-fill" style="width:{'100%' if res['pages']<=2 else '40%'}; background:{'#22c55e' if res['pages']<=2 else '#ef4444'}"></div></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                tab1, tab2, tab3 = st.tabs(["📊 Diagnostic Overview", "📤 Export PDF", "🛠️ Raw Text"])
                with tab1:
                    st.markdown("### Executive Insights")
                    col1, col2 = st.columns(2)
                    with col1:
                        with st.container(border=True):
                            st.markdown("##### 📌 Extracted Industry Keywords")
                            if res['top_keywords']:
                                st.markdown(" ".join([f"<span style='background-color: #e8f4f8; color: #2980b9; padding: 4px 12px; border-radius: 15px; font-size: 13px; font-weight: bold; border: 1px solid #b3d7ff; display: inline-block; margin-right: 5px; margin-bottom: 5px;'>{k}</span>" for k in res['top_keywords']]), unsafe_allow_html=True)
                            else: st.write("*Tidak cukup data.*")
                    with col2:
                        with st.container(border=True):
                            st.markdown("##### ⚠️ Cliché Buzzword Detection")
                            if res['cliche_words']:
                                st.error(f"Terdeteksi kata usang: **{', '.join(res['cliche_words']).title()}**")
                            else: st.success("CV bersih dari kata sifat klise/pasif.")

                    with st.container(border=True):
                        st.markdown("##### 💡 Reviewer Notes")
                        if res['xyz_score'] < 50: st.error("**Kualitas Konten:** Rendah. Rekomendasikan Klien untuk ubah format naratif ke 'Action Verb + Konteks + Angka'.")
                        else: st.info("**Kualitas Konten:** Kuat. Klien sudah menggunakan metrik kuantitatif dengan baik.")

                with tab2:
                    pdf_bytes = create_pdf(res, raw_text, uploaded_file.name.split('.')[0])
                    st.download_button("⬇️ DOWNLOAD PREMIUM REPORT", pdf_bytes, f"Audit_{uploaded_file.name}", "application/pdf", type="primary", use_container_width=True)
                with tab3: st.code(raw_text)

            except Exception as e:
                status.update(label="❌ Terjadi Kesalahan", state="error", expanded=True)
                st.error("⚠️ Sistem gagal membaca dokumen.")
