FROM python:3.8-slim-buster
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y ca-certificates python3-pip git jupyter-notebook ghostscript libgs-dev imagemagick tesseract-ocr tesseract-ocr-eng mongo-tools

# Update CA Certificates
RUN update-ca-certificates

# Configure ImageMagick
RUN sed -i "s^<policy domain=\"coder\" rights=\"none\" pattern=\"PDF\" />^<policy domain=\"coder\" rights=\"read|write\" pattern=\"PDF\" />^g" /etc/ImageMagick-6/policy.xml

RUN mkdir /apps

WORKDIR /apps
RUN mkdir corpora
COPY . corpora/

RUN pip3 install --no-cache-dir -r /apps/corpora/requirements.txt
RUN pip3 install --no-cache-dir --no-input spacy
RUN pip3 install --no-cache-dir --no-input booknlp
RUN python3 -m nltk.downloader punkt stopwords wordnet averaged_perceptron_tagger
RUN python3 -m spacy download en_core_web_sm

#RUN pip3 uninstall -y bson
#RUN pip3 uninstall -y pymongo
#RUN pip3 install --no-input pymongo

WORKDIR /apps/corpora
RUN python3 setup.py install

RUN ipython kernel install --name='Corpora' --display-name='Corpora'

RUN adduser corpora
RUN chown -R corpora.corpora /apps
USER corpora
WORKDIR /apps/corpora