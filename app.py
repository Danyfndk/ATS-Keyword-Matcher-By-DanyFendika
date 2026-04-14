import streamlit as st
import pdfplumber
import language_tool_python
import re
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Open-Source ATS Matcher", layout="wide")

# --- INISIALISASI NLTK & LANGUAGE TOOL ---
@st.cache_resource
def load_nlp_tools():
    # Download stopwords jika belum ada
    nltk.download('stopwords', quiet=True)
    
    # Load language tools menggunakan PUBLIC API agar tidak butuh Java di server
    tool_id = language_tool_python.LanguageToolPublicAPI('id-ID')
    tool_en = language_tool_python.LanguageToolPublicAPI('en-US')
    
    # Siapkan stopwords gabungan (Inggris & Indonesia)
    stop_words_en = set(stopwords.words('english'))
    stop_words_id = set(stopwords.words('indonesian'))
    all_stopwords = list(stop_words_en.union(stop_words_id))
    
    return tool_id, tool_en, all_stopwords

tool_id, tool_en, custom_stopwords = load_nlp_tools()

# --- FUNGSI EKSTRAKSI PDF ---
def extract_text_from_pdf(uploaded_file):
    text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    return text

# --- FUNGSI GRAMMAR CHECK ---
def check_grammar(text):
    matches_id = tool_id.check(text)
    matches_en = tool_en.check(text)
    
    issues = []
    for match in matches_id[:3]:
        issues.append(f"[ID] '{match.context}' -> Saran: {match.replacements[:2]}")
    for match in matches_en[:3]:
        issues.append(f"[EN] '{match.context}' -> Saran: {match.replacements[:2]}")
        
    return issues if issues else ["Tata bahasa dasar sudah rapi."]

# --- FUNGSI ATS SCORING & KEYWORD EXTRACTION (SCIKIT-LEARN) ---
def analyze_ats_metrics(cv_text, jd_text):
    # 1. Menghitung Cosine Similarity (Skor ATS)
    vectorizer = TfidfVectorizer(stop_words=custom_stopwords, ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform([jd_text, cv_text])
    match_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0] * 100
    
    # 2. Ekstraksi Kata Kunci yang Hilang
    # Mengambil kata/frasa penting dari JD yang tidak ada di CV
    jd_vectorizer = TfidfVectorizer(stop_words=custom_stopwords, ngram_range=(1, 2))
    jd_vectorizer.fit([jd_text])
    jd_keywords = set(jd_vectorizer.get_feature_names_out())
    
    cv_vectorizer = TfidfVectorizer(stop_words=custom_stopwords, ngram_range=(1, 2))
    cv_vectorizer.fit([cv_text])
    cv_keywords = set(cv_vectorizer.get_feature_names_out())
    
    missing_keywords = list(jd_keywords - cv_keywords)
    
    # Sortir berdasarkan panjang kata untuk memfilter kata-kata tidak penting, ambil 10 teratas
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
st.markdown("Sistem analisis CV lokal berbasis statistik (TF-IDF & Cosine Similarity) tanpa ketergantungan pada LLM eksternal.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Unggah CV (PDF)")
    uploaded_cv = st.file_uploader("Unggah dokumen CV", type=["pdf"])

with col2:
    st.subheader("2. Job Description")
    job_description = st.text_area("Paste dekskripsi lowongan kerja", height=150)

if st.button("🚀 Analisis CV Sekarang", type="primary", use_container_width=True):
    if uploaded_cv and job_description:
        with st.spinner("Menjalankan pipeline NLP lokal..."):
            
            cv_text = extract_text_from_pdf(uploaded_cv)
            
            if not cv_text.strip():
                st.error("Gagal mengekstrak teks. Pastikan CV bukan gambar hasil scan.")
            else:
                # Menjalankan fungsi NLP
                grammar_issues = check_grammar(cv_text)
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
                        st.error("Tidak ditemukan angka atau metrik dalam CV. Praktisi Human Capital akan lebih menghargai pencapaian yang terukur (contoh: 'memangkas waktu hingga 20%').")

                with col_res2:
                    st.subheader("✍️ Koreksi Ejaan & Profesionalitas")
                    st.write("**Deteksi LanguageTool:**")
                    for issue in grammar_issues:
                        st.write(issue)
                        
                    st.markdown("---")
                    st.write("**Rekomendasi Format Terstruktur:**")
                    st.write("- Pastikan menggunakan *font* standar industri (Arial, Calibri).")
                    st.write("- Hindari penggunaan grafik, tabel, atau kolom rumit agar *parser* membaca teks secara runut.")
                    st.write("- Mulai poin pengalaman kerja dengan kata kerja aktif bahasa Inggris (seperti *Managed, Developed, Analyzed*).")

    else:
        st.warning("Mohon lengkapi pengunggahan CV dan input Job Description.")
