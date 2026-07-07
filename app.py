import streamlit as st
import io
import zipfile
import os
from pdf_parser import process_pdf, fix_html_structure, mask_personal_info, parse_data, classify_entries
# 페이지 설정
st.set_page_config(page_title="집회시위 정보 추출기", page_icon="📋")

st.title("📋 집회시위 정보 추출기")
st.write("PDF 파일을 업로드하면 집회 및 시위 정보를 자동으로 추출하여 분류합니다.")

# API 키 설정 (Streamlit Secrets에서 가져오기)
try:
    API_KEY = st.secrets["API_KEY"]
except:
    API_KEY = os.getenv("UPSTAGE_API_KEY")
    # st.error("API 키가 설정되지 않았습니다. 관리자에게 문의하세요.")
    # st.stop()

# 파일 업로드
uploaded_file = st.file_uploader("PDF 파일을 선택하세요", type=['pdf'])

if uploaded_file is not None:
    with st.spinner('PDF 파일을 처리 중입니다...'):
        try:
            # PDF 처리
            response_data = process_pdf(uploaded_file, API_KEY)
            
            # HTML 수집 및 구조 수정
            html_parts = []
            if "elements" in response_data:
                for element in response_data["elements"]:
                    if "content" in element and "html" in element["content"]:
                        html_content = element["content"]["html"]
                        if html_content and html_content.strip():
                            fixed_html = fix_html_structure(html_content)
                            html_parts.append(fixed_html)
            
            # 데이터 파싱
            all_html = ''.join(html_parts)
            formatted_entries = parse_data(all_html)
            
            # 관할별 분류
            mayoung_entries, ganggwang_entries, jungjong_entries = classify_entries(formatted_entries)
            
            st.success(f'처리 완료! 총 {len(formatted_entries)}건의 정보를 추출했습니다.')
            
            # 결과 표시
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader(f"🔵 마영관 ({len(mayoung_entries)}건)")
                for entry in mayoung_entries:
                    st.text(entry)
            
            with col2:
                st.subheader(f"🟢 강광 ({len(ganggwang_entries)}건)")
                for entry in ganggwang_entries:
                    st.text(entry)
            
            with col3:
                st.subheader(f"🟡 중종 ({len(jungjong_entries)}건)")
                for entry in jungjong_entries:
                    st.text(entry)
            
            # 다운로드 파일 생성
            def create_download_files():
                files = {}
                
                # 전체
                files['집회시위정보_전체.txt'] = '\n'.join(formatted_entries)
                
                # 마영관
                mayoung_content = f"=== 마영관 ===\n총 {len(mayoung_entries)}건\n\n" + '\n'.join(mayoung_entries)
                files['집회시위정보_마영관.txt'] = mayoung_content
                
                # 강광
                ganggwang_content = f"=== 강광 ===\n총 {len(ganggwang_entries)}건\n\n" + '\n'.join(ganggwang_entries)
                files['집회시위정보_강광.txt'] = ganggwang_content
                
                # 중종
                jungjong_content = f"=== 중종 ===\n총 {len(jungjong_entries)}건\n\n" + '\n'.join(jungjong_entries)
                files['집회시위정보_중종.txt'] = jungjong_content
                
                return files
            
            files = create_download_files()
            
            # ZIP 파일 생성
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for filename, content in files.items():
                    zip_file.writestr(filename, content.encode('utf-8'))
            
            zip_buffer.seek(0)
            
            # 다운로드 버튼
            st.download_button(
                label="📁 모든 파일 다운로드 (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="집회시위정보.zip",
                mime="application/zip"
            )
            
        except Exception as e:
            st.error(f"처리 중 오류가 발생했습니다: {str(e)}")

# 사용법 설명
with st.expander("사용법"):
    st.write("""
    1. PDF 파일을 업로드하세요
    2. 자동으로 집회/시위 정보를 추출합니다
    3. 관할별로 분류된 결과를 확인하세요
    4. ZIP 파일로 모든 결과를 다운로드할 수 있습니다
    
    **분류 기준:**
    - 마영관: 마포, 서대문, 은평, 서부, 영등포, 구로, 강서, 양천, 관악, 방배, 금천, 동작
    - 강광: 강남, 서초, 수서, 송파, 성동, 강동, 광진
    - 중종: 나머지 지역
    
    **개인정보 보호:**
    - 개인명의 '00' 표기는 자동으로 '◯◯'로 마스킹됩니다
    """)