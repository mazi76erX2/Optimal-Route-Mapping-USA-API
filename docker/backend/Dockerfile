# Stage 1: Build environment
FROM python:3.12.7-slim-bullseye AS builder

# Set timezone
ENV TZ=UTC+2
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install system dependencies
RUN apt-get update && apt-get install -y \
    netcat \
    libpq5 \
    build-essential \
    libpq-dev \
    curl \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    python3-dotenv \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV GDAL_VERSION=3.2.2
ENV GDAL_DATA=/usr/share/gdal

# Install pip and pipenv
RUN pip3 install --progress-bar off --upgrade pip
RUN pip3 install --progress-bar off pipenv

# Install base Python packages
RUN pip3 install numpy==2.1.2
RUN pip3 install wheel setuptools>=67

# Stage 2: Application build
FROM python:3.12.7-slim-bullseye AS app

# Install system dependencies (needed for runtime)
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    netcat \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV GDAL_DATA=/usr/share/gdal

# Copy pip and dependencies from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/pip* /usr/local/bin/
COPY --from=builder /usr/bin/gdal-config /usr/bin/gdal-config

# Set working directory
WORKDIR /app

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install pipenv and dependencies
RUN pip3 install pipenv
RUN pipenv install --deploy --system  # Install dependencies directly into the system Python

# Copy application code
COPY . .

# Stage 3: Final image
FROM app AS final

# Install development dependencies
RUN pipenv install --deploy --system --dev

# Set up entrypoint
COPY docker/backend/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//g' /entrypoint.sh && \
    chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]