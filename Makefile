run:
	fastapi app/main.py 

container-run :
	docker run --env-file .env -p 8000:8000 prod

test:
	pytest tests -q

lint:
	ruff check

install:
	pip install -r requirements