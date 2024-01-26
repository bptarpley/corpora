FROM ubuntu:jammy
ENV PYTHONUNBUFFERED 1
ENV TZ=America/Chicago

# Necessary repositories and settings for python 3.11 and tesseract 5
RUN apt-get update
RUN apt-get install -y software-properties-common curl
RUN add-apt-repository -y ppa:deadsnakes/ppa -y
RUN add-apt-repository -y ppa:alex-p/tesseract-ocr5
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone


# Necessary repository for mongodb-database-tools
RUN curl -fsSL https://pgp.mongodb.com/server-7.0.asc | \
   gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg \
   --dearmor

RUN echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] http://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list


# Remove old version of python3
RUN apt-get remove -y --auto-remove python3 python3.10 python3.10-full python3.10-minimal python3.10-dev
RUN apt-get purge -y python3 python3.10 python3.10-minimal python3.10-dev
RUN rm -rf /usr/local/lib/python3.10
RUN rm -f /usr/bin/python3


# Install needed debian packages
RUN apt-get update
RUN apt-get install -y python3.11
RUN apt-get install -y ca-certificates python3-pip git jupyter-notebook ghostscript mongodb-database-tools
RUN apt-get install -y libgs-dev imagemagick tesseract-ocr tesseract-ocr-eng


# Update CA Certificates
RUN update-ca-certificates


# Configure ImageMagick
RUN sed -i "s^<policy domain=\"coder\" rights=\"none\" pattern=\"PDF\" />^<policy domain=\"coder\" rights=\"read|write\" pattern=\"PDF\" />^g" /etc/ImageMagick-6/policy.xml


# Build directory structure and copy files
RUN mkdir /apps
WORKDIR /apps
RUN mkdir corpora
COPY . corpora/

# Install python dependencies
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 10
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --upgrade numpy
RUN pip3 install --no-cache-dir -r /apps/corpora/requirements.txt
RUN pip3 uninstall -y pyzmq
RUN pip3 install pyzmq
RUN python3 -m spacy download en_core_web_sm

WORKDIR /apps/corpora
RUN python3 setup.py install

RUN python3 -m ipykernel install --name='Corpora' --display-name='Corpora'

RUN adduser corpora
RUN mkdir -p /conf/plugin_modules
RUN chown -R corpora.corpora /conf
RUN export PYTHONUSERBASE=/conf/plugin_modules
RUN chown -R corpora.corpora /apps
USER corpora
WORKDIR /apps/corpora
