#!/bin/bash
#
# CloudWatch 모니터링 및 알림 설정 스크립트
# 
# 사용법:
#   ./scripts/setup-monitoring.sh --email your-email@example.com
#
# 이 스크립트는:
# 1. SNS 토픽 생성 (알림용)
# 2. CloudWatch Alarms 생성 (Job 실패 감지)
# 3. 이메일 구독 설정
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
AWS_REGION="ap-northeast-2"
APP_NAME="insight-invest"
ENV_NAME="dev"
EMAIL=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --email)
            EMAIL="$2"
            shift 2
            ;;
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --env)
            ENV_NAME="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 --email <email> [--region <region>] [--env <env>]"
            echo ""
            echo "Options:"
            echo "  --email    Email address for notifications (required)"
            echo "  --region   AWS region (default: ap-northeast-2)"
            echo "  --env      Environment name (default: dev)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate email
if [ -z "$EMAIL" ]; then
    echo -e "${RED}Error: Email address is required${NC}"
    echo "Usage: $0 --email your-email@example.com"
    exit 1
fi

echo -e "${GREEN}Setting up CloudWatch monitoring for Insight-Invest${NC}"
echo "Region: $AWS_REGION"
echo "Environment: $ENV_NAME"
echo "Notification Email: $EMAIL"
echo ""

# 1. Create SNS Topic
echo -e "${YELLOW}Step 1: Creating SNS Topic...${NC}"
TOPIC_NAME="${APP_NAME}-${ENV_NAME}-alerts"
TOPIC_ARN=$(aws sns create-topic \
    --name "$TOPIC_NAME" \
    --region "$AWS_REGION" \
    --output text \
    --query 'TopicArn' 2>/dev/null || echo "")

if [ -z "$TOPIC_ARN" ]; then
    # Topic might already exist, try to get it
    TOPIC_ARN=$(aws sns list-topics \
        --region "$AWS_REGION" \
        --output text \
        --query "Topics[?contains(TopicArn, '$TOPIC_NAME')].TopicArn" | head -1)
fi

echo -e "${GREEN}✓ SNS Topic: $TOPIC_ARN${NC}"

# 2. Subscribe email to SNS topic
echo -e "${YELLOW}Step 2: Subscribing email to SNS topic...${NC}"
SUBSCRIPTION_ARN=$(aws sns subscribe \
    --topic-arn "$TOPIC_ARN" \
    --protocol email \
    --notification-endpoint "$EMAIL" \
    --region "$AWS_REGION" \
    --output text \
    --query 'SubscriptionArn' 2>/dev/null || echo "pending")

echo -e "${GREEN}✓ Email subscription created${NC}"
echo -e "${YELLOW}⚠ Please check your email ($EMAIL) and confirm the subscription!${NC}"
echo ""

# 3. Create CloudWatch Alarms for Scheduled Jobs
echo -e "${YELLOW}Step 3: Creating CloudWatch Alarms...${NC}"

JOBS=("us-price-updater" "kr-price-updater" "macro-updater")

for JOB in "${JOBS[@]}"; do
    ALARM_NAME="${APP_NAME}-${ENV_NAME}-${JOB}-failed"
    LOG_GROUP="/copilot/${APP_NAME}-${ENV_NAME}-${JOB}"
    
    echo "Creating alarm for: $JOB"
    
    # Create metric filter for job failures
    aws logs put-metric-filter \
        --log-group-name "$LOG_GROUP" \
        --filter-name "${JOB}-failures" \
        --filter-pattern "[time, level = ERROR*, ...]" \
        --metric-transformations \
            metricName="${JOB}-failures",\
metricNamespace="InsightInvest/Jobs",\
metricValue=1,\
defaultValue=0 \
        --region "$AWS_REGION" 2>/dev/null || true
    
    # Create alarm
    aws cloudwatch put-metric-alarm \
        --alarm-name "$ALARM_NAME" \
        --alarm-description "Alert when ${JOB} fails" \
        --metric-name "${JOB}-failures" \
        --namespace "InsightInvest/Jobs" \
        --statistic Sum \
        --period 300 \
        --evaluation-periods 1 \
        --threshold 1 \
        --comparison-operator GreaterThanOrEqualToThreshold \
        --alarm-actions "$TOPIC_ARN" \
        --treat-missing-data notBreaching \
        --region "$AWS_REGION" 2>/dev/null || true
    
    echo -e "${GREEN}✓ Alarm created: $ALARM_NAME${NC}"
done

echo ""

# 4. Create alarm for API server errors
echo -e "${YELLOW}Step 4: Creating API Server alarm...${NC}"
API_LOG_GROUP="/copilot/${APP_NAME}-${ENV_NAME}-api"
API_ALARM_NAME="${APP_NAME}-${ENV_NAME}-api-errors"

aws logs put-metric-filter \
    --log-group-name "$API_LOG_GROUP" \
    --filter-name "api-5xx-errors" \
    --filter-pattern "[..., status_code = 5*, ...]" \
    --metric-transformations \
        metricName="api-5xx-errors",\
metricNamespace="InsightInvest/API",\
metricValue=1,\
defaultValue=0 \
    --region "$AWS_REGION" 2>/dev/null || true

aws cloudwatch put-metric-alarm \
    --alarm-name "$API_ALARM_NAME" \
    --alarm-description "Alert when API returns 5xx errors" \
    --metric-name "api-5xx-errors" \
    --namespace "InsightInvest/API" \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --alarm-actions "$TOPIC_ARN" \
    --treat-missing-data notBreaching \
    --region "$AWS_REGION" 2>/dev/null || true

echo -e "${GREEN}✓ API Server alarm created${NC}"
echo ""

# Summary
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Created Resources:"
echo "  - SNS Topic: $TOPIC_ARN"
echo "  - Email Subscription: $EMAIL (check your email to confirm!)"
echo "  - CloudWatch Alarms:"
echo "    • ${APP_NAME}-${ENV_NAME}-us-price-updater-failed"
echo "    • ${APP_NAME}-${ENV_NAME}-kr-price-updater-failed"
echo "    • ${APP_NAME}-${ENV_NAME}-macro-updater-failed"
echo "    • ${APP_NAME}-${ENV_NAME}-api-errors"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Confirm email subscription (check your inbox)"
echo "  2. View alarms: aws cloudwatch describe-alarms --region $AWS_REGION"
echo "  3. Test notification: aws sns publish --topic-arn $TOPIC_ARN --message 'Test' --region $AWS_REGION"
echo ""
echo -e "${GREEN}You will now receive email notifications when jobs fail!${NC}"

