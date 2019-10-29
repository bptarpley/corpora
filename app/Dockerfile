FROM ubuntu:18.04
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y git python3-pip libmysqlclient-dev ghostscript libgs-dev imagemagick tesseract-ocr tesseract-ocr-eng

# Configure ImageMagick
RUN sed -i "s^<policy domain=\"coder\" rights=\"none\" pattern=\"PDF\" />^<policy domain=\"coder\" rights=\"read|write\" pattern=\"PDF\" />^g" /etc/ImageMagick-6/policy.xml

RUN mkdir /apps

WORKDIR /apps
RUN mkdir corpora
COPY . corpora/

RUN pip3 install -r /apps/corpora/requirements.txt
RUN python3 -m nltk.downloader punkt stopwords wordnet averaged_perceptron_tagger

WORKDIR /apps/corpora
RUN python3 setup.py install
