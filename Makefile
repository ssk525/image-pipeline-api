.PHONY: install test run bench docker-up docker-down

install:
	pip install -r requirements.txt

test:
	pytest -q

run:
	python run_api.py

bench:
	python run_benchmark.py

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
