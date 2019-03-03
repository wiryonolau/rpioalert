.PHONY: help

help: ## This help.
    @awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help

THIS_FILE := $(lastword $(MAKEFILE_LIST))

# Start the container
wheel:
	/usr/bin/env python3 setup.py sdist bdist_wheel

install:
	/usr/bin/env pip3 uninstall -y rpioalert
	/usr/bin/env python3 setup.py clean --all install clean --all
