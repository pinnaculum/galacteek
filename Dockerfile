FROM python:3.6.4-stretch

RUN apt-get update
RUN apt-get install -y libgl1-mesa-glx libnss3 libxtst6 libxext6 \
	libasound2 libegl1-mesa libpulse-mainloop-glib0 libpulse0

WORKDIR /usr/local

# Install dependencies.
ADD requirements.txt /usr/local
RUN cd /usr/local && \
    pip3 install -r requirements.txt

# Get ipfs binary
RUN wget http://dist.ipfs.io/go-ipfs/v0.4.15/go-ipfs_v0.4.15_linux-amd64.tar.gz
RUN tar -xvf go-ipfs_v0.4.15_linux-amd64.tar.gz
RUN cp go-ipfs/ipfs /usr/local/bin

# Add actual source code.
COPY . /usr/local/galacteek
RUN cd /usr/local/galacteek && \
	python setup.py build install

ENTRYPOINT ["galacteek"]
