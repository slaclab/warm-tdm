# Aggregate build targets for firmware releases.
# Keep this list aligned with firmware/releases.yaml.

TARGETS := \
	ColumnFpgaBoard \
	ColumnFpgaBoard0 \
	ColumnFpgaBoard325Coordinator \
	ColumnFpgaBoard325Coordinator10G \
	ColumnFpgaBoardAwaXe \
	ColumnModule \
	ColumnModule0 \
	RowFpgaBoard \
	RowFpgaBoard0 \
	RowFpgaBoard325 \
	RowModule \
	RowModule0 \
	RowModuleC00

SUBTARGET ?= prom

.PHONY: all list clean $(TARGETS)

all: $(TARGETS)

list:
	@printf '%s\n' $(TARGETS)

$(TARGETS):
	cd $@ && $(MAKE) $(SUBTARGET)

clean:
	@for target in $(TARGETS); do \
		(cd $$target && $(MAKE) clean) || exit $$?; \
	done
