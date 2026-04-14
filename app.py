import streamlit as st
import pdfplumber
import re
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Open-Source ATS Matcher", layout="wide")

# --- INISIALISASI NLTK ---
@st.cache_resource
def load_nlp_tools():
    # Download stopwords
    nltk.download('stopwords', quiet=True)
    
    # Siapkan stopwords gabungan (Inggris & Indonesia)
    stop_words_en = set(stopwords.words('english'))
    stop_words_id = set(stopwords.words('indonesian'))
    all_stopwords = list(stop_words_en.union(stop_words_id))
    
    return all_stopwords

custom_stopwords = load_nlp_tools()

# --- FUNGSI EKSTRAKSI PDF ---
def extract_text_from_pdf(uploaded_file):
    text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    return text

# --- FUNGSI CEK PROFESIONALITAS (Pengganti LanguageTool) ---
def check_professionalism(text):
    issues = []
    text_lower = text.lower()

    # 1. Deteksi kata informal/kasual
    casual_words = ['bikin', 'ngerjain', 'gue', 'aku', 'nyari', 'gonna', 'wanna', 'stuff', 'things']
    found_casual = [word for word in casual_words if re.search(r'\b' + word + r'\b', text_lower)]
    if found_casual:
        issues.append(f"⚠️ **Hindari kata informal:** Ditemukan kata '{', '.join(found_casual)}'. Gunakan bahasa yang lebih profesional.")

    # 2. Deteksi Kata Ganti Orang (Di CV, sebaiknya dihindari)
    pronouns = [' saya ', ' aku ', ' i ', ' me ', ' my ']
    found_pronouns = [p.strip() for p in pronouns if p in text_lower]
    if len(found_pronouns) > 2:
        issues.append("⚠️ **Kata Ganti Orang Berlebih:** CV yang baik menghindari kata ganti (saya, I, me). Langsung gunakan 'Action Verbs' (contoh: 'Memimpin tim...' bukan 'Saya memimpin tim...').")

    # 3. Pengecekan Email
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if emails:
        for email in emails:
            if re.search(r'\d{4,}', email): 
                issues.append(f"ℹ️ **Saran Email:** Email '{email}' mengandung banyak angka. Pertimbangkan menggunakan nama bersih agar terlihat lebih profesional.")
    else:
        issues.append("❌ **Data Kontak:** Tidak ditemukan alamat email di dalam CV Anda.")

    if not issues:
        issues.append("✅ Kosakata dan format teks terlihat profesional.")

    return issues

# --- FUNGSI ATS SCORING & KEYWORD EXTRACTION ---
def analyze_ats_metrics(cv_text, jd_text):
    # 1. Menghitung Cosine Similarity (Skor ATS)
    vectorizer = TfidfVectorizer(stop_words=custom_stopwords, ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform([jd_text, cv_text])
    match_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0] * 100
    
    # 2. Ekstraksi Kata Kunci yang Hilang
    jd_vectorizer = TfidfVectorizer(stop_words=custom_stopwords, ngram_range=(1, 2))
    jd_vectorizer.fit([jd_text])
    jd_keywords = set(jd_vectorizer.get_feature_names_out())
    
    cv_vectorizer = TfidfVectorizer(stop_words=custom_stopwords, ngram_range=(1, 2))
    cv_vectorizer.fit([cv_text])
    cv_keywords = set(cv_vectorizer.get_feature_names_out())
    
    missing_keywords = list(jd_keywords - cv_keywords)
    # Sortir berdasarkan panjang kata, ambil 10 teratas
    missing_keywords = sorted(missing_keywords, key=len, reverse=True)[:10]

    # 3. Analisis Quantifiable Metrics (Angka/Persentase menggunakan Regex)
    metrics_found = re.findall(r'\b\d+(?:[\.,]\d+)?\b|\b\d+%', cv_text)
    
    return {
        "score": round(match_score, 1),
        "missing_keywords": missing_keywords,
        "metrics_count": len(metrics_found)
    }

# --- ANTARMUKA STREAMLIT ---
st.title("📄 Open-Source ATS Keyword Matcher")
st.markdown("Sistem analisis CV lokal berbasis statistik (TF-IDF & Cosine Similarity) yang aman, cepat, dan 100% *offline*.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Unggah CV (PDF)")
    uploaded_cv = st.file_uploader("Unggah dokumen CV", type=["pdf"])

with col2:
    st.subheader("2. Job Description")
    job_description = st.text_area("Paste dekskripsi lowongan kerja", height=150)

if st.button("🚀 Analisis CV Sekarang", type="primary", use_container_width=True):
    if uploaded_cv and job_description:
        with st.spinner("Menjalankan pipeline analitik..."):
            
            cv_text = extract_text_from_pdf(uploaded_cv)
            
            if not cv_text.strip():
                st.error("Gagal mengekstrak teks. Pastikan CV bukan gambar hasil scan.")
            else:
                professionalism_issues = check_professionalism(cv_text)
                ats_results = analyze_ats_metrics(cv_text, job_description)
                
                st.success("Pemrosesan Data Selesai!")
                
                # --- DASHBOARD HASIL ---
                st.markdown(f"### 🎯 ATS Match Score: **{ats_results['score']}%**")
                st.progress(ats_results['score'] / 100)
                st.caption("*Skor dihitung menggunakan model jarak vektor Cosine Similarity.*")
                
                st.divider()
                
                col_res1, col_res2 = st.columns(2)
                
                with col_res1:
                    st.subheader("🔑 Rekomendasi Keyword (Gap Analysis)")
                    st.write("Kata kunci dari Job Deskripsi yang **tidak ditemukan** di CV Anda:")
                    if ats_results['missing_keywords']:
                        for kw in ats_results['missing_keywords']:
                            st.warning(f"- {kw}")
                    else:
                        st.success("Semua kata kunci utama tampaknya sudah masuk di CV Anda!")
                        
                    st.subheader("📊 Analisis Data Storytelling")
                    if ats_results['metrics_count'] > 5:
                        st.success(f"Sangat Baik! Ditemukan **{ats_results['metrics_count']} metrik kuantitatif** (angka/persentase). Ini menunjukkan orientasi pada pencapaian nyata.")
                    elif ats_results['metrics_count'] > 0:
                        st.info(f"Cukup. Ditemukan **{ats_results['metrics_count']} metrik kuantitatif**. Disarankan untuk memperbanyak penyajian data pada pengalaman kerja.")
                    else:
                        st.error("Tidak ditemukan angka atau metrik dalam CV. Praktisi Human Capital sangat menghargai pencapaian yang terukur.")

                with col_res2:
                    st.subheader("✍️ Cek Profesionalitas & Format")
                    for issue in professionalism_issues:
                        st.write(issue)
                        
                    st.markdown("---")
                    st.write("**Rekomendasi Format Standar ATS:**")
                    st.write("- Gunakan tata letak vertikal sederhana (satu kolom).")
                    st.write("- Simpan file dengan nama yang jelas (contoh: *NamaLengkap_Posisi_CV.pdf*).")
                    st.write("- Pastikan menggunakan *font* yang mudah dibaca mesin (Arial, Calibri, Helvetica).")

    else:
        st.warning("Mohon lengkapi pengunggahan CV dan input Job Description.")
