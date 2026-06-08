import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json

# 1. 종목명으로 네이버 금융 종목 코드(6자리)를 찾는 함수
def get_stock_code(stock_name):
    try:
        # 네이버 금융 종목 자동완성/검색 내부 API 활용
        search_url = f"https://ac.finance.naver.com/ac?q={stock_name}&q_enc=utf-8&st=1&frm=stock&r_format=json"
        response = requests.get(search_url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            # 검색 결과 데이터 구조 파싱
            items = data.get('items', [])
            if items and items[0]:
                # 첫 번째 매칭된 종목의 코드 추출 (예: [['삼성전자', '005930', ...]])
                stock_code = items[0][0][0][1]
                return stock_code
        return None
    except Exception:
        return None

# 2. 종목 코드를 기반으로 네이버 금융에서 현재가와 시가총액을 크롤링하는 함수
def get_stock_info(stock_code):
    if not stock_code:
        return "N/A", "N/A"
        
    url = f"https://finance.naver.com/item/main.naver?code={stock_code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return "접속 실패", "접속 실패"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # A. 현재가 크롤링 (blind 태그 내부 텍스트 추출)
        today_div = soup.find('div', {'class': 'today'})
        if today_div:
            blind_span = today_div.find('span', {'class': 'blind'})
            current_price = blind_span.text.strip() if blind_span else "N/A"
        else:
            current_price = "N/A"
            
        # B. 시가총액 크롤링 (테이블 소스 파싱)
        # 네이버 금융 '시가총액' 항목은 클래스가 'tab_con1'인 영역 안의 테이블에 위치함
        market_cap_table = soup.find('table', {'summary': '시가총액 정보'})
        if market_cap_table:
            # 시가총액은 보통 첫 번째 tr의 td 안에 위치
            td_elements = market_cap_table.find_all('td')
            if td_elements:
                market_cap = td_elements[0].text.replace('\n', '').replace('\t', '').strip()
            else:
                market_cap = "N/A"
        else:
            market_cap = "N/A"
            
        return current_price, market_cap
        
    except Exception:
        return "오류 발생", "오류 발생"

# 3. Streamlit UI 페이지 레이아웃 설정
st.set_page_config(page_title="네이버 금융 종목 정보 추출기", layout="wide")
st.title("📈 주식 종목별 현재가 & 시가총액 실시간 조회기")
st.caption("엑셀에서 종목명 리스트를 복사하여 아래에 붙여넣으면 네이버 금융 데이터를 기반으로 실시간 수집합니다.")

st.markdown("---")

# 엑셀 데이터 붙여넣기용 텍스트 영역
stock_input = st.text_area(
    "종목명 리스트를 입력하세요 (엑셀에서 열을 통째로 복사해서 붙여넣어도 인지합니다)",
    height=250,
    placeholder="삼성전자\nSK하이닉스\n카카오\nNAVER"
)

# 크롤링 가동 버튼
if st.button("🚀 데이터 추출 시작", type="primary"):
    if not stock_input.strip():
        st.warning("⚠️ 최소 하나 이상의 종목명을 입력해 주세요.")
    else:
        # 입력된 텍스트 정제 및 엔터 단위 분하
        raw_stocks = stock_input.split('\n')
        stock_names = [name.strip() for name in raw_stocks if name.strip()]
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, name in enumerate(stock_names):
            status_text.text(f"⏳ 진행 중 ({idx+1}/{len(stock_names)}): '{name}' 정보 조회 중...")
            
            # 1단계: 종목명 매칭 코드 찾기
            code = get_stock_code(name)
            
            # 2단계: 해당 코드로 현재가/시총 긁어오기
            if code:
                price, cap = get_stock_info(code)
                display_code = code
            else:
                display_code = "찾을 수 없음"
                price, cap = "N/A", "N/A"
                
            results.append({
                "입력 종목명": name,
                "종목 코드": display_code,
                "현재가 (원)": price,
                "시가총액": cap
            })
            
            # 진행바 상태 최신화
            progress_bar.progress((idx + 1) / len(stock_names))
            
            # 네이버 서버 부하 차단 방지를 위한 최소한의 타임 슬립 (0.2초)
            time.sleep(0.2)
            
        status_text.text("✅ 모든 종목의 금융 정보 크롤링이 완료되었습니다!")
        
        # 데이터프레임 시각화
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        
        # 엑셀 호환 CSV 파일 다운로드 연동
        csv_data = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 수집 결과 Excel(CSV) 파일 다운로드",
            data=csv_data,
            file_name="naver_finance_results.csv",
            mime="text/csv"
        )
