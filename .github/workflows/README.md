# GitHub Actions CI/CD 설정

이 디렉토리에는 자동 배포를 위한 GitHub Actions 워크플로우가 포함되어 있습니다.

## 🚀 자동 배포 워크플로우

### deploy.yml

- **트리거**: `main` 브랜치에 push 시 자동 실행
- **조건**: `server/` 또는 `copilot/` 디렉토리가 변경된 경우에만
- **동작**: AWS Copilot을 사용하여 API를 dev 환경에 배포

## 📝 설정 방법

### 1. AWS 자격증명을 GitHub Secrets에 추가

GitHub 레포지토리 → Settings → Secrets and variables → Actions

다음 secrets를 추가하세요:

```
AWS_ACCESS_KEY_ID: AKIA...
AWS_SECRET_ACCESS_KEY: ...
```

### 2. IAM 사용자 생성 (아직 없다면)

AWS Console → IAM → Users → Add user

**필요한 권한:**

- AmazonECS_FullAccess
- AmazonVPCFullAccess
- CloudFormationFullAccess
- IAMFullAccess (Copilot이 역할 생성에 필요)
- AmazonEC2ContainerRegistryFullAccess
- AmazonSSMFullAccess

또는 더 제한적인 정책:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:*",
        "ecr:*",
        "cloudformation:*",
        "ec2:*",
        "elasticloadbalancing:*",
        "logs:*",
        "ssm:GetParameter",
        "ssm:GetParameters",
        "iam:PassRole",
        "iam:GetRole",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:PutRolePolicy"
      ],
      "Resource": "*"
    }
  ]
}
```

### 3. 수동 배포 실행

GitHub 레포지토리 → Actions → Deploy to AWS Copilot → Run workflow

## 🔄 워크플로우 동작 방식

1. **코드 체크아웃**: 최신 코드를 가져옴
2. **AWS 인증**: Secrets에 저장된 자격증명으로 인증
3. **Copilot 설치**: 최신 버전의 Copilot CLI 설치
4. **서비스 배포**: `copilot svc deploy` 실행
5. **상태 확인**: 배포 성공 여부 확인
6. **알림**: 성공/실패 알림

## 📊 배포 확인

배포가 완료되면 Actions 탭에서 로그를 확인할 수 있습니다.

성공적인 배포는:

- ✅ 녹색 체크마크
- API URL이 로그에 출력됨

## 🛠️ 트러블슈팅

### 인증 오류

- AWS credentials가 올바르게 설정되었는지 확인
- IAM 사용자에 충분한 권한이 있는지 확인

### 배포 실패

- Copilot 로그 확인: `copilot svc logs`
- CloudFormation 스택 이벤트 확인

### 타임아웃

- 배포에 시간이 오래 걸릴 수 있음 (5-10분)
- GitHub Actions 타임아웃 증가 필요시 workflow에 `timeout-minutes` 추가

## 🔐 보안 고려사항

- ✅ AWS 자격증명은 절대 코드에 포함하지 않음
- ✅ GitHub Secrets에 안전하게 저장
- ✅ 최소 권한 원칙 적용
- ⚠️ 정기적으로 access keys 교체
