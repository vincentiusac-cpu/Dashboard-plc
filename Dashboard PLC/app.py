import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io

# --- KONFIGURASI TAMPILAN PROFESIONAL (FITUR 2) ---
st.set_page_config(page_title="Dashboard PLC Monitoring", layout="wide", page_icon="📊")
st.markdown("""
<style>
    /* Sembunyikan menu Streamlit default & footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Warna latar belakang dan font */
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { color: #1f2937; font-family: 'Segoe UI', sans-serif; }
    
    /* Styling untuk kartu KPI */
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 5px solid #3b82f6;
    }
</style>
""", unsafe_allow_html=True)

# Header dengan Logo (Opsional: ganti URL dengan logo perusahaan Anda)
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image("https://cdn-icons-png.flaticon.com/512/2920/2920349.png", width=80)
with col_title:
    st.title("Dashboard Monitoring Status Pembayaran Bulanan")
    st.caption("Sistem Analisis Penjualan & Piutang - PLC Network")

st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header(" Upload Data Penjualan")
st.sidebar.info("💡 **Tips**: Anda bisa memilih **lebih dari 1 file** (Ctrl+Click) untuk membandingkan data antar bulan!")

uploaded_files = st.sidebar.file_uploader(
    "Upload File Excel (.xlsx)", 
    type=["xlsx"], 
    accept_multiple_files=True
)

reference_date = st.sidebar.date_input(" Tanggal Referensi (Hitung Overdue)", value=datetime.now())

st.sidebar.subheader("️ Alert Overdue")
overdue_threshold = st.sidebar.slider("Threshold (hari)", 0, 120, 30)

# --- FUNGSI PENGOLAHAN DATA ---
@st.cache_data
def load_and_clean_data(file):
    df = None
    header_found = None
    for header_row in range(0, 10):
        try:
            df_temp = pd.read_excel(file, header=header_row)
            df_temp.columns = [str(c).strip() for c in df_temp.columns]
            if 'No. Customer' in df_temp.columns:
                df = df_temp
                header_found = header_row
                break
        except:
            continue
    
    if df is None:
        return None
    
    if 'No.' in df.columns:
        df = df.drop(columns=['No.'])
    
    df = df.dropna(subset=['No. Customer'])
    df['No. Customer'] = pd.to_numeric(df['No. Customer'], errors='coerce')
    df = df.dropna(subset=['No. Customer'])
    
    date_cols = ['Tgl. Invoice', 'Due Invoic', 'Tgl Bayar']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
            
    num_cols = ['Total Invoice', 'Jumlah Bayar', 'PPN Invoice', 'PPH 2%', 'PPH 1.5%', 'DPP Invoice']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    # Tambahkan kolom Bulan dari Tgl. Invoice untuk Tren Bulanan
    if 'Tgl. Invoice' in df.columns:
        df['Bulan'] = df['Tgl. Invoice'].dt.strftime('%B %Y')
    else:
        df['Bulan'] = 'Tidak Diketahui'
        
    return df

def calculate_status(row, ref_date):
    total = row['Total Invoice']
    paid = row['Jumlah Bayar']
    due = row['Due Invoic']
    if pd.isna(due): return 'Tidak Ada Jatuh Tempo'
    elif paid >= total and total > 0: return 'Lunas'
    elif paid > 0 and paid < total: return 'Bayar Sebagian'
    elif due < ref_date: return 'Terlambat (Overdue)'
    else: return 'Belum Jatuh Tempo'

def categorize_segment(nama_customer):
    nama = str(nama_customer).upper()
    if 'KOM -' in nama or 'KOM-' in nama: return 'KOM'
    elif 'GAR -' in nama or 'GAR-' in nama: return 'GAR'
    else: return 'POP'

def hitung_umur_piutang(tgl_jatuh_tempo, tgl_referensi):
    if pd.isna(tgl_jatuh_tempo): return 0
    tgl_jt = pd.to_datetime(tgl_jatuh_tempo, errors='coerce')
    tgl_ref = pd.to_datetime(tgl_referensi, errors='coerce')
    if pd.isna(tgl_jt) or pd.isna(tgl_ref): return 0
    return (tgl_ref - tgl_jt).days

def kategorikan_aging(days):
    if days < 0: return 'Belum Jatuh Tempo'
    elif days == 0: return 'Tepat Waktu (0 hari)'
    elif days <= 30: return '1-30 hari'
    elif days <= 60: return '31-60 hari'
    elif days <= 90: return '61-90 hari'
    elif days <= 120: return '91-120 hari'
    else: return '> 120 hari (Kritis)'

# --- LOGIC UTAMA ---
if uploaded_files:
    all_data = []
    for file in uploaded_files:
        df_temp = load_and_clean_data(file)
        if df_temp is not None:
            all_data.append(df_temp)
        else:
            st.warning(f"⚠️ File {file.name} tidak dapat diproses (format salah).")
            
    if not all_data:
        st.error(" Tidak ada file yang valid untuk diproses.")
        st.stop()
        
    # Gabungkan semua data dari berbagai bulan
    df = pd.concat(all_data, ignore_index=True)
    st.success(f"✅ Berhasil memuat {len(uploaded_files)} file dengan total {len(df)} transaksi.")
    
    ref_dt = pd.to_datetime(reference_date)
    df['Status Pembayaran'] = df.apply(lambda row: calculate_status(row, ref_dt), axis=1)
    df['Segmen'] = df['Nama Customer'].apply(categorize_segment)
    
    df['Aging Days'] = df['Due Invoic'].apply(lambda x: hitung_umur_piutang(x, ref_dt))
    df['Aging Days'] = pd.to_numeric(df['Aging Days'], errors='coerce').fillna(0).astype(int)
    df['Aging Category'] = df['Aging Days'].apply(kategorikan_aging)
    
    # KPI CARDS
    total_tagihan = df['Total Invoice'].sum()
    total_terbayar = df['Jumlah Bayar'].sum()
    collection_rate = (total_terbayar / total_tagihan * 100) if total_tagihan > 0 else 0
    total_piutang = total_tagihan - total_terbayar
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Transaksi", f"{len(df)}")
    c2.metric("Total Tagihan", f"Rp {total_tagihan:,.0f}")
    c3.metric("Total Terbayar", f"Rp {total_terbayar:,.0f}")
    c4.metric("Sisa Piutang", f"Rp {total_piutang:,.0f}")
    c5.metric("Collection Rate", f"{collection_rate:.1f} %")
    
    overdue_mask = (df['Aging Days'] >= overdue_threshold) & (df['Jumlah Bayar'] < df['Total Invoice'])
    overdue_df = df[overdue_mask].copy()
    
    if not overdue_df.empty:
        st.warning(f"⚠️ **ALERT**: {len(overdue_df)} invoice terlambat > {overdue_threshold} hari. Total Piutang: **Rp {overdue_df['Total Invoice'].sum() - overdue_df['Jumlah Bayar'].sum():,.0f}**")
    
    st.markdown("---")
    
    # TABS
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📈 Tren Bulanan", "📊 Status & Segmen", "🏆 Top Customer & Aging",
        " Pajak & Marketing", " Analisis Paket", "📋 Detail Data", "⚠️ Alert Overdue"
    ])
    
    aging_order = ['Belum Jatuh Tempo', 'Tepat Waktu (0 hari)', '1-30 hari', '31-60 hari', '61-90 hari', '91-120 hari', '> 120 hari (Kritis)']
    
    # ===== TAB 1: TREN BULANAN (FITUR 1) =====
    with tab1:
        st.subheader(" Perbandingan Performa Antar Bulan")
        trend_data = df.groupby('Bulan').agg(
            Total_Tagihan=('Total Invoice', 'sum'),
            Total_Terbayar=('Jumlah Bayar', 'sum'),
            Jumlah_Transaksi=('No. Invoice', 'count')
        ).reset_index()
        
        # Urutkan berdasarkan tanggal (ambil dari data asli)
        bulan_urut = df.groupby('Bulan')['Tgl. Invoice'].min().reset_index().sort_values('Tgl. Invoice')['Bulan'].tolist()
        trend_data['Bulan'] = pd.Categorical(trend_data['Bulan'], categories=bulan_urut, ordered=True)
        trend_data = trend_data.sort_values('Bulan')
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            fig_trend_line = px.line(trend_data, x='Bulan', y=['Total_Tagihan', 'Total_Terbayar'], 
                                     markers=True, title="Tren Tagihan vs Terbayar",
                                     color_discrete_map={'Total_Tagihan': '#ef4444', 'Total_Terbayar': '#22c55e'})
            fig_trend_line.update_layout(yaxis_title="Nominal (Rp)")
            st.plotly_chart(fig_trend_line, use_container_width=True)
            
        with col_t2:
            fig_trend_bar = px.bar(trend_data, x='Bulan', y='Jumlah_Transaksi', 
                                   title="Jumlah Transaksi per Bulan", color='Jumlah_Transaksi',
                                   color_continuous_scale='Blues', text_auto='.0f')
            st.plotly_chart(fig_trend_bar, use_container_width=True)
            
        st.markdown("#### 📊 Detail Perbandingan Bulanan")
        trend_data['Collection Rate (%)'] = (trend_data['Total_Terbayar'] / trend_data['Total_Tagihan'] * 100).round(1)
        st.dataframe(trend_data.style.format({'Total_Tagihan': 'Rp {:,.0f}', 'Total_Terbayar': 'Rp {:,.0f}'}), use_container_width=True, hide_index=True)

    # ===== TAB 2: STATUS & SEGMEN =====
    with tab2:
        st.subheader("Distribusi Status Pembayaran")
        col_a, col_b = st.columns([1, 2])
        with col_a:
            status_counts = df['Status Pembayaran'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Jumlah']
            color_map = {'Lunas': '#22c55e', 'Bayar Sebagian': '#f59e0b', 'Terlambat (Overdue)': '#ef4444', 'Belum Jatuh Tempo': '#3b82f6', 'Tidak Ada Jatuh Tempo': '#9ca3af'}
            fig_pie = px.pie(status_counts, values='Jumlah', names='Status', hole=0.4, color='Status', color_discrete_map=color_map)
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_b:
            aging_df = df.groupby('Status Pembayaran')['Total Invoice'].sum().reset_index()
            aging_df.columns = ['Status', 'Nominal']
            fig_bar = px.bar(aging_df, x='Status', y='Nominal', color='Status', color_discrete_map=color_map, text_auto='.2s')
            st.plotly_chart(fig_bar, use_container_width=True)
            
        st.markdown("---")
        st.subheader("📊 Ringkasan Sumber Pendapatan per Segmen")
        segmen_summary = df.groupby('Segmen').agg(Jumlah_Customer=('No. Customer', 'nunique'), Total_Tagihan=('Total Invoice', 'sum'), Total_Terbayar=('Jumlah Bayar', 'sum')).reset_index()
        s1, s2, s3 = st.columns(3)
        for col, segmen, warna, emoji in [(s1, 'POP', '#3b82f6', '🏪'), (s2, 'KOM', '#f97316', ''), (s3, 'GAR', '#22c55e', '🏠')]:
            data_seg = segmen_summary[segmen_summary['Segmen'] == segmen]
            if not data_seg.empty:
                tagihan = data_seg['Total_Tagihan'].values[0]
                terbayar = data_seg['Total_Terbayar'].values[0]
                jml_cust = data_seg['Jumlah_Customer'].values[0]
                pct = (tagihan / total_tagihan * 100) if total_tagihan > 0 else 0
                with col:
                    st.markdown(f"""<div style='background-color:{warna}; padding:20px; border-radius:10px; color:white; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                        <h3 style='color:white; margin:0;'>{emoji} Segmen {segmen}</h3>
                        <p><b>{jml_cust}</b> Customer</p><hr style='border-color:white;'>
                        <h4 style='color:white; margin:0;'>Rp {tagihan:,.0f}</h4>
                        <p><b>Kontribusi: {pct:.1f}%</b></p></div>""", unsafe_allow_html=True)

    # ===== TAB 3: TOP CUSTOMER & AGING =====
    with tab3:
        st.subheader("🏆 Top 10 Customer dengan Tagihan Terbesar")
        top10 = df.groupby(['No. Customer', 'Nama Customer', 'Segmen']).agg(Total_Tagihan=('Total Invoice', 'sum'), Total_Terbayar=('Jumlah Bayar', 'sum')).reset_index()
        top10['Sisa Piutang'] = top10['Total_Tagihan'] - top10['Total_Terbayar']
        top10 = top10.sort_values('Total_Tagihan', ascending=False).head(10)
        fig_top10 = px.bar(top10, x='Total_Tagihan', y='Nama Customer', orientation='h', color='Segmen', color_discrete_map={'POP': '#3b82f6', 'KOM': '#f97316', 'GAR': '#22c55e'}, text_auto='.2s')
        fig_top10.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top10, use_container_width=True)
        
        st.markdown("---")
        st.subheader("⏰ Aging Report (Umur Piutang)")
        piutang_df = df[df['Jumlah Bayar'] < df['Total Invoice']].copy()
        piutang_df['Sisa Piutang'] = piutang_df['Total Invoice'] - piutang_df['Jumlah Bayar']
        aging_summary = piutang_df.groupby('Aging Category').agg(Jumlah_Invoice=('No. Invoice', 'count'), Total_Piutang=('Sisa Piutang', 'sum')).reset_index()
        aging_summary['Aging Category'] = pd.Categorical(aging_summary['Aging Category'], categories=aging_order, ordered=True)
        aging_summary = aging_summary.sort_values('Aging Category')
        
        aging_colors = {'Belum Jatuh Tempo': '#22c55e', 'Tepat Waktu (0 hari)': '#86efac', '1-30 hari': '#fde047', '31-60 hari': '#fdba74', '61-90 hari': '#f97316', '91-120 hari': '#ef4444', '> 120 hari (Kritis)': '#7f1d1d'}
        fig_aging = px.bar(aging_summary, x='Aging Category', y='Total_Piutang', color='Aging Category', color_discrete_map=aging_colors, text_auto='.2s', title="Total Piutang per Kategori Umur")
        st.plotly_chart(fig_aging, use_container_width=True)

    # ===== TAB 4: PAJAK & MARKETING =====
    with tab4:
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.subheader("🧾 Ringkasan Pajak")
            total_ppn = df['PPN Invoice'].sum()
            total_pph2 = df['PPH 2%'].sum()
            total_pph15 = df['PPH 1.5%'].sum()
            p1, p2, p3 = st.columns(3)
            p1.metric("Total PPN", f"Rp {total_ppn:,.0f}")
            p2.metric("Total PPH 2%", f"Rp {total_pph2:,.0f}")
            p3.metric("Total PPH 1.5%", f"Rp {total_pph15:,.0f}")
        with col_p2:
            st.subheader("🎯 Performa Marketing")
            mkt_df = df.groupby('Marketing').agg(Total_Tagihan=('Total Invoice', 'sum'), Total_Bayar=('Jumlah Bayar', 'sum')).reset_index().sort_values('Total_Tagihan', ascending=False)
            fig_mkt = px.bar(mkt_df, x='Marketing', y='Total_Tagihan', color='Marketing', text_auto='.2s')
            st.plotly_chart(fig_mkt, use_container_width=True)

    # ===== TAB 5: PAKET =====
    with tab5:
        st.subheader("📦 Top 10 Paket Terlaris")
        paket_df = df['Nama Paket'].value_counts().head(10).reset_index()
        paket_df.columns = ['Nama Paket', 'Jumlah']
        fig_paket = px.bar(paket_df, x='Jumlah', y='Nama Paket', orientation='h', color='Jumlah', color_continuous_scale='Viridis', text_auto='.0f')
        fig_paket.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_paket, use_container_width=True)

    # ===== TAB 6: DETAIL & EXPORT =====
    with tab6:
        st.subheader("Tabel Detail Data Transaksi")
        filter_status = st.multiselect("Filter Status:", options=df['Status Pembayaran'].unique(), default=df['Status Pembayaran'].unique())
        filter_segmen = st.multiselect("Filter Segmen:", options=['POP', 'KOM', 'GAR'], default=['POP', 'KOM', 'GAR'])
        filter_bulan = st.multiselect("Filter Bulan:", options=sorted(df['Bulan'].unique()), default=sorted(df['Bulan'].unique()))
        
        filtered_df = df[(df['Status Pembayaran'].isin(filter_status)) & (df['Segmen'].isin(filter_segmen)) & (df['Bulan'].isin(filter_bulan))]
        display_cols = ['No. Customer', 'Nama Customer', 'Segmen', 'Bulan', 'Nama Paket', 'Total Invoice', 'Jumlah Bayar', 'Due Invoic', 'Aging Days', 'Marketing', 'Status Pembayaran']
        st.dataframe(filtered_df[display_cols].style.format({'Total Invoice': 'Rp {:,.0f}', 'Jumlah Bayar': 'Rp {:,.0f}'}), use_container_width=True, height=400)
        
        st.markdown("---")
        st.subheader("📥 Download Laporan")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            filtered_df.to_excel(writer, sheet_name='Data Lengkap', index=False)
        st.download_button(label=" Download Data yang Difilter (Excel)", data=buffer.getvalue(), file_name=f"Laporan_PLC_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    # ===== TAB 7: ALERT OVERDUE =====
    with tab7:
        st.subheader(f"⚠️ Monitoring Overdue (>{overdue_threshold} hari)")
        if not overdue_df.empty:
            overdue_df['Sisa Piutang'] = overdue_df['Total Invoice'] - overdue_df['Jumlah Bayar']
            overdue_display = overdue_df[['No. Customer', 'Nama Customer', 'Segmen', 'Bulan', 'Total Invoice', 'Jumlah Bayar', 'Sisa Piutang', 'Due Invoic', 'Aging Days', 'Marketing']].sort_values('Aging Days', ascending=False)
            st.dataframe(overdue_display.style.format({'Total Invoice': 'Rp {:,.0f}', 'Jumlah Bayar': 'Rp {:,.0f}', 'Sisa Piutang': 'Rp {:,.0f}'}), use_container_width=True, height=500)
            
            buffer_ov = io.BytesIO()
            with pd.ExcelWriter(buffer_ov, engine='openpyxl') as writer:
                overdue_display.to_excel(writer, sheet_name='List Overdue', index=False)
            st.download_button(label="📥 Download List Overdue (Excel)", data=buffer_ov.getvalue(), file_name=f"List_Overdue_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.success(f"✅ Tidak ada invoice yang terlambat lebih dari {overdue_threshold} hari.")

else:
    st.info("👈 Silakan upload file Excel di sidebar kiri untuk memulai. (Bisa pilih multiple file sekaligus!)")