# ============================================================
# Build stage: installs/compiles all Python dependencies.
# Dev headers and the compiler toolchain live only here, so
# they (and their CVE surface, e.g. linux-libc-dev kernel
# headers) never reach the runtime image.
# ============================================================
FROM ubuntu:noble AS builder
ENV PYTHONUNBUFFERED=1
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3.12-dev python3-pip build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade --ignore-installed pip setuptools wheel

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements.txt
RUN python3 -m spacy download en_core_web_sm

# Install the corpora package itself
COPY . /tmp/corpora/
RUN python3 -m pip install --no-cache-dir /tmp/corpora


# ============================================================
# Runtime stage
# ============================================================
FROM ubuntu:noble
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Chicago
# Required for start.sh's "pip3 install --user" of plugin
# dependencies (PEP 668: noble's python is externally managed)
ENV PIP_BREAK_SYSTEM_PACKAGES=1
ARG DEBIAN_FRONTEND=noninteractive

# Runtime debian packages, plus the MongoDB repository for
# mongodb-database-tools (client tools only; works against 7.0 servers)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg tzdata \
    && curl -fsSL https://pgp.mongodb.com/server-8.0.asc | \
        gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor \
    && echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] http://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-8.0.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3 git \
        tesseract-ocr tesseract-ocr-eng mongodb-database-tools \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Python packages (site-packages + entry points like daphne/jupyter/pip)
COPY --from=builder /usr/local /usr/local

# Build directory structure and copy files
RUN mkdir /apps
WORKDIR /apps
COPY . corpora/

RUN python3 -m ipykernel install --name='Corpora' --display-name='Corpora'

# Replace noble's default "ubuntu" user so corpora keeps UID 1000
# (matches file ownership from previous jammy-based images)
RUN userdel -r ubuntu \
    && adduser --disabled-password --gecos "" --uid 1000 corpora \
    && mkdir -p /conf/plugin_modules \
    && chown -R corpora:corpora /conf /apps
USER corpora
WORKDIR /apps/corpora
