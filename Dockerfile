FROM python:3.11-slim

# Install OpenJDK and Apache Ant, which are required by figtreekit --setup-figtree
# to download and compile the FigTree renderer (GPL-2.0-or-later) on demand.
# Use default-jdk-headless so the package name tracks the Debian release's
# current default JDK (e.g. OpenJDK 21 on trixie), avoiding "Unable to locate
# package openjdk-17-jdk-headless" when python:3.11-slim moves to newer Debian.
RUN apt-get update && apt-get install -y --no-install-recommends \
        default-jdk-headless \
        ant \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .

# Uncomment the line below to compile FigTree at image build time.
# This requires network access to download the FigTree source code.
# Alternative: if the figtree_patched.jar is already bundled in the source
# distribution, rendering works without this step — just ensure Java is
# installed at runtime.  Use --build-arg SETUP_FIGTREE=true to control this
# from the docker build command line.
# RUN figtreekit --setup-figtree

WORKDIR /data
ENTRYPOINT ["figtreekit"]
