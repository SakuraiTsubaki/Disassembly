.PHONY: setup check test verify

setup:
	./setup.sh

check:
	@echo "Checking repository structure..."
	@test -d docs
	@test -d toolchains
	@test -d emulators
	@test -d scripts
	@test -d targets
	@test -d schemas
	@test -d tests
	@test -d reports
	@test -d manifests
	@echo "Structure OK"

test: check
	@echo "No target-specific tests configured yet."

verify: check
	@echo "No target-specific verification configured yet."
