FROM python:3.6.4-stretch

RUN apt-get update
RUN apt-get install -y libgl1-mesa-glx libnss3 libxtst6 libxext6 \
	libasound2 libegl1-mesa libpulse-mainloop-glib0 libpulse0

WORKDIR /usr/local

# Install dependencies.
ADD requirements.txt /usr/local
RUN cd /usr/local && \
    pip3 install -r requirements.txt

# Add actual source code.
COPY . /usr/local/galacteek
RUN cd /usr/local/galacteek && \
	python setup.py install

ENTRYPOINT ["galacteek"]
