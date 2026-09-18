.PHONY: ingest query eval eval-baseline eval-drift api app test docker-build clean

ingest:
	python scripts/ingest.py --strategy parent_child

query:
	python scripts/query_cli.py --q "Which supplier provides the component used in Product X?"

eval:
	python scripts/evaluate.py

eval-baseline:
	python scripts/evaluate.py --fail-under 0.6 --save-baseline

eval-drift:
	python scripts/evaluate.py --fail-under 0.6 --compare-baseline

ablate:
	python scripts/ablate.py

test:
	python -m pytest tests/ -q

api:
	uvicorn backend.app.main:app --reload --port 8000

docker-build:
	docker build -t rag-showcase:1.0.0 .

app:
	cd frontend && npm run dev

clean:
	python -c "import shutil,pathlib; [shutil.rmtree(p,ignore_errors=True) for p in [pathlib.Path('data/02_cleaned'),pathlib.Path('data/03_chunked'),pathlib.Path('data/04_vectors')]]; [p.mkdir(parents=True,exist_ok=True) for p in [pathlib.Path('data/02_cleaned'),pathlib.Path('data/03_chunked'),pathlib.Path('data/04_vectors')]]"
