import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

# 1. 네이버 금융 검색창에서 종목명을 쳐서 코드를 추출하는 함수 (헤더 우회 처리 추가)
def get_stock_code_naver(stock_name):
    try:
        # 네이버 금융 종목 검색 주소
        url = f"https://finance.naver.com/search/searchList.naver?query={stock_name}"
        
        # [핵심] 네이버 차단을 뚫기 위한 정밀 브라우저 헤더 주입
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://finance.naver.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 검색 결과 테이블에서 종목 코드 링크 찾기
        # 네이버 금융 검색창에 이름을 검색했을 때 나오는 첫 번째 항목의 코드를 가져옴
        search_result = soup.find('td', {'class': 'tit'})
        if search_result:
            a_tag = search_result.find('a')
            if a_tag and 'code=' in a_tag['href']:
                # href="...code=005930" 형태에서 6자리 코드만 분리
                return a_tag['href'].split('code=')[-1]
                
        # 만약 바로 상세페이지로 리다이렉트 되거나 예외적인 경우에 대비한 2차 검색 체계
        # (예: 삼성전자 같은 유명 종목은 바로 상세페이지로 튈 수 있음)
        auto_url = f"https://ac.finance.naver.com/ac?q={stock_name}&q_enc=utf-8&st=1&frm=stock&r_format=json"
        auto_resp = requests.get(auto_url, headers=headers, timeout=5)
        if auto_resp.status_code == 200:
            items = auto_resp.json().get('items', [])
            if items and items[0]:
                return items[0][0][0][1]
                
        return None
    except Exception:
        return None

# 2. 종목 코드를 기반으로 현재가와 시가총액을 크롤링하는 함수
def get_stock_info_naver(stock_code):
    url = f"https://finance.naver.com/item/main.naver?code={stock_code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://finance.naver.com/'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return "접속 실패", "접속 실패"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # A. 현재가 크롤링
        today_div = soup.find('div', {'class': 'today'})
        if today_div:
            blind_span = today_div.find('span', {'class': 'blind'})
            current_price = blind_span.text.strip() if blind_span else "N/A"
        else:
            current_price = "N/A"
            
        # B. 시가총액 크롤링
        market_cap_table = soup.find('table', {'summary': '시가총액 정보'})
        if market_cap_table:
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

# 3. Streamlit 대시보드 UI
st.set_page_config(page_title="네이버 금융 대량 조회기", layout="wide")
st.title("📈 주식 종목별 현재가 & 시가총액 실시간 조회기")
st.caption("네이버 금융 웹 크롤링 우회 로직이 반영된 순수 네이버 기반 조회기입니다.")

st.markdown("---")

# 엑셀 붙여넣기용 영역
stock_input = st.text_area(
    "종목명 리스트를 입력하세요 (한 줄에 하나씩)",
    height=250,
    placeholder="삼성전자\nSK하이닉스\n카카오\nNAVER"
)

if st.button("🚀 데이터 추출 시작", type="primary"):
    if not stock_input.strip():
        st.warning("⚠️ 최소 하나 이상의 종목명을 입력해 주세요.")
    else:
        raw_stocks = stock_input.split('\n')
        stock_names = [name.strip() for name in raw_stocks if name.strip()]
        
        results = []
        progress_bar = st.progress(0)
        st_text = st.empty()
        
        for idx, name in enumerate(stock_names):
            st_text.text(f"⏳ 진행 중 ({idx+1}/{len(stock_names)}): '{name}' 검색 및 데이터 추출 중...")
            
            # 순수 네이버 크롤링으로 종목 코드 탐색
            code = get_stock_code_naver(name)
            
            if code:
                price, cap = get_stock_info_naver(code)
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
            
            progress_bar.progress((idx + 1) / len(stock_names))
            
            # 너무 빠르면 네이버가 또 차단하므로 0.3초의 안전 마진을 둡니다.
            time.sleep(0.3)
            
        st_text.text("✅ 모든 종목의 네이버 금융 정보 크롤링이 완료되었습니다!")
        
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 수집 결과 Excel(CSV) 파일 다운로드",
            data=csv_data,
            file_name="naver_finance_pure_results.csv",
            mime="text/csv"
        )
