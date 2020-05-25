FROM python:3.8-slim

LABEL maintainer=francoisancel@gmail.com
RUN apt-get update && apt-get install -y gcc

RUN useradd --create-home --shell /bin/bash appuser
USER appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"
RUN mkdir /home/appuser/src && mkdir /home/appuser/static && mkdir /home/appuser/media && mkdir ~/data

COPY main.py /home/appuser/src
COPY requirements.txt /home/appuser/src
WORKDIR /home/appuser/src

RUN pip install -U -r /home/appuser/src/requirements.txt

CMD ["python", "main.py"]
