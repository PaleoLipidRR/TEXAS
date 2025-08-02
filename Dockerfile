# Dockerfile
FROM squidfunk/mkdocs-material:latest

# install mkdocstrings plugin (and any others you need)
RUN pip install mkdocstrings mkdocstrings-python

WORKDIR /docs

# by default this image has mkdocs in PATH
ENTRYPOINT ["mkdocs"]
