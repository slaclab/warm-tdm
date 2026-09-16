# Aggregate build targets for firmware releases.
# Keep this list aligned with firmware/releases.yaml.

TARGETS := \
	ColumnFpgaBoard325Fp \
	ColumnFpgaBoard325Int \
	ColumnFpgaBoard325Fp1G \
	ColumnFpgaBoard325Int1G \
	ColumnFpgaBoard325Fp10G \
	ColumnFpgaBoard325Int10G \
	RowFpgaBoard160 \
	RowFpgaBoard325

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
