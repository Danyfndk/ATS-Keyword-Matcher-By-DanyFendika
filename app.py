import streamlit as st
import pdfplumber
import re
import nltk
from nltk.corpus import stopwords

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="CV Auditor & ATS Readiness", layout="wide")

# --- INISIALISASI NLTK ---
@st.cache_resource
def load_nlp_data():
    nltk.download('stopwords', quiet=True)
    nltk.download('punkt', quiet=True)
    return set(stopwords.words('english')).union(set(stopwords.words('indonesian')))

stop_words = load_nlp_data()

# --- LOGIKA AUDITOR (BACKEND) ---

def audit_cv(text):
    results = {}
    text_clean = text.lower()
    lines = text.split('\n')
    
    # 1. ATS Parsability
    total_chars = len(text)
    if total_chars > 0:
        special_chars = len(re.findall(r'[^a-zA-Z0-9\s\.\,\@\+\-\(\)]', text))
        parsability_ratio = (total_chars - special_chars) / total_chars
        results['parsability'] = {
            'score': round(parsability_ratio * 100, 1),
            'status': "Sangat Baik" if parsability_ratio > 0.85 else "Perlu Perbaikan"
        }

    # 2. Section Header & Content Recognition (LEBIH CERDAS)
    found_sections = []
    missing_sections = []

    # -- Cek Pengalaman, Pendidikan, Skil (Tetap Header Matching) --
    if re.search(r'(experience|pengalaman|work history)', text_clean):
        found_sections.append('Experience/Pengalaman')
    else: missing_sections.append('Experience/Pengalaman')

    if re.search(r'(education|pendidikan)', text_clean):
        found_sections.append('Education/Pendidikan')
    else: missing_sections.append('Education/Pendidikan')

    if re.search(r'(skills|keahlian|competencies)', text_clean):
        found_sections.append('Skills/Keahlian')
    else: missing_sections.append('Skills/Keahlian')

    # -- Cek Summary (Content Matching) --
    # Asumsi: Jika ada paragraf di atas section Experience, itu adalah Summary
    exp_match = re.search(r'(experience|pengalaman)', text_clean)
    if exp_match and exp_match.start() > 150:
        found_sections.append('Summary/Profile (Terdeteksi dari format paragraf)')
    elif re.search(r'(summary|profile|tentang saya|overview)', text_clean):
        found_sections.append('Summary/Profile')
    else:
        missing_sections.append('Summary/Profile')

    # -- Cek Kontak (Content Matching: Deteksi Email atau No HP) --
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    # Menghapus spasi dan strip sementara untuk mengecek nomor HP (misal +62 8125...)
    text_no_spaces = re.sub(r'[\s\-]', '', text) 
    has_phone = bool(re.search(r'\+?\d{10,14}', text_no_spaces))
    
    if has_email or has_phone:
        found_sections.append('Contact/Kontak (Terdeteksi via Email/Telepon)')
    else:
        missing_sections.append('Contact/Kontak')
    results['sections'] = {'found': found_sections, 'missing': missing_sections}

    # 3. Word Volume
    words = text.split()
    word_count = len(words)
    if word_count < 250:
        volume_status = "Terlalu Singkat (Kurang detail pencapaian)"
    elif 250 <= word_count <= 700:
        volume_status = "Optimal (Ideal untuk 1-2 halaman)"
    else:
        volume_status = "Terlalu Padat (Beresiko diabaikan rekruter)"
    results['volume'] = {'count': word_count, 'status': volume_status}

    # 4. Digital Footprint (Diperlonggar)
    # Mencari kata 'linkedin' atau URL linkedin. Ikon tidak terbaca oleh parser.
    linkedin_found = re.search(r'linkedin', text_clean)
    github_found = re.search(r'(github|portfolio|behance|dribbble|gitlab)', text_clean)
    results['footprint'] = {
        'linkedin': True if linkedin_found else False,
        'github': True if github_found else False
    }

    # 5. Buzzword Detector
    buzzwords = ['hard worker', 'pekerja keras', 'team player', 'think outside the box', 'synergy', 'fast learner', 'cepat belajar']
    found_buzz = [word for word in buzzwords if re.search(r'\b' + word + r'\b', text_clean)]
    results['buzzwords'] = found_buzz

    # 6. Quantifiable Metrics
    metrics = re.findall(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', text)
    results['metrics_count'] = len(metrics)

    # 7. Bullet Point Density
    bullet_patterns = [r'^\s*[\-\•\-\*]\s+', r'^\s*\d+\.\s+']
    bullet_count = sum(1 for line in lines if any(re.match(p, line.strip()) for p in bullet_patterns))
    results['bullet_count'] = bullet_count

    return results

# --- ANTARMUKA STREAMLIT (FRONTEND) ---

st.title("🛡️ CV Auditor & ATS Readiness Evaluator")
st.markdown("Aplikasi ini menganalisis kualitas anatomi CV Anda berdasarkan standar teknis sistem pembaca mesin (ATS).")

uploaded_file = st.file_uploader("Unggah CV Anda (Format PDF)", type=["pdf"])

if uploaded_file:
    with st.spinner("Mengekstrak dan menganalisis teks dokumen..."):
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"
        
        if not full_text.strip():
            st.error("Gagal membaca teks. CV Anda mungkin berupa gambar atau desain Canva yang disatukan menjadi gambar rata (flattened).")
        else:
            report = audit_cv(full_text)
            
            # --- DASHBOARD HASIL ---
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Skor Keterbacaan Mesin", f"{report['parsability']['score']}%")
            with col2:
                st.metric("Total Kata", report['volume']['count'])
            with col3:
                st.metric("Metrik Data (Angka) Ditemukan", report['metrics_count'])

            st.divider()

            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("📂 Kelengkapan Struktur")
                for sec in report['sections']['found']:
                    st.success(f"✅ {sec}")
                for sec in report['sections']['missing']:
                    st.error(f"❌ {sec} (Tidak Terdeteksi)")
                
                st.subheader("🌐 Jejak Digital")
                if report['footprint']['linkedin']:
                    st.success("✅ LinkedIn Profile Terdeteksi")
                else:
                    st.error("❌ LinkedIn Profile")
                
                if report['footprint']['github']:
                    st.success("✅ Portfolio/Link Tambahan Terdeteksi")
                else:
                    st.error("❌ Portfolio/Link Tambahan")

            with c2:
                st.subheader("✍️ Analisis Diksi & Konten")
                st.info(f"**Status Kepadatan:** {report['volume']['status']}")
                
                if report['buzzwords']:
                    st.warning(f"**Buzzwords Terdeteksi:** {', '.join(report['buzzwords'])}")
                else:
                    st.success("Bagus! Tidak ditemukan kata-kata klise yang berlebihan.")

                st.subheader("📊 Struktur Poin (Bullet Points)")
                if report['bullet_count'] < 5:
                    st.error(f"Ditemukan {report['bullet_count']} poin. Terlalu sedikit. CV dengan format paragraf naratif (seperti pengalaman kerja di CV ini) sangat sulit di-skimming oleh rekruter.")
                else:
                    st.success(f"Ditemukan {report['bullet_count']} poin. Struktur list sudah cukup baik.")

            st.divider()
            st.subheader("💡 Rekomendasi Auditor")
            if "Summary/Profile" in report['sections']['missing']:
                st.warning("- **Header Hilang:** Sangat disarankan untuk tetap menuliskan kata 'Summary' atau 'Profile' agar mesin mudah memetakan data Anda.")
            if not report['footprint']['linkedin']:
                st.warning("- **Krisis Keterbacaan Ikon:** Mesin ATS tidak bisa membaca ikon/logo LinkedIn. Tulislah URL Anda secara eksplisit (contoh: *linkedin.com/in/namaanda*) atau minimal tulis kata 'LinkedIn'.")
            if report['bullet_count'] < 5:
                st.warning("- **Ubah Paragraf Menjadi Poin:** Rekruter hanya punya waktu 7 detik. Ubah deskripsi pengalaman kerja Anda dari bentuk paragraf panjang menjadi *bullet points*.")
