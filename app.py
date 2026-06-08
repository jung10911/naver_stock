import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
import re

# 헤더 설정 (네이버 크롤링 차단 방지)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
}

def get_stock_info(stock_name):
    """
    종목명을 기반으로 네이버 증권에서 종목코드, 현재가, 시가총액을 크롤링합니다.
    """
    cleaned_name = stock_name.strip()
    if not cleaned_name:
        return None
    
    try:
        # 1. 종목명 검색을 통해 종목코드(code) 추출
        search_url = f"https://finance.naver.com/search/searchList.naver?query={cleaned_name}"
        response = requests.get(search_url, headers=HEADERS)
        response.raise_for_status()
        
        # 네이버 금융은 EUC-KR 또는 UTF-8 혼용이 있으므로 인코딩 처리
        html = response.content.decode('euc-kr', errors='replace')
        soup = BeautifulSoup(html, 'html.parser')
        
        # 검색 결과 테이블에서 첫 번째 종목 링크 찾기
        stock_link = soup.select_one("td.tit > a")
        
        if not stock_link:
            return {"종목명": cleaned_name, "종목코드": "N/A", "현재가": "N/A", "시가총액": "N/A", "상태": "종목 미검색"}
        
        # href에서 6자리 종목코드 추출
        href = stock_link.get('href')
        code = re.search(r'code=(\d{6})', href).group(1)
        actual_name = stock_link.text.strip()
        
        # 2. 종목 메인 페이지에서 현재가 및 시가총액 크롤링
        main_url = f"https://finance.naver.com/item/main.naver?code={code}"
        main_response = requests.get(main_url, headers=HEADERS)
        main_soup = BeautifulSoup(main_response.text, 'html.parser')
        
        # 현재가 추출
        today_div = main_soup.select_one("div.today")
        current_price = "N/A"
        if today_div:
            price_blind = today_div.select_one("p.no_today > em > span.blind")
            if price_blind:
                current_price = price_blind.text.strip()
        
        # 시가총액 추출 (포괄적인 상위 테이블에서 '시가총액' 텍스트가 있는 th 찾기)
        market_cap = "N/A"
        aside_table = main_soup.select_one("#aside .tab_con1")
        if aside_table:
            th_list = aside_table.select("trth")
            for th in th_list:
                if "시가총액" in th.text:
                    td = th.find_next_sibling("td")
                    if td:
                        # 불필요한 공백 및 개행 제거
                        market_cap = re.sub(r'\s+', ' ', td.text).strip()
                        break
                        
        return {
            "종목명": actual_name,
            "종목코드": code,
            "현재가": current_price,
            "시가총액": market_cap,
            "상태": "조회 성공"
        }
        
    except Exception as e:
        return {"종목명": cleaned_name, "종목코드": "N/A", "현재가": "N/A", "시가총액": "N/A", "상태": f"오류: {str(e)}"}

# --- Streamlit UI 구성 ---
st.set_page_config(page_title="네이버 금융 크롤러", layout="wide")

st.title("📊 종목 정보 추출기 (현재가 & 시가총액)")
st.caption("엑셀에서 종목명 열을 복사하여 아래에 붙여넣으세요. (줄바꿈 또는 쉼표 구분 지원)")

# 텍스트 입력창 (엑셀 복사-붙여넣기 대응)
input_data = st.text_area(
    "종목명을 입력하세요:", 
    placeholder="예시:\n삼성전자\nSK하이닉스\n현대차",
    height=200
)

if st.button("데이터 추출 시작", type="primary"):
    if not input_data.strip():
        st.warning("종목명을 입력해주세요.")
    else:
        # 입력된 데이터를 줄바꿈 또는 쉼표 기준으로 분리 및 정제
        raw_list = re.split(r'[\n,]', input_data)
        stock_list = [item.strip() for item in raw_list if item.strip()]
        
        if not stock_list:
            st.error("유효한 종목명이 없습니다.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results = []
            
            # 반복 크롤링 수행
            for idx, name in enumerate(stock_list):
                status_text.text(f"조회 중 ({idx+1}/{len(stock_list)}): {name}")
                info = get_stock_info(name)
                if info:
                    results = info
                progress_bar.progress((idx + 1) / len(stock_list))
            
            status_text.text("조회 완료!")
            progress_bar.empty()
            
            # 결과 표 출력
            df = pd.DataFrame(results)
            st.subheader("📋 추출 결과")
            st.dataframe(df, use_container_width=True)
            
            # 엑셀 다운로드 기능 제공
            try:
                # 메모리 상에 엑셀 파일 생성
                from io import BytesIO
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='주가정보')
                processed_data = output.getvalue()
                
                st.download_button(
                    label="📥 엑셀 파일 (.xlsx) 다운로드",
                    data=processed_data,
                    file_name="네이버금융_추출결과.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"엑셀 파일 생성 중 오류가 발생했습니다: {e}")
