# Aggregate build targets for firmware releases.
# Keep this list aligned with firmware/releases.yaml.

TARGETS := \
	ColumnFpgaBoard160 \
	ColumnFpgaBoard160Coord \
	ColumnFpgaBoard325Coord \
	ColumnFpgaBoard325Coord10G \
	ColumnFpgaBoard325AwaXeCoord10G \
	RowFpgaBoard160 \
	RowFpgaBoard160Coord \
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
