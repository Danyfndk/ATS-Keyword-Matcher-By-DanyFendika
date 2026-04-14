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
    
    # 1. ATS Parsability (Keterbacaan Mesin)
    # Menghitung rasio karakter non-alphanumeric (simbol aneh)
    total_chars = len(text)
    if total_chars > 0:
        special_chars = len(re.findall(r'[^a-zA-Z0-9\s]', text))
        parsability_ratio = (total_chars - special_chars) / total_chars
        results['parsability'] = {
            'score': round(parsability_ratio * 100, 1),
            'status': "Sangat Baik" if parsability_ratio > 0.85 else "Perlu Perbaikan (Terlalu banyak simbol/format rumit)"
        }

    # 2. Section Header Recognition (Kelengkapan Struktur)
    sections = {
        'Experience/Pengalaman': r'(experience|pengalaman kerja|work history|career)',
        'Education/Pendidikan': r'(education|pendidikan|academic)',
        'Skills/Keahlian': r'(skills|keahlian|competencies|kemampuan)',
        'Summary/Profile': r'(summary|profile|tentang saya|overview)',
        'Contact/Kontak': r'(contact|informasi kontak|telepon|email)'
    }
    found_sections = []
    missing_sections = []
    for section, pattern in sections.items():
        if re.search(pattern, text_clean):
            found_sections.append(section)
        else:
            missing_sections.append(section)
    results['sections'] = {'found': found_sections, 'missing': missing_sections}

    # 3. Word Volume & Brevity (Kepadatan Teks)
    words = text.split()
    word_count = len(words)
    if word_count < 300:
        volume_status = "Terlalu Singkat (Kurang detail)"
    elif 300 <= word_count <= 700:
        volume_status = "Optimal (Ideal untuk 1-2 halaman)"
    else:
        volume_status = "Terlalu Padat (Beresiko diabaikan rekruter)"
    results['volume'] = {'count': word_count, 'status': volume_status}

    # 4. Digital Footprint (LinkedIn & Link Verifier)
    linkedin_found = re.search(r'linkedin\.com\/in\/[a-z0-9\-]+', text_clean)
    github_found = re.search(r'github\.com\/[a-z0-9\-]+', text_clean)
    results['footprint'] = {
        'linkedin': True if linkedin_found else False,
        'github': True if github_found else False
    }

    # 5. Buzzword & Fluff Detector (Pendeteksi Klise)
    buzzwords = ['hard worker', 'pekerja keras', 'team player', 'think outside the box', 'synergy', 'fast learner', 'cepat belajar', 'responsible']
    found_buzz = [word for word in buzzwords if re.search(r'\b' + word + r'\b', text_clean)]
    results['buzzwords'] = found_buzz

    # 6. Quantifiable Metrics (Data Storytelling)
    # Mencari angka, persentase, atau simbol mata uang
    metrics = re.findall(r'(\b\d+(?:[\.,]\d+)?%|\b\d{2,}\b)', text)
    results['metrics_count'] = len(metrics)

    # 7. Bullet Point Density
    bullet_patterns = [r'^\s*[\-\•\-\*]\s+', r'^\s*\d+\.\s+']
    bullet_count = 0
    for line in lines:
        if any(re.match(p, line.strip()) for p in bullet_patterns):
            bullet_count += 1
    results['bullet_count'] = bullet_count

    return results

# --- ANTARMUKA STREAMLIT (FRONTEND) ---

st.title("🛡️ CV Auditor & ATS Readiness Evaluator")
st.markdown("Aplikasi ini menganalisis kualitas struktur CV Anda berdasarkan standar teknis sistem ATS dan praktik terbaik Human Capital.")

uploaded_file = st.file_uploader("Unggah CV Anda (Format PDF)", type=["pdf"])

if uploaded_file:
    with st.spinner("Menganalisis anatomi dokumen..."):
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"
        
        if not full_text.strip():
            st.error("Gagal membaca teks. CV Anda mungkin berupa gambar hasil scan (bukan teks asli).")
        else:
            report = audit_cv(full_text)
            
            # --- DASHBOARD HASIL ---
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Skor Keterbacaan Mesin", f"{report['parsability']['score']}%")
            with col2:
                st.metric("Total Kata", report['volume']['count'])
            with col3:
                st.metric("Metrik Data Ditemukan", report['metrics_count'])

            st.divider()

            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("📂 Kelengkapan Struktur")
                for sec in report['sections']['found']:
                    st.write(f"✅ {sec}")
                for sec in report['sections']['missing']:
                    st.write(f"❌ {sec} (Tidak Terdeteksi)")
                
                st.subheader("🌐 Jejak Digital")
                st.write(f"{'✅' if report['footprint']['linkedin'] else '❌'} LinkedIn Profile")
                st.write(f"{'✅' if report['footprint']['github'] else '❌'} Portfolio/GitHub")

            with c2:
                st.subheader("✍️ Analisis Diksi & Konten")
                st.info(f"**Status Kepadatan:** {report['volume']['status']}")
                
                if report['buzzwords']:
                    st.warning(f"**Buzzwords Terdeteksi:** {', '.join(report['buzzwords'])}")
                    st.caption("Saran: Ganti kata klise di atas dengan bukti pencapaian nyata.")
                else:
                    st.success("Bagus! Tidak ditemukan kata-kata klise yang berlebihan.")

                st.subheader("📊 Struktur Poin (Bullet Points)")
                if report['bullet_count'] < 5:
                    st.error(f"Ditemukan {report['bullet_count']} poin. Terlalu sedikit. Gunakan bullet points untuk memudahkan rekruter melakukan skimming.")
                else:
                    st.success(f"Ditemukan {report['bullet_count']} poin. Struktur list sudah cukup baik.")

            st.divider()
            st.subheader("💡 Rekomendasi Auditor")
            if report['parsability']['score'] < 85:
                st.warning("- **Perbaiki Format:** CV Anda memiliki banyak karakter non-standar. Gunakan font standar seperti Arial atau Calibri dan hindari tabel kompleks.")
            if report['metrics_count'] < 3:
                st.warning("- **Data Storytelling:** Tambahkan angka atau persentase untuk membuktikan keberhasilan Anda (misal: 'Meningkatkan penjualan 15%' alih-alih 'Meningkatkan penjualan').")
            if not report['footprint']['linkedin']:
                st.warning("- **Optimasi Profil:** Tambahkan tautan profil LinkedIn yang aktif untuk meningkatkan kredibilitas profesional.")
            if report['sections']['missing']:
                st.warning(f"- **Header Hilang:** Pastikan Anda memiliki bagian {', '.join(report['sections']['missing'])} dengan judul yang standar.")
