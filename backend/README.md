# Cura backend

FastAPI app. From this directory:

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
pytest
```

Mock mode: `ENABLE_LLM=false`.
