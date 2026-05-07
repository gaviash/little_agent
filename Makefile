run:
	python app/main.py 

test:
	pytest tests -q

lint:
	ruff check

install:
	pip install -r requirements