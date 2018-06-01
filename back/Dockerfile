FROM ubuntu:latest
RUN apt-get update
RUN apt-get install -y python3-pip
COPY requirements.txt /usr/back/requirements.txt
COPY app.py /usr/back/app.py
RUN pip3 install -r /usr/back/requirements.txt
CMD python3 /usr/back/app.py
