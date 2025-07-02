# 使用Debian基础镜像替代Alpine
FROM python:3.11-slim

# 安装必要的系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    vim \
    git \
    bash \
    build-essential \
    libssl-dev \
    libnghttp2-dev \
    zlib1g-dev \
    autoconf \
    automake \
    libtool \
    cmake \
    golang \
    ninja-build \
    perl \
    wget \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app


# 构建和安装 curl-impersonate
RUN git clone https://github.com/lwthiker/curl-impersonate.git && \
    cd curl-impersonate && \
    mkdir -p build && cd build && \
    ../configure && \
    make chrome-build && \
    make chrome-install && \
    ldconfig && \
    cd ../.. && rm -rf curl-impersonate

# Upgrade pip
RUN pip install --upgrade pip

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install  --no-cache -r requirements.lock


# Default command
CMD ["python", "main.py"]
