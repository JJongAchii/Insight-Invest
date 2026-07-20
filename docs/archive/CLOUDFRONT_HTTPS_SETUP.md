# 🔒 CloudFront HTTPS 설정 완료 문서

## 📋 설정 개요

**날짜**: 2025-11-18  
**목적**: ECS 백엔드에 HTTPS 추가하여 Vercel(HTTPS)에서 API 호출 가능하게 함  
**방법**: CloudFront를 ECS 앞에 배치하여 무료 HTTPS 인증서 활용

---

## 🎯 문제점

```
이전 구조:
Vercel (HTTPS) → ❌ ECS (HTTP)
└─ 브라우저 Mixed Content 에러로 차단
```

```
해결 후 구조:
Vercel (HTTPS) → ✅ CloudFront (HTTPS) → ECS (HTTP)
└─ 정상 작동!
```

---

## ⚙️ 설정 과정

### Step 1: CloudFront 설정 파일 생성

```bash
cat > /tmp/cf-config.json <<'EOF'
{
  "CallerReference": "insight-invest-$(date +%s)",
  "Comment": "Insight-Invest API HTTPS",
  "Enabled": true,
  "Origins": {
    "Quantity": 1,
    "Items": [{
      "Id": "ECS-ALB",
      "DomainName": "insigh-Publi-FwsGgD0nr2FV-2128202508.ap-northeast-2.elb.amazonaws.com",
      "CustomOriginConfig": {
        "HTTPPort": 80,
        "HTTPSPort": 443,
        "OriginProtocolPolicy": "http-only",
        "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
        "OriginReadTimeout": 60,
        "OriginKeepaliveTimeout": 5
      }
    }]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "ECS-ALB",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {
      "Quantity": 7,
      "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
      "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}
    },
    "ForwardedValues": {
      "QueryString": true,
      "Cookies": {"Forward": "all"},
      "Headers": {"Quantity": 4, "Items": ["Origin", "Access-Control-Request-Headers", "Access-Control-Request-Method", "Authorization"]}
    },
    "MinTTL": 0,
    "DefaultTTL": 0,
    "MaxTTL": 0,
    "Compress": true,
    "TrustedSigners": {"Enabled": false, "Quantity": 0}
  },
  "PriceClass": "PriceClass_All"
}
EOF
```

### Step 2: CloudFront Distribution 생성

```bash
aws cloudfront create-distribution \
  --distribution-config file:///tmp/cf-config.json \
  --output json > /tmp/cf-output.json
```

**결과:**

- Distribution ID: `E1HKH7I9E4T2IZ`
- CloudFront Domain: `dstd3fi5dcl7b.cloudfront.net`
- Status: `InProgress` → `Deployed` (약 2분 소요)

### Step 3: 배포 상태 확인

```bash
aws cloudfront get-distribution \
  --id E1HKH7I9E4T2IZ \
  --query 'Distribution.Status' \
  --output text
```

**결과**: `Deployed` ✅

### Step 4: CloudFront 동작 테스트

```bash
# Health check
curl https://dstd3fi5dcl7b.cloudfront.net/

# API endpoint 테스트
curl https://dstd3fi5dcl7b.cloudfront.net/meta
```

**결과**: 정상 작동 확인 ✅

### Step 5: Vercel 환경변수 설정

**위치**: https://vercel.com/dashboard → Settings → Environment Variables

**입력 내용:**

```
Name:  NEXT_PUBLIC_API_BASE_URL
Value: https://dstd3fi5dcl7b.cloudfront.net

Environments:
✅ Production
✅ Preview
✅ Development
```

### Step 6: Vercel 재배포

**위치**: Deployments → 최신 배포 → Redeploy

---

## 📊 최종 설정 정보

| 항목                           | 값                                                                    |
| ------------------------------ | --------------------------------------------------------------------- |
| **CloudFront Distribution ID** | E1HKH7I9E4T2IZ                                                        |
| **CloudFront Domain**          | dstd3fi5dcl7b.cloudfront.net                                          |
| **CloudFront URL**             | https://dstd3fi5dcl7b.cloudfront.net                                  |
| **Origin (ECS ALB)**           | insigh-Publi-FwsGgD0nr2FV-2128202508.ap-northeast-2.elb.amazonaws.com |
| **Protocol**                   | HTTPS (CloudFront) → HTTP (ECS)                                       |
| **Viewer Protocol Policy**     | Redirect HTTP to HTTPS                                                |
| **Caching**                    | Disabled (TTL: 0)                                                     |
| **Allowed Methods**            | GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE                          |
| **Price Class**                | All Edge Locations                                                    |

---

## ✅ 검증 결과

### API Endpoints 테스트

```bash
# Health check
curl https://dstd3fi5dcl7b.cloudfront.net/
# {"status":"healthy","service":"Insight-Invest API"}

# Meta data
curl https://dstd3fi5dcl7b.cloudfront.net/meta
# [{"meta_id": 1, "ticker": "SPY", ...}]

# Tickers
curl https://dstd3fi5dcl7b.cloudfront.net/meta/tickers
# 정상 작동 확인

# Backtest
curl https://dstd3fi5dcl7b.cloudfront.net/backtest/algorithm
# 정상 작동 확인

# Regime
curl https://dstd3fi5dcl7b.cloudfront.net/regime/info
# 정상 작동 확인
```

**모든 API 엔드포인트 정상 작동** ✅

---

## 🔧 관리 명령어

### CloudFront 상태 확인

```bash
aws cloudfront get-distribution \
  --id E1HKH7I9E4T2IZ \
  --query 'Distribution.Status'
```

### CloudFront 정보 조회

```bash
aws cloudfront get-distribution \
  --id E1HKH7I9E4T2IZ
```

### CloudFront 캐시 무효화 (필요시)

```bash
aws cloudfront create-invalidation \
  --distribution-id E1HKH7I9E4T2IZ \
  --paths "/*"
```

### CloudFront 삭제 (필요시)

```bash
# 1. Distribution 비활성화
aws cloudfront get-distribution-config \
  --id E1HKH7I9E4T2IZ > /tmp/config.json

# config.json에서 "Enabled": true → false로 변경

aws cloudfront update-distribution \
  --id E1HKH7I9E4T2IZ \
  --distribution-config file:///tmp/config.json \
  --if-match ETAG_VALUE

# 2. 비활성화 완료 후 삭제
aws cloudfront delete-distribution \
  --id E1HKH7I9E4T2IZ \
  --if-match ETAG_VALUE
```

---

## 💰 비용

**CloudFront 무료 티어:**

- 데이터 전송: 매월 1TB (무료)
- HTTPS 요청: 매월 1,000만 건 (무료)
- SSL 인증서: 무료 (AWS 제공)

**현재 사용량 예상:**

- API 호출: 매우 적음 (무료 티어 내)
- 데이터 전송: 소량 (무료 티어 내)

**예상 월 비용: $0** ✅

---

## 📝 주요 설정 포인트

### 1. Origin Protocol Policy

```json
"OriginProtocolPolicy": "http-only"
```

- CloudFront → ECS 간 HTTP 사용
- ECS는 HTTP만 지원하므로 필수

### 2. Viewer Protocol Policy

```json
"ViewerProtocolPolicy": "redirect-to-https"
```

- 클라이언트 → CloudFront 간 HTTPS 강제
- HTTP 요청은 자동으로 HTTPS로 리다이렉트

### 3. Caching 비활성화

```json
"MinTTL": 0,
"DefaultTTL": 0,
"MaxTTL": 0
```

- API 응답은 실시간이어야 하므로 캐싱 비활성화
- 항상 최신 데이터 제공

### 4. CORS Headers 전달

```json
"Headers": {
  "Items": [
    "Origin",
    "Access-Control-Request-Headers",
    "Access-Control-Request-Method",
    "Authorization"
  ]
}
```

- CORS preflight 요청 처리를 위해 필수
- Vercel → CloudFront → ECS 간 CORS 정상 작동

### 5. All HTTP Methods 허용

```json
"Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
```

- RESTful API이므로 모든 HTTP 메서드 필요
- OPTIONS는 CORS preflight에 필수

---

## 🚀 배포 흐름

```
코드 변경 → GitHub Push
                ↓
           Vercel 자동 배포
                ↓
    환경변수: NEXT_PUBLIC_API_BASE_URL
                ↓
          CloudFront (HTTPS)
                ↓
            ECS (HTTP)
                ↓
           PostgreSQL
```

---

## 🔍 트러블슈팅

### 문제 1: Mixed Content 에러

**증상**: 브라우저 콘솔에 `blocked:mixed-content` 에러

**원인**: Vercel(HTTPS)에서 ECS(HTTP)로 직접 호출

**해결**: CloudFront 추가 (본 문서의 설정)

### 문제 2: CORS 에러

**증상**: `Access-Control-Allow-Origin` 에러

**확인사항**:

1. ECS `main.py`의 CORS 설정
2. CloudFront에서 CORS 헤더 전달 설정
3. Vercel 도메인이 허용 목록에 있는지 확인

**ECS CORS 설정** (`server/app/main.py`):

```python
origins = [
    "http://localhost:3000",
    "https://insight-invest-ten.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 문제 3: 배포 느림

**증상**: CloudFront 배포가 10분 이상 소요

**원인**: 전 세계 엣지 로케이션에 배포 중

**해결**: 정상적인 현상, 기다리면 됨

### 문제 4: 캐시 문제

**증상**: API 응답이 업데이트되지 않음

**해결**: 캐시 무효화

```bash
aws cloudfront create-invalidation \
  --distribution-id E1HKH7I9E4T2IZ \
  --paths "/*"
```

---

## 📚 참고 자료

- [AWS CloudFront 문서](https://docs.aws.amazon.com/cloudfront/)
- [CloudFront 가격](https://aws.amazon.com/cloudfront/pricing/)
- [CORS 설정 가이드](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/header-caching.html#header-caching-web-cors)

---

## 🎉 완료!

**현재 상태:**

- ✅ CloudFront HTTPS 설정 완료
- ✅ ECS 백엔드 정상 작동
- ✅ Vercel 프론트엔드 연동 준비 완료
- ✅ 무료 SSL 인증서 적용
- ✅ 전 세계 CDN 배포 완료

**다음 단계:**

1. Vercel 재배포
2. 대시보드에서 데이터 확인
3. 모든 페이지 테스트

---

**설정 완료 시간**: 약 5분  
**배포 대기 시간**: 약 2분  
**총 소요 시간**: 약 7분

🎊 성공적으로 HTTPS 설정 완료!
