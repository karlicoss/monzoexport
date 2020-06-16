FROM python:3.8
ENV GID=1000 UID=1000
COPY . /app
RUN pip3 install --no-cache -r /app/requirements.txt
CMD ["/app/run"]
# TODO volume??
