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
JOBS ?=

.PHONY: all list report clean $(TARGETS)

all: $(TARGETS)

list:
	@printf '%s\n' $(TARGETS)

# Parallel build of every target with a pass/fail summary + per-target logs,
# where a failure in one target is easy to spot. Delegates to build_release.sh
# (the single source of that summary logic) over this Makefile's TARGETS.
# --force so it runs on a dirty dev tree like `all` does (images get a -dirty
# git stamp); use build_release.sh directly, without --force, for real releases.
# Cap concurrency with e.g. `make report JOBS=4`.
report:
	@./build_release.sh --targets "$(TARGETS)" -t "$(SUBTARGET)" --force $(if $(strip $(JOBS)),-j $(JOBS),)

$(TARGETS):
	cd $@ && $(MAKE) $(SUBTARGET)

clean:
	@for target in $(TARGETS); do \
		(cd $$target && $(MAKE) clean) || exit $$?; \
	done
