UID := $(shell id -u)
GID := $(shell id -g)
IMAGE := warm-tdm
PROJECT_DIR := $(shell pwd)

OS := $(shell uname -s)
ARCH := $(shell uname -m)

ifeq ($(OS),Linux)
    PLATFORM := linux
else ifeq ($(OS)$(ARCH),Darwinx86_64)
    PLATFORM := mac_intel
else ifeq ($(OS)$(ARCH),Darwinarm64)
    PLATFORM := mac_silicon
else
    $(error Unsupported platform: $(OS) $(ARCH))
endif

DOCKER_BUILD := docker build \
    --build-arg HOST_UID=$(shell id -u) \
    --build-arg HOST_GID=$(shell id -g) \
    --build-arg HOST_USER=$(shell id -un) \
    --build-arg HOST_GROUP=$(shell id -gn | grep -E '^[a-zA-Z]' || echo hostgroup)


ifeq ($(PLATFORM),mac_silicon)
    DOCKER_BUILD += --platform linux/amd64
endif

.PHONY: build run clean

build:
	@echo "Detected platform: $(PLATFORM)"
	$(DOCKER_BUILD) -t $(IMAGE) .

run:
	./run.sh $(PROJECT_DIR)

clean:
	docker rmi $(IMAGE)
