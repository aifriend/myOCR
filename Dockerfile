# OCRmyPDF
#
#FROM jbarlow83/ocrmypdf:v13.6.2 
#FROM python:3.9-slim
FROM jbarlow83/ocrmypdf:v14.0.0

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
ENV FLASK_APP=api.py
ENV FLASK_DEBUG=0
ENV GS_TAG=gs9550
ENV GS_VERSION=9.55.0
ENV PATH=/usr/local/bin:$PATH

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y \
    build-essential autoconf automake libtool \
    libleptonica-dev \
    zlib1g-dev \
    wget \
    ghostscript \
    apt-utils \
    libqpdf-dev \
    zlib1g \
    liblept5 \
    make \
    gpg \
    gpg-agent \
    gnupg2 \
    ca-certificates \
    dirmngr \
    libsm6 \
    libxext6 \
    libxrender-dev \
    pngquant \
    unpaper   \
    curl \
    git \
    python3-distutils  \
    python3-apt \
    qpdf \
    img2pdf \
    poppler-utils  \
    python-six   

RUN apt-get update && apt-get install -y software-properties-common && add-apt-repository ppa:alex-p/tesseract-ocr5 -y  && \
    apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    libtesseract-dev 
    
RUN \
  curl https://bootstrap.pypa.io/get-pip.py | python3

RUN \
  mkdir jbig2 \
  && curl -L https://github.com/agl/jbig2enc/archive/ea6a40a.tar.gz | \
  tar xz -C jbig2 --strip-components=1 \
  && cd jbig2 \
  && ./autogen.sh && ./configure && make && make install \
  && cd .. \
  && rm -rf jbig2

COPY . /app
WORKDIR /app

RUN pip3 install --no-cache-dir --upgrade pip  -r  /app/requirements.txt \
    setuptools \
    pytesseract \
    gunicorn==20.1.0 


#RUN apt-get purge --auto-remove python3.10 -y && rm -rf /usr/local/bin/pip3.10

#RUN apt-get update -y && apt-get install -y software-properties-common && add-apt-repository ppa:deadsnakes/ppa -y && \
#    apt install python3.9 -y \
#    python3.9-dev \
#    python3.9-distutils \
#    python3.9-lib2to3 \
#    python3.9-gdbm



ENTRYPOINT ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "2", "--worker-connections", "10", "--timeout", "1000", "--preload", "wsgi:app"]
