import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import time

# 페이지 설정
st.set_page_config(page_title="네이버 금융 대량 종목 조회기", layout="wide")

# [올려주신 핵심 로직 유지] 네이버 금융 전수조사 페이지를 안정적으로 긁어오는 함수
def get_all_market_data(market_code):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'
    }
    
    base_url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={market_code}"
    res = requests.get(base_url, headers=headers)
    soup = BeautifulSoup(res.text, 'lxml')
    
    last_page_tag = soup.find('td', class_='pgRR')
    last_page = int(last_page_tag.a['href'].split('page=')[-1]) if last_page_tag else 1

    all_dfs = []
    
    # URL에 시가총액(market_sum)이 기본 포함되도록 구성
    for page in range(1, last_page + 1):
        url = f"{base_url}&fieldIds=market_sum&page={page}"
        res = requests.get(url, headers=headers)
        
        html_content = res.content.decode('euc-kr', errors='replace')
        df_list = pd.read_html(io.StringIO(html_content))
        df = df_list[1]
        
        df = df.dropna(subset=['종목명'])
        df = df.loc[:, ~df.columns.str.contains('Unnamed')]
        
        all_dfs.append(df)
        time.sleep(0.05) # 서버 부하 방지 micro delay
        
    final_df = pd.concat(all_dfs, ignore_index=True)
    return final_df

# 메인 UI
st.title("📊 엑셀 붙여넣기 기반 현재가 & 시가총액 조회기")
st.markdown("올려주신 네이버 금융 시세 전수조사 로직을 기반으로, **내가 입력한 순서 그대로** 시가총액과 현재가를 정렬하여 제공합니다.")

st.markdown("---")

# 엑셀 대량 붙여넣기 영역
stock_input = st.text_area(
    "조회할 종목명 리스트를 입력하세요 (엑셀에서 열을 통째로 복사해서 붙여넣어도 인지합니다)",
    height=200,
    placeholder="삼성전자\nSK하이닉스\n카카오\nNAVER"
)

if st.button("🚀 금융 정보 수집 시작", type="primary"):
    if not stock_input.strip():
        st.warning("⚠️ 최소 하나 이상의 종목명을 입력해 주세요.")
    else:
        # 입력 데이터 정제
        target_stocks = [name.strip() for name in stock_input.split('\n') if name.strip()]
        
        with st.spinner("⏳ 네이버 금융 실시간 시세 판을 분석 중입니다..."):
            try:
                # 안전하게 코스피(0), 코스닥(1) 데이터를 모두 가져와 병합합니다.
                kospi_df = get_all_market_data("0")
                kosdaq_df = get_all_market_data("1")
                total_market_df = pd.concat([kospi_df, kosdaq_df], ignore_index=True)
                
                # 데이터프레임 내 종목명 양 끝 공백 제거
                total_market_df['종목명'] = total_market_df['종목명'].astype(str).str.strip()
                
                # 사용자가 입력한 종목명만 필터링하는 핵심 로직
                filtered_result = total_market_df[total_market_df['종목명'].isin(target_stocks)].reset_index(drop=True)
                
                # 핵심단어(요청 컬럼)만 추출 및 정리
                target_columns = ['종목명', '현재가', '시가총액']
                available_columns = [col for col in target_columns if col in filtered_result.columns]
                final_df = filtered_result[available_columns].copy()
                
                # [수정] 글자 단위를 제외하고 순수 숫자 형식에 천 단위 콤마(,)만 추가하는 전처리
                if '현재가' in final_df.columns:
                    final_df['현재가'] = pd.to_numeric(final_df['현재가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)
                    final_df['현재가'] = final_df['현재가'].apply(lambda x: f"{x:,}")
                    
                if '시가총액' in final_df.columns:
                    final_df['시가총액'] = pd.to_numeric(final_df['시가총액'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)
                    final_df['시가총액'] = final_df['시가총액'].apply(lambda x: f"{x:,}")
                
                # 사용자가 입력했으나 네이버 상장판에서 매칭되지 않은 종목 보완
                found_stocks = final_df['종목명'].tolist()
                missing_stocks = [s for s in target_stocks if s not in found_stocks]
                
                if missing_stocks:
                    missing_data = [{"종목명": missing, "현재가": "N/A", "시가총액": "N/A"} for missing in missing_stocks]
                    final_df = pd.concat([final_df, pd.DataFrame(missing_data)], ignore_index=True)

                # 사용자가 입력한 순서(target_stocks)대로 최종 결과 정렬
                final_df['종목명'] = pd.Categorical(final_df['종목명'], categories=target_stocks, ordered=True)
                final_df = final_df.sort_values('종목명').reset_index(drop=True)
                final_df['종목명'] = final_df['종목명'].astype(str)

                # 결과 출력
                st.subheader(f"✅ 분석 결과 (총 {len(final_df)}개 종목 완료)")
                st.dataframe(final_df, use_container_width=True)
                
                # 엑셀 다운로드 파일 빌드
                csv = final_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    label="📥 분석 결과 CSV 다운로드",
                    data=csv,
                    file_name="naver_finance_clean.csv",
                    mime='text/csv',
                )
                
            except Exception as e:
                st.error(f"실행 중 예외 오류가 발생했습니다: {e}")
