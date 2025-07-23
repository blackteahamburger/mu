help:
	@echo "make run - run the local development version of Mu."
	@echo "make clean - reset the project and remove auto-generated assets."
	@echo "make ruff - run the Ruff linter."
	@echo "make fix - run the Ruff linter and fix any issues it can."
	@echo "make test - run the test suite."
	@echo "make coverage - view a report on test coverage."
	@echo "make format_check - run the Ruff formatter to check for formatting issues."
	@echo "make format - run the Ruff formatter."
	@echo "make check - run all the checkers and tests."
	@echo "make docs - run sphinx to create project documentation."
	@echo "make translate_begin LANG=xx_XX - create/update a mu.po file for translation."
	@echo "make translate_done LANG=xx_XX - compile translation strings in mu.po to mu.mo file."
	@echo "make translate_test LANG=xx_XX - run translate_done and launch Mu in the given LANG."
	@echo "make translate_begin_all - create/update mu.po files for all languages in mu/locale."
	@echo "make translate_done_all - compile all mu.po files to mu.mo files in mu/locale."

run: clean
	python run.py

clean:
	rm -rf build
	rm -rf dist
	rm -rf .coverage
	rm -rf .eggs
	rm -rf *.egg-info
	rm -rf docs/_build
	rm -rf .pytest_cache
	rm -rf lib
	rm -rf .git/avatar/*
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -rf {} +
	rm -f ./mu/locale/messages.pot

ruff:
	ruff check

fix:
	ruff check --fix

test: clean
	py.test

coverage: clean
	py.test --cov-report term-missing --cov=mu tests/

format:
	ruff format

format_check:
	ruff format --check

check: clean ruff format_check coverage

docs: clean
	$(MAKE) -C docs html

translate_begin:
	mkdir -p mu/locale/$(LANG)/LC_MESSAGES;
	pybabel extract -o mu/locale/messages.pot $$(find mu -name '*.py' ! -path 'mu/modes/api/*')
	if [ -f mu/locale/$(LANG)/LC_MESSAGES/mu.po ]; then \
		pybabel update -i mu/locale/messages.pot -o mu/locale/$(LANG)/LC_MESSAGES/mu.po --locale=$(LANG); \
		echo "Updated mu/locale/$(LANG)/LC_MESSAGES/mu.po."; \
	else \
		pybabel init -i mu/locale/messages.pot -o mu/locale/$(LANG)/LC_MESSAGES/mu.po --locale=$(LANG); \
		echo "Created mu/locale/$(LANG)/LC_MESSAGES/mu.po."; \
	fi; \
	echo "Review its translation strings and finalize with 'make translate_done'."

translate_done:
	mkdir -p mu/locale/$(LANG)/LC_MESSAGES
	pybabel compile -i mu/locale/$(LANG)/LC_MESSAGES/mu.po -o mu/locale/$(LANG)/LC_MESSAGES/mu.mo --locale=$(LANG)

translate_test:
	make translate_done LANG=$(LANG)
	python run.py --lang=$(LANG)

translate_begin_all:
	@for lang in $(shell find mu/locale -mindepth 1 -maxdepth 1 -type d | sed 's|mu/locale/||'); do \
		echo "Translating for $$lang..."; \
		make translate_begin LANG=$$lang; \
	done

translate_done_all:
	@for lang in $(shell find mu/locale -mindepth 1 -maxdepth 1 -type d | sed 's|mu/locale/||'); do \
		echo "Compiling translations for $$lang..."; \
		make translate_done LANG=$$lang; \
	done
