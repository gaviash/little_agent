FROM python:3.11.9-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends\
    curl \
    unzip \
    zip \
    procps \
    file \
    coreutils \
    && rm -rf /var/lib/apt/lists/*


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /prod

COPY . .

RUN pip install --no-cache-dir -r requirements.txt 
CMD [ "fastapi","run","app/main.py" ]
EXPOSE 8000