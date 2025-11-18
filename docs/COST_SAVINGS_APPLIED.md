# 적용된 비용 절감 사항

## ✅ 변경 완료

### 1. **ALB (Application Load Balancer) 제거** ✨
**절감액: $16/월 (-33%)**

#### 변경 내용
```yaml
# copilot/api/manifest.yml

Before:
type: Load Balanced Web Service  # ALB 사용
http:
  path: "/"

After:
type: Backend Service  # ALB 제거
network:
  vpc:
    placement: public  # 직접 접근
```

#### 영향
- ✅ 월 $16 절감
- ⚠️ Auto-scaling 불가 (count: 1 고정)
- ⚠️ Public IP로 직접 접근 (IP 변경 가능)
- ⚠️ SSL/TLS 수동 관리 필요

#### 접근 방법
```bash
# 배포 후 Public IP 확인
copilot svc show --name api --json | jq -r '.tasks[0].publicIP'

# API 접근
curl http://<PUBLIC_IP>:8000/health
```

---

### 2. **CloudWatch Log Retention 축소** 
**절감액: $1/월**

#### 변경 내용
```yaml
# 모든 manifest 파일

Before:
logging:
  retention: 30  # 30일

After:
logging:
  retention: 7  # 7일
```

#### 영향
- ✅ 로그 저장 비용 감소
- ℹ️ 7일 이상 된 로그는 자동 삭제
- ℹ️ 필요시 로그 export 가능

---

### 3. **Spot Instances 적용 (Scheduled Jobs)** 
**절감액: $0.70/월 (-70%)**

#### 변경 내용
```yaml
# copilot/jobs/*/manifest.yml

추가됨:
platform: linux/x86_64
capacityProviders:
  - FARGATE_SPOT
```

#### 영향
- ✅ 70% 비용 절감
- ⚠️ AWS가 capacity 필요 시 중단 가능 (드물게 발생)
- ✅ 자동 재시도로 중단 시에도 완료

---

## 💰 비용 비교

### Before (원래 설계)
```
ECS Fargate (API)         : $13.00
Application Load Balancer : $16.00  ← 제거
RDS (db.t3.micro)         : $15.00
Scheduled Jobs            : $1.00
CloudWatch Logs (30일)    : $2.50   ← 축소
Data Transfer             : $1.00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총 월 비용: $48.50
```

### After (비용 절감 버전) ✨
```
ECS Fargate (API)         : $13.00
Application Load Balancer : $0.00   ← 제거됨!
RDS (db.t3.micro)         : $15.00
Scheduled Jobs (Spot)     : $0.30   ← Spot으로 70% 절감
CloudWatch Logs (7일)     : $1.50   ← 7일로 축소
Data Transfer             : $1.00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총 월 비용: $30.80

절감액: $17.70/월 (-36.5%) 🎉
```

---

## 🚀 배포 방법

### 옵션 1: GitHub Actions (추천)

```bash
git add .
git commit -m "Apply cost optimization: remove ALB, use Spot instances"
git push origin main
```

### 옵션 2: 수동 배포

```bash
# API 서버 재배포 (ALB 제거)
copilot svc deploy --name api --env dev

# Jobs 재배포 (Spot instances + 짧은 log retention)
copilot job deploy --name us-price-updater --env dev
copilot job deploy --name kr-price-updater --env dev
copilot job deploy --name macro-updater --env dev
```

---

## ⚠️ 주의사항

### 1. API 접근 방식 변경

**기존 (ALB 사용):**
```
https://your-app.region.elb.amazonaws.com/
```

**변경 후 (Direct IP):**
```
http://<ECS_TASK_PUBLIC_IP>:8000/
```

**해결 방법:**

#### A. Route 53 사용 (권장)
```bash
# Public IP 확인
PUBLIC_IP=$(copilot svc show --name api --json | jq -r '.tasks[0].publicIP')

# Route 53에 A 레코드 생성
aws route53 change-resource-record-sets \
  --hosted-zone-id YOUR_ZONE_ID \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.yourdomain.com",
        "Type": "A",
        "TTL": 60,
        "ResourceRecords": [{"Value": "'$PUBLIC_IP'"}]
      }
    }]
  }'
```

#### B. 프론트엔드에서 직접 IP 사용
```javascript
// client/.env.production
NEXT_PUBLIC_API_URL=http://<PUBLIC_IP>:8000
```

#### C. Service Discovery 사용
```yaml
# copilot/api/manifest.yml에 추가
network:
  connect: true  # Service Discovery 활성화
```

### 2. SSL/TLS 설정

ALB 없이 HTTPS를 사용하려면:

**옵션 A: Nginx + Let's Encrypt**
```dockerfile
# Dockerfile 수정
FROM python:3.10-slim

# Nginx 설치
RUN apt-get update && apt-get install -y nginx certbot

# Nginx 설정
COPY nginx.conf /etc/nginx/nginx.conf

# Let's Encrypt 인증서 발급
RUN certbot --nginx -d api.yourdomain.com
```

**옵션 B: Cloudflare 사용 (무료)**
- Cloudflare에 도메인 추가
- DNS에서 API IP 지정
- Cloudflare가 자동으로 SSL 적용

### 3. Spot Instances 중단 대응

Spot instances는 드물게 AWS가 capacity 필요 시 중단될 수 있습니다.

**대응 방법:**
- ✅ 이미 `retries: 2` 설정되어 자동 재시도
- ✅ 다음 예정 시간에 다시 실행
- ✅ CloudWatch 알림 설정으로 실패 감지

**중단 확률:** 매우 낮음 (< 5%)

---

## 📈 추가 절감 가능 항목

현재 적용하지 않았지만, 더 절감하려면:

### 1. RDS 다운그레이드 (-$7/월)
```yaml
db.t3.micro → db.t4g.micro (ARM)
비용: $15 → $8
절감: $7/월
```

**적용 방법:**
```bash
# AWS Console에서 RDS 인스턴스 수정
# 인스턴스 클래스: db.t4g.micro 선택
```

### 2. 무료 DB 사용 (-$15/월)

**Neon (PostgreSQL, 무료):**
- 10 GB 무료
- https://neon.tech

**적용 방법:**
```bash
# Neon 가입 후 connection string 복사
copilot secret init \
  --name DATABASE_URL \
  --values dev=postgresql://user:pass@ep-xxx.neon.tech/main
```

### 3. 모니터링 최소화 (-$1/월)

```bash
# CloudWatch Dashboard 제거
rm copilot/environments/addons/cloudwatch-dashboard.yml

# Alarm 설정 제거
# scripts/setup-monitoring.sh 실행 안함
```

---

## 🎯 비용 시나리오

### Scenario A: 현재 적용 ($30.80/월)
```
✅ ALB 제거
✅ Spot instances
✅ Log retention 7일
⬜ RDS 유지 (db.t3.micro)
⬜ 모니터링 유지
```

### Scenario B: 추가 절감 ($23/월)
```
✅ ALB 제거
✅ Spot instances
✅ Log retention 7일
✅ RDS 다운그레이드 (db.t4g.micro)
⬜ 모니터링 유지
```

### Scenario C: 최대 절감 ($15/월)
```
✅ ALB 제거
✅ Spot instances
✅ Log retention 3일
✅ 무료 DB (Neon)
✅ 모니터링 최소화
```

---

## ✅ 배포 체크리스트

배포 전:
- [ ] 프론트엔드 API URL 변경 준비
- [ ] RDS 연결 확인
- [ ] 백업 확인

배포 후:
- [ ] API Public IP 확인
- [ ] Health check 성공 확인
- [ ] 프론트엔드 연결 테스트
- [ ] Scheduled Jobs 실행 확인
- [ ] 비용 모니터링 시작

---

## 📞 문제 발생 시

### ALB 복구하려면

```yaml
# copilot/api/manifest.yml 복구
type: Load Balanced Web Service

http:
  path: "/"

network:
  vpc:
    placement: private
```

```bash
copilot svc deploy --name api --env dev
```

### Spot instances 비활성화하려면

```yaml
# copilot/jobs/*/manifest.yml에서 제거
# platform: linux/x86_64
# capacityProviders:
#   - FARGATE_SPOT
```

---

## 🎉 결론

**절감액: 월 $17.70 (-36.5%)**

적용된 최적화:
1. ✅ ALB 제거: -$16/월
2. ✅ Log retention 축소: -$1/월
3. ✅ Spot instances: -$0.70/월

트레이드오프:
- Auto-scaling 불가 → 소규모 프로젝트에는 문제 없음
- IP 주소 변경 가능 → Route 53 또는 Service Discovery로 해결
- Spot 중단 가능성 → 자동 재시도로 해결

**추천**: 프로토타입/초기 단계에는 완벽한 선택! 🚀

트래픽이 증가하면 ALB를 다시 추가하는 것을 고려하세요.

