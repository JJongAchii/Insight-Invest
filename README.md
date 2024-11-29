<img src="/client/src/images/logo.png" width="700">

## Insight-Invest Web Page
> 거시적 경제 시장 국면 파악 및 개인화된 투자전략 백테스팅 도구 <br>
> 개발기간: 2024.09 - 개발중

## 웹사이트 주소
URL: https://insight-invest-ten.vercel.app/

## 화면 소개
1. HOME
   - 주요 경제 실적 발표 및 일정
   - Market Index
   - 글로벌 환율 정보
   - Market Index 차트 정보

2. Regime
   - 장단기금리차, 실업률, CPI 지수 등 주요 경제지표 historical 데이터
  
3. Backtest
   - Simulation
     - 테스트해보고자 하는 여러 전략 생성 가능
     - 생성한 전략의 성과 지표
     - 저장하고 싶은 전략 저장 시 Database 저장
     - 전략 간의 성과비교
   - Strategy List
     - Database에 저장된 전략 리스트
     - 전략 선택시 성과 리포트 생성(Metrics, Performance Charts...)
  
## 시작 가이드
### Requirements
For building and running the application you need:
- Python 3.10.15
- Node.js 20.17.1
- Next.js 14.2.16

### Installation
```
$ git clone https://github.com/JJongAchii/Insight-Invest.git
$ cd Insight-Invest
```

### Backend
```
$ cd server
$ docker build -t insight-invest-server
$ docker run -p 8000:8000 insight-invest-server
```

Docker를 사용하지 않고 직접 패키지를 설치할 경우:
```
$ cd server
$ pip install -r requirements.txt
$ uvicorn app.main:app --reload
```

### Frontend
```
$ cd client
$ npm install
$ npm run dev
```

## Stacks
### Programming Languages
![Python](http://img.shields.io/badge/-Python-3566ab?style=flat&logo=Python&logoColor=white)
![Javascript](http://img.shields.io/badge/-Javascript-f7df1e?style=flat&logo=Javascript&logoColor=white)

### Framework
![Fastapi](http://img.shields.io/badge/-FastAPI-009688?style=flat&logo=FastAPI&logoColor=white)
![Next.js](http://img.shields.io/badge/-Next.js-000000?style=flat&logo=Next.js&logoColor=white)

### Server & Database
![Linux](http://img.shields.io/badge/-Linux-fcc624?style=flat&logo=Linux&logoColor=white)
![PostgreSQL](http://img.shields.io/badge/-PostgreSQL-4169e1?style=flat&logo=PostgreSQL&logoColor=white)
![Docker](http://img.shields.io/badge/-Docker-2496ed?style=flat&logo=Docker&logoColor=white)
![Git](http://img.shields.io/badge/-Git-f05032?style=flat&logo=Git&logoColor=white)

### Build
![Vercel](http://img.shields.io/badge/-Vercel-000000?style=flat&logo=Vercel&logoColor=white)
