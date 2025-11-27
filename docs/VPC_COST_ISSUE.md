# VPC 비용 이슈 해결

## 🚨 문제: 예상치 못한 VPC 비용 ($9.52/월)

### 증상

```
Amazon Virtual Private Cloud: $9.52/월
```

이 비용은 **NAT Gateway**에서 발생했습니다.

---

## 🔍 원인 분석

### NAT Gateway가 필요한 이유

**Private subnet의 ECS 태스크**가 외부 인터넷에 접근하려면 **NAT Gateway**가 필요합니다.

```yaml
# 문제가 된 설정
network:
  vpc:
    placement: private  # ⚠️ Private subnet
```

### 비용 구조

| 항목                   | 비용           | 월간 비용 (24시간)         |
| ---------------------- | -------------- | -------------------------- |
| NAT Gateway 시간당     | $0.045/시간    | $0.045 × 720h = **$32.40** |
| 데이터 처리            | $0.045/GB      | 사용량에 따라 추가         |
| **실제 청구된 비용**   |                | **$9.52** (부분 사용)      |

---

## ✅ 해결 방법: Public Subnet 사용

### Private vs Public Subnet

| 구분        | Private Subnet                | Public Subnet                      |
| ----------- | ----------------------------- | ---------------------------------- |
| 인터넷 접근 | NAT Gateway 필요 (**유료**)   | Internet Gateway 사용 (**무료**)   |
| 비용        | **$32/월**                    | **$0/월**                          |
| 보안        | 높음 (인바운드 불가)          | 중간 (Security Group으로 보호)     |
| 적합한 용도 | 민감한 데이터베이스, 내부 API | 웹 서버, 배치 작업, 공개 API       |

### Scheduled Jobs는 Public Subnet이 적합합니다!

**이유**:

1. ✅ **인터넷 접근이 필요**: yfinance API, FRED API 등 외부 데이터 소스 호출
2. ✅ **짧은 실행 시간**: 하루 1-2번, 10-15분만 실행
3. ✅ **민감 정보 없음**: 공개 API에서 데이터만 가져옴
4. ✅ **Security Group으로 보호**: 인바운드 접속 차단 가능

---

## 🔧 적용된 변경사항

### Before (문제 상황)

```yaml
# copilot/*/manifest.yml
network:
  vpc:
    placement: private  # ⚠️ NAT Gateway 필요 → $32/월
```

### After (해결)

```yaml
# copilot/*/manifest.yml
network:
  vpc:
    placement: public  # ✅ Internet Gateway 사용 → $0/월
```

**변경된 서비스**:

- ✅ `kr-price-updater`
- ✅ `us-price-updater`
- ✅ `macro-updater`

**변경 안한 서비스**:

- API 서버 (`api`): 이미 public subnet 사용 중

---

## 💰 비용 절감 효과

### Before (변경 전)

```
ECS Fargate (API)        : $14.74
Amazon VPC (NAT Gateway) : $9.52   ← 문제!
Amazon ECS               : $3.28
Amazon RDS               : $1.32
Others                   : $1.01
Tax                      : $2.98
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총 월 비용: $32.85
```

### After (변경 후)

```
ECS Fargate (API)        : $14.74
Amazon VPC (NAT Gateway) : $0.00   ← 제거!
Amazon ECS               : $3.28
Amazon RDS               : $1.32
Others                   : $1.01
Tax                      : $2.98
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총 월 비용: $23.33

절감액: $9.52/월 (-29%)
```

---

## 🚀 배포 방법

### 1. 변경사항 커밋

```bash
git add copilot/
git commit -m "fix: Move scheduled jobs to public subnet to avoid NAT Gateway costs"
git push origin main
```

### 2. Jobs 재배포

```bash
# 각 Job 재배포
copilot job deploy --name kr-price-updater --env dev
copilot job deploy --name us-price-updater --env dev
copilot job deploy --name macro-updater --env dev
```

### 3. NAT Gateway 제거 확인

변경 후 AWS Console에서 확인:

1. **VPC → NAT Gateways** 메뉴로 이동
2. NAT Gateway가 **Idle** 상태인지 확인
3. 며칠 후에도 사용되지 않으면 **삭제**

```bash
# AWS CLI로 NAT Gateway 삭제 (선택사항)
aws ec2 describe-nat-gateways --filter "Name=state,Values=available"

# NAT Gateway ID 확인 후 삭제
aws ec2 delete-nat-gateway --nat-gateway-id nat-xxxxxx
```

---

## 🔒 보안 고려사항

### Q: Public subnet이 안전한가요?

**A: 네, Security Group으로 충분히 보호됩니다.**

#### Security Group 설정

```yaml
# AWS Copilot이 자동으로 생성하는 Security Group
Inbound Rules:
  - None  # 인바운드 트래픽 차단

Outbound Rules:
  - All traffic  # 아웃바운드만 허용 (API 호출 가능)
```

#### 추가 보호 조치

1. **최소 권한 원칙**:
   ```yaml
   # Task Role에 필요한 권한만 부여
   - RDS 접근
   - CloudWatch Logs 쓰기
   - 그 외 권한 없음
   ```

2. **VPC Flow Logs**:
   - 의심스러운 트래픽 모니터링
   - CloudWatch Logs에 기록

3. **네트워크 ACL**:
   - 필요시 추가 방화벽 규칙 적용

---

## 📊 NAT Gateway가 정말 필요한 경우

다음과 같은 경우에는 NAT Gateway를 유지해야 합니다:

### 1. 고도로 민감한 데이터 처리

```yaml
# 예: 금융 데이터, 개인정보 처리
# 절대 public subnet 노출 금지
network:
  vpc:
    placement: private  # NAT Gateway 필요
```

### 2. 컴플라이언스 요구사항

- PCI-DSS, HIPAA 등 규정 준수
- 외부 접근 완전 차단 필요

### 3. 고정 IP가 필요한 경우

```yaml
# NAT Gateway에 Elastic IP 연결
# 외부 API가 화이트리스트 IP 요구하는 경우
```

---

## 🎯 대안: VPC Endpoint (선택사항)

NAT Gateway 대신 **VPC Endpoint**를 사용하면 AWS 서비스 접근 비용을 줄일 수 있습니다.

### S3, DynamoDB 등 AWS 서비스 접근

```yaml
# VPC Endpoint (무료 또는 저렴)
- S3 Gateway Endpoint: 무료
- DynamoDB Gateway Endpoint: 무료
- RDS Interface Endpoint: $7.2/월 (선택사항)
```

하지만 **외부 API (yfinance, FRED)**는 VPC Endpoint로 접근 불가하므로, 우리 케이스에는 **Public Subnet이 최선**입니다.

---

## ✅ 결론

### 적용된 해결책

```
✅ Scheduled Jobs → Public Subnet
✅ Security Group으로 보안 유지
✅ NAT Gateway 제거 → $9.52/월 절감
```

### 최종 비용 구조

```
월 총 비용: ~$23/월
- ECS Fargate: $14.74
- ECS: $3.28
- RDS: $1.32
- Others: $1.01
- Tax: $2.98
```

이제 **예상 비용과 거의 일치**하며, 불필요한 NAT Gateway 비용이 제거되었습니다! 🎉
