FROM python:3.12-slim
WORKDIR /app
COPY services/api ./services/api
COPY packages/mini_llm ./packages/mini_llm
RUN pip install --no-cache-dir -e ./services/api
# mini LLM (torch) is optional in the container; uncomment to include:
# RUN pip install --no-cache-dir -e ./packages/mini_llm
EXPOSE 8484
CMD ["python", "-m", "uvicorn", "aurelia_api.main:app", "--host", "0.0.0.0", "--port", "8484"]
