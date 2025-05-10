FROM python:3.10

ADD . /opt/tg_sync
WORKDIR /opt/tg_sync
RUN pip install -r requirements.txt

ENTRYPOINT ["/opt/tg_sync/tg-sync.py"]

