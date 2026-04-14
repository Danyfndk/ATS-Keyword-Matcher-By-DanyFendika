import streamlit as st
import pdfplumber
import re
import nltk
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="CV Auditor & ATS Readiness", page_icon="📑", layout="wide")

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
    return set(action_verbs) # Diubah ke Set agar pencarian (lookup) lebih cepat (O(1))

ACTION_VERBS = setup_nlp()

# --- FUNGSI UTAMA AUDITOR (COMMERCIAL LOGIC) ---
def calculate_tenure(text):
    year_patterns = re.findall(r'(\b20\d{2}\b)\s*[\-\–]\s*(\b20\d{2}\b|present|now|current)', text.lower())
    total_years = 0
    current_year = datetime.now().year
    for start, end in year_patterns:
        start_yr = int(start)
        end_yr = current_year if end in ['present', 'now', 'current'] else int(end)
        diff = end_yr - start_yr
        if 0 < diff < 40: # Logika batas wajar masa kerja
            total_years += diff
    return total_years

def audit_cv_final(text, num_pages):
    text_clean = text.lower()
    lines = text.split('\n')
    report = {}

    # 1. Parsability (FIXED: Whitelist simbol-simbol wajar dalam CV seperti bullet points dll)
    special_chars = len(re.findall(r'[^\w\s\.\,\@\+\-\(\)\/\:\&\|\%\•\▪\●\*]', text))
    parsability = ((len(text) - special_chars) / len(text)) * 100 if len(text) > 0 else 0
    report['parsability_score'] = min(max(round(parsability, 1), 0), 100) # Memastikan skor selalu 0-100

    # 2. Sections Header
    sections = {'Experience': r'\b(experience|pengalaman)\b', 'Education': r'\b(education|pendidikan)\b', 
                'Skills': r'\b(skills|keahlian)\b', 'Summary': r'\b(summary|profile|overview)\b'}
    found_sec = [s for s, p in sections.items() if re.search(p, text_clean)]
    missing_sec = [s for s in sections.keys() if s not in found_sec]
    report['section_score'] = (len(found_sec) / len(sections)) * 100
    report['missing_sections'] = missing_sec

    # 3. XYZ & Metrics (FIXED: Hitung metrik secara independen PER BARIS)
    valid_lines = 0
    score_per_line = 0
    global_metrics = re.findall(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', text) # Hitung total metrik di dokumen
    
    for line in lines:
        clean_line = line.strip().lower()
        if len(clean_line) > 30: # Asumsi panjang 1 kalimat deskripsi
            valid_lines += 1
            words_in_line = set(re.findall(r'\b\w+\b', clean_line))
            
            has_verb = any(verb in words_in_line for verb in ACTION_VERBS)
            has_metric = bool(re.search(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', clean_line)) # Evaluasi metrik tepat di baris ini
            
            if has_verb and has_metric: 
                score_per_line += 1.0
            elif has_verb: 
                score_per_line += 0.5
            elif has_metric: 
                score_per_line += 0.5
                
    report['xyz_score'] = min(max(round((score_per_line / valid_lines * 100) if valid_lines > 0 else 0, 1), 0), 100)
    report['metrics_count'] = len(global_metrics)
    report['total_tenure'] = calculate_tenure(text)

    # 4. Page Length
    report['pages'] = num_pages

    # 5. Contact Info Parsing (FIXED: Regex anti false-positive dengan range tahun)
    email_found = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    # Regex telepon yang mencari standar +62/08 atau standar internasional yang rapat
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
    
    # Pengurangan skor untuk pelanggaran fatal standar global
    if report['pages'] > 2:
        final_score -= 10  
    if not report['contact_info']['Email'] or not report['contact_info']['Phone']:
        final_score -= 15  
        
    report['final_score'] = min(max(round(final_score, 1), 0), 100) # Safeguard bounds (0-100)
    return report

# --- FUNGSI GENERATOR PDF (ENTERPRISE LAYOUT) ---
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 18) 
        self.set_text_color(44, 62, 80) 
        self.cell(180, 8, 'CV AUDIT & ATS READINESS REPORT', 0, 1, 'C')
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
        self.cell(180, 4, 'Strictly evaluated based on enterprise ATS standards and Google XYZ Formula.', 0, 1, 'C')
        self.set_font('Arial', 'B', 9)
        self.set_text_color(44, 62, 80)
        self.cell(180, 5, 'Audit Conducted by: Dany Fendika - ATS Readiness Specialist & HR Data Analyst', 0, 1, 'C')
        self.set_font('Arial', 'I', 8)
        self.set_text_color(127, 140, 141)
        self.cell(180, 4, f'Page {self.page_no()}', 0, 0, 'C')

def create_pdf(report_data, raw_text):
    pdf = PDFReport(orientation='P', unit='mm', format='A4')
    pdf.set_margins(15, 20, 15) 
    pdf.set_auto_page_break(auto=True, margin=28)
    pdf.add_page()
    
    # --- 1. SCORECARD DASHBOARD ---
    pdf.set_fill_color(236, 240, 241) 
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 1. OVERALL ATS READINESS SCORE', 0, 1, 'L', fill=True)
    pdf.ln(5)
    
    if report_data['final_score'] >= 80: 
        pdf.set_text_color(39, 174, 96) 
    elif report_data['final_score'] >= 50: 
        pdf.set_text_color(230, 126, 34) 
    else: 
        pdf.set_text_color(192, 57, 43) 
        
    pdf.set_font('Arial', 'B', 34)
    pdf.cell(180, 15, f"{report_data['final_score']} / 100", 0, 1, 'C')
    pdf.ln(6)
    
    # --- 2. GLOBAL BENCHMARK MATRIX ---
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 6, 'GLOBAL ATS BENCHMARK MATRIX:', 0, 1, 'L')
    pdf.ln(1)
    
    pdf.set_font('Arial', 'B', 9)
    pdf.set_draw_color(200, 200, 200) 
    
    pdf.set_fill_color(233, 247, 239) 
    pdf.cell(35, 7, ' 80% - 100%', border=1, align='C', fill=True)
    pdf.set_font('Arial', '', 9)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(145, 7, ' EXCELLENT: Probabilitas tinggi lolos ATS. Format & struktur sangat ideal.', border=1, ln=1)
    
    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(253, 242, 233) 
    pdf.cell(35, 7, ' 50% - 79%', border=1, align='C', fill=True)
    pdf.set_font('Arial', '', 9)
    pdf.cell(145, 7, ' FAIR: Berisiko. Perlu perbaikan kualitas kalimat dan metrik data.', border=1, ln=1)
    
    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(250, 224, 228) 
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
    
    pdf.set_font('Arial', '', 9.5)
    pdf.set_text_color(60, 60, 60)
    intro_text = (
        "Empat metrik di bawah ini dievaluasi berdasarkan standar rekrutmen global dan cara kerja algoritma "
        "Applicant Tracking System (ATS). Sistem memvalidasi integritas format, kekuatan narasi pencapaian, "
        "serta kuantifikasi data untuk memastikan CV Anda siap bersaing secara profesional."
    )
    pdf.multi_cell(180, 5, intro_text)
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 5, f"A. ATS Parsability (Text Readability) : {report_data['parsability_score']}%", 0, 1)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(127, 140, 141)
    pdf.multi_cell(180, 4.5, "Note: Semakin tinggi skor, semakin aman CV dari risiko 'rusak' saat diekstrak ATS. Hindari desain 2 kolom atau penggunaan tabel.")
    pdf.ln(4)

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

    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 5, f"C. Quantifiable Metrics: {report_data['metrics_count']} Data Points Found", 0, 1)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(127, 140, 141)
    pdf.multi_cell(180, 4.5, "Note: Jumlah metrik (angka/persentase) di CV Anda sebagai bukti pencapaian kerja yang nyata.")
    pdf.ln(4)

    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 5, f"D. Document Format: {report_data['pages']} Pages", 0, 1)
    pdf.set_font('Arial', 'I', 9)
    pdf.set_text_color(127, 140, 141)
    pdf.multi_cell(180, 4.5, "Note: Standar panjang dokumen resume profesional global adalah 1 hingga maksimal 2 halaman.")
    pdf.ln(6)

    # --- 4. DIAGNOSTIC RESULTS & ANALYSIS ---
    pdf.set_fill_color(236, 240, 241)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(180, 8, ' 3. DIAGNOSTIC RESULTS & ANALYSIS', 0, 1, 'L', fill=True)
    pdf.ln(4)
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(20, 20, 20)
    
    # 1. Struktur / Section (Teks sudah dirapikan sesuai standar pilar)
    if report_data['missing_sections']:
        pdf.multi_cell(180, 5.5, f"[-] MISSING SECTIONS: ATS gagal mendeteksi bagian: {', '.join(report_data['missing_sections']).title()}. Standar global mewajibkan 4 pilar utama CV: Summary (Profil), Experience (Pengalaman), Education (Pendidikan), dan Skills (Keahlian).")
    else:
        pdf.multi_cell(180, 5.5, "[+] STRUCTURE: Sangat baik. Seluruh 4 pilar wajib (Summary, Experience, Education, Skills) telah terdeteksi oleh sistem.")
    pdf.ln(2)

    # 2. Konten / XYZ
    if report_data['xyz_score'] < 50:
        pdf.multi_cell(180, 5.5, "[-] CONTENT: Kalimat pengalaman kerja kurang kuat. Gunakan format Action Verb + Konteks + Metrik (Angka/Persentase) untuk mendeskripsikan dampak pekerjaan.")
    else:
        pdf.multi_cell(180, 5.5, "[+] CONTENT: Penggunaan Action Verbs dan metrik kuantitatif pada pengalaman kerja sudah sangat baik.")
    pdf.ln(2)

    # 3. Kontak
    missing_contacts = [k for k, v in report_data['contact_info'].items() if not v]
    if missing_contacts:
        pdf.multi_cell(180, 5.5, f"[-] CONTACT INFO: ATS gagal membaca kontak: {', '.join(missing_contacts)}. Pastikan menggunakan teks standar, hindari penggunaan ikon/gambar tanpa keterangan teks.")
    else:
        pdf.multi_cell(180, 5.5, "[+] CONTACT INFO: Valid. Email, Telepon, dan tautan LinkedIn berhasil diekstrak dengan baik.")
    pdf.ln(2)
        
    # 4. Limit Halaman
    if report_data['pages'] > 2:
        pdf.multi_cell(180, 5.5, f"[-] PAGE LIMIT: CV Anda memiliki {report_data['pages']} halaman. Pertimbangkan untuk memadatkan informasi menjadi maksimal 1-2 halaman agar lebih efektif.")
    pdf.ln(3)

    # --- HALAMAN 2: X-RAY VISION ---
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
    pdf.set_font('Courier', '', 8.5)
    pdf.set_text_color(50, 50, 50)
    pdf.set_fill_color(248, 249, 249) 
    pdf.multi_cell(180, 4.5, safe_raw_text[:3500] + ("\n\n[...TEXT TRUNCATED...]" if len(safe_raw_text) > 3500 else ""), fill=True)

    return bytes(pdf.output(dest='S'))

# --- UI STREAMLIT (ENTERPRISE DASHBOARD STYLE) ---
st.title("💼 CV Auditor & ATS Readiness")
st.markdown("Evaluasi anatomi dokumen CV Anda berdasarkan standar global **Human Capital** dan **Mesin ATS**.")

with st.container(border=True):
    uploaded_file = st.file_uploader("Upload Dokumen CV (Hanya format PDF - Maksimal 1MB)", type=["pdf"])

if uploaded_file:
    MAX_FILE_SIZE = 1 * 1024 * 1024 
    
    if uploaded_file.size > MAX_FILE_SIZE:
        st.error("⚠️ Ukuran file terlalu besar! Batas maksimal ukuran dokumen CV adalah 1MB. Silakan kompres CV Anda terlebih dahulu.")
    else:
        with st.spinner("Mesin sedang mengekstrak dan mengaudit dokumen..."):
            with pdfplumber.open(uploaded_file) as pdf:
                num_pages = len(pdf.pages) 
                raw_text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            
            if raw_text:
                res = audit_cv_final(raw_text, num_pages) 
                
                st.write("") 
                
                # --- ROW 1: SCORE & MATRIX ---
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
                    
                    missing_c = sum(value == False for value in res['contact_info'].values())
                    m3.metric("Kelengkapan Kontak", f"{3 - missing_c}/3", help="Deteksi keberadaan Email, Nomor HP, dan Profil LinkedIn.")
                    m4.metric("Jumlah Halaman", f"{res['pages']} Hal", help="Standar CV profesional adalah 1 - 2 Halaman.")

                # --- ROW 3: REPORT & X-RAY ---
                st.write("")
                col_dl, col_xray = st.columns([1, 1])
                
                with col_dl:
                    with st.container(border=True):
                        st.subheader("📄 Ekspor Laporan")
                        st.markdown("Unduh hasil audit resmi (PDF) berisi rekomendasi dan tampilan X-Ray Vision.")
                        
                        st.write("") 
                        st.write("") 

                        pdf_bytes = create_pdf(res, raw_text)
                        
                        nama_file_asli = uploaded_file.name.rsplit('.', 1)[0]
                        tanggal_sekarang = datetime.now().strftime('%d-%m-%Y')
                        nama_file_download = f"{nama_file_asli}-{tanggal_sekarang}.pdf"
                        
                        st.download_button(
                            label="⬇️ Download Enterprise PDF Report",
                            data=pdf_bytes,
                            file_name=nama_file_download,
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
