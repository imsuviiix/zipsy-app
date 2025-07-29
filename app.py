import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import io
import zipfile
import os
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

def process_pdf(pdf_file):
    """PDF 파일을 처리하여 HTML로 변환"""
    url = "https://api.upstage.ai/v1/document-digitization"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    files = {"document": pdf_file}
    data = {
        "model": "document-parse-250508",
        "ocr": "force",
        "coordinates": True,
        "output_formats": '["html"]',
        "base64_encoding": "['table']"
    }
    
    response = requests.post(url, headers=headers, files=files, data=data)
    return response.json()

def fix_html_structure(html_content):
    """HTML 테이블 구조 수정"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    tables = soup.find_all('table')
    for table in tables:
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            for row in rows:
                tds = row.find_all('td')
                current_td_count = len(tds)
                
                # 8개보다 적으면 앞쪽에 빈 셀 추가
                if current_td_count < 8:
                    missing_count = 8 - current_td_count
                    for _ in range(missing_count):
                        new_td = soup.new_tag('td')
                        new_td.string = ''
                        row.insert(0, new_td)
                
                # 8개보다 많으면 초과하는 셀 제거
                elif current_td_count > 8:
                    excess_tds = row.find_all('td')[8:]
                    for td in excess_tds:
                        td.decompose()
    
    return str(soup)

def mask_personal_info(text):
    """개인정보 마스킹: 00을 ◯◯로 변경"""
    # 한글 성씨 + 00 패턴을 찾아서 ◯◯로 변경
    # 예: 김00, 이00, 박00 등
    masked_text = re.sub(r'([가-힣])00', r'\1◯◯', text)
    
    # 개인(성00) 패턴도 처리
    masked_text = re.sub(r'개인\(([가-힣])00\)', r'개인(\1◯◯)', masked_text)
    
    return masked_text

def parse_data(html_content):
    """HTML에서 데이터 추출 및 파싱"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 테이블에서 행 추출
    tables = soup.find_all("table")
    all_rows = []
    
    for table in tables:
        tbody = table.find("tbody")
        if not tbody:
            continue
        
        rows = tbody.find_all("tr")
        for row in rows:
            cols = [col.get_text(strip=True) for col in row.find_all("td")]
            if len(cols) >= 6:
                # 첫 번째 컬럼(번호) 제거하고 실제 데이터만 사용
                if cols[0].isdigit() or cols[0].startswith('-'):
                    cols = cols[1:]  # 번호 컬럼 제거
                all_rows.append(cols)
    
    # 데이터 정리
    cleaned_rows = []
    prev_row = [""] * 8
    
    for row in all_rows:
        current_row = row + [""] * (8 - len(row)) if len(row) < 8 else row[:8]
        
        for i in range(8):
            if current_row[i] and current_row[i].strip():
                prev_row[i] = current_row[i]
            else:
                current_row[i] = prev_row[i]
        
        if len(current_row) >= 8 and current_row[2] and current_row[3]:
            cleaned_rows.append(current_row)
    
    # 포맷 변환
    formatted_entries = []
    for row in cleaned_rows:
        # 컬럼 수에 따라 다른 매핑 적용
        if len(row) == 5:
            # 5개 컬럼: [주최자, 시간장소, 인원, 행사유형, 관할]
            organizer = row[0] if row[0] else "주최자불명"
            time_loc = row[1] if row[1] else "시간장소불명"
            people = row[2] if row[2] else "인원불명"
            event_type = row[3] if row[3] else "행사유형불명"
            region_text = row[4] if row[4] else "관할불명"
            event = organizer  # 주최자를 행사명으로 사용
        elif len(row) == 6:
            # 6개 컬럼: [주최자, 행사명, 시간장소, 인원, 행사유형, 관할]
            organizer = row[0] if row[0] else "주최자불명"
            event = row[1].replace(" ", "") if row[1] else "행사명불명"
            time_loc = row[2] if row[2] else "시간장소불명"
            people = row[3] if row[3] else "인원불명"
            event_type = row[4] if row[4] else "행사유형불명"
            region_text = row[5] if row[5] else "관할불명"
        elif len(row) == 7:
            # 7개 컬럼: [주최자, 행사명, 시간장소, 인원, 행사유형, 관할, 추가정보]
            organizer = row[0] if row[0] else "주최자불명"
            event = row[1].replace(" ", "") if row[1] else "행사명불명"
            time_loc = row[2] if row[2] else "시간장소불명"
            people = row[3] if row[3] else "인원불명"
            event_type = row[4] if row[4] else "행사유형불명"
            region_text = row[5] if row[5] else "관할불명"
        else:
            # 8개 컬럼: [주최자, 행사명, 시간장소, 인원, 행사유형, 관할, 추가정보, 추가정보]
            organizer = row[2] if row[2] else "주최자불명"
            event = row[3].replace(" ", "") if row[3] else "행사명불명"
            time_loc = row[4] if row[4] else "시간장소불명"
            people = row[5] if row[5] else "인원불명"
            event_type = row[6] if row[6] else "행사유형불명"
            region_text = row[7] if row[7] else "관할불명"
        
        # 주최자에만 개인정보 마스킹 적용
        organizer = mask_personal_info(organizer)
        
        # 시간과 장소 분리
        if "~" in time_loc:
            # 다양한 시간 패턴 매칭
            time_patterns = [
                r'(\d{1,2}:\d{2}~\d{1,2}:\d{2})',  # 17:00~22:00
                r'(\d{1,2}:\d{2}∼\d{1,2}:\d{2})',  # 17:00∼22:00
                r'(\d{1,2}:\d{2}~未定)',  # 18:30~未定
                r'(\d{1,2}:\d{2}∼未定)',  # 18:30∼未定
                r'(\d{1,2}:\d{2}~\s*翌\)\d{1,2}:\d{2})',  # 23:00~ 翌)03:00
                r'(\d{1,2}:\d{2}∼\s*翌\)\d{1,2}:\d{2})',  # 23:00∼ 翌)03:00
                r'(\d{1,2}:\d{2}~\d{1,2}:\d{2}~\d{1,2}:\d{2})',  # 복합 시간
                r'(\d{1,2}:\d{2}∼\d{1,2}:\d{2}∼\d{1,2}:\d{2})',  # 복합 시간
                r'(\d{1,2}:\d{2}~\d{1,2}:\d{2}\s+\d{1,2}:\d{2}~\d{1,2}:\d{2})',  # 여러 시간대
                r'(\d{1,2}:\d{2}∼\d{1,2}:\d{2}\s+\d{1,2}:\d{2}∼\d{1,2}:\d{2})',  # 여러 시간대
            ]
            
            time_found = False
            for pattern in time_patterns:
                time_match = re.search(pattern, time_loc)
                if time_match:
                    time = time_match.group(1)
                    location = time_loc.replace(time, "").strip()
                    location = re.sub(r'<[^>]*>', '', location).strip()
                    time_found = True
                    break
            
            if not time_found:
                time = "시간정보없음"
                location = re.sub(r'<[^>]*>', '', time_loc).strip()
        else:
            time = "시간정보없음"
            location = re.sub(r'<[^>]*>', '', time_loc).strip()
        
        # 관할서 추출
        region_match = re.search(r'([가-힣\s]+)\s*<[^>]*>', region_text)
        if region_match:
            region = region_match.group(1).strip().replace(" ", "")
        else:
            region_parts = region_text.split()
            region = region_parts[-1].replace(" ", "") if region_parts else "관할불명"
        
        formatted = f"-{organizer}/{event}/{time}/{location}/{people}/집회/{region}"
        formatted_entries.append(formatted)
    
    return formatted_entries

def classify_entries(entries):
    """관할별로 분류"""
    mayoung_regions = ["마포", "서대문", "은평", "서부", "영등포", "구로", "강서", "양천", "관악", "방배", "금천", "동작"]
    ganggwang_regions = ["강남", "서초", "수서", "송파", "성동", "강동", "광진"]
    
    mayoung_entries = []
    ganggwang_entries = []
    jungjong_entries = []
    
    for entry in entries:
        region = entry.split("/")[-1]
        
        if any(r in region for r in mayoung_regions):
            mayoung_entries.append(entry)
        elif any(r in region for r in ganggwang_regions):
            ganggwang_entries.append(entry)
        else:
            jungjong_entries.append(entry)
    
    return mayoung_entries, ganggwang_entries, jungjong_entries

# 파일 업로드
uploaded_file = st.file_uploader("PDF 파일을 선택하세요", type=['pdf'])

if uploaded_file is not None:
    with st.spinner('PDF 파일을 처리 중입니다...'):
        try:
            # PDF 처리
            response_data = process_pdf(uploaded_file)
            
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