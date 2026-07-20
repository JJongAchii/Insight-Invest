# Insight-Invest API — AWS Lambda 컨테이너 이미지 (재구조 2026-07)
# 빌드:  docker build --secret id=gh_token,src=<토큰파일> -t insight-invest-api server/
# 로컬 개발은 이미지 불필요: uvicorn app.main:app --reload

FROM public.ecr.aws/lambda/python:3.12

RUN dnf install -y git && dnf clean all

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# qdata는 private repo — BuildKit secret이라 토큰이 레이어·히스토리에 남지 않는다
RUN --mount=type=secret,id=gh_token \
    pip install --no-cache-dir \
    "qdata[s3] @ git+https://$(cat /run/secrets/gh_token)@github.com/JJongAchii/quant-data.git"

ENV TZ=Asia/Seoul

COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY datastore/ ${LAMBDA_TASK_ROOT}/datastore/
COPY module/ ${LAMBDA_TASK_ROOT}/module/

CMD ["app.main.handler"]
