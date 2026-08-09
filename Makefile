NUITKA = uv run nuitka
PYINSTALLER = uv run pyinstaller
PYTHON = uv run python
APP = src/pydm/app.py
HOST = src/pydm/native_host.py
DIST = dist
VERSION = $(shell $(PYTHON) -c "import sys; sys.path.insert(0, 'src'); import pydm.version as v; print(v.__version__)")
PORTABLE_NAME = PyDM-v$(VERSION)-Windows-x64-Portable
PORTABLE_PYINSTALLER_NAME = PyDM-v$(VERSION)-Windows-x64-Portable-Pyinstaller
INSTALLER_NAME = PyDM-v$(VERSION)-Windows-x64-Installer

.PHONY: all clean pydm pydm-host help nuitka pyinstaller portable portable-pyinstaller installer extension

all: clean pydm pydm-host

nuitka:
	@$(MAKE) pydm-nuitka pydm-host-nuitka

pyinstaller:
	@$(MAKE) portable-pyinstaller

portable: clean pydm-nuitka pydm-host-nuitka
	$(PYTHON) -c "import shutil, sys; from pathlib import Path; sys.path.insert(0, 'src'); import pydm.version as v; dist = Path('$(DIST)'); version = v.__version__; root = dist / f'PyDM-v{version}-Windows-x64-Portable'; root.mkdir(parents=True, exist_ok=True); src_dirs = [dist / 'app.dist', dist / 'native_host.dist']; [shutil.copytree(src, root, dirs_exist_ok=True) for src in src_dirs if src.exists()]; [shutil.copy2(src, root / src.name) for src in [dist / 'com.pydm.host.json'] if src.exists()]; shutil.make_archive(str(dist / f'PyDM-v{version}-Windows-x64-Portable'), 'zip', root)"

portable-pyinstaller: clean pydm-pyinstaller pydm-host-pyinstaller
	$(PYTHON) -c "import shutil, sys; from pathlib import Path; sys.path.insert(0, 'src'); import pydm.version as v; dist = Path('$(DIST)'); version = v.__version__; root = dist / f'PyDM-v{version}-Windows-x64-Portable-Pyinstaller'; root.mkdir(parents=True, exist_ok=True); files = [dist / 'pydm.exe', dist / 'pydm-host.exe', Path('native') / 'com.pydm.host.json']; [shutil.copy2(src, root / src.name) for src in files if src.exists()]; shutil.make_archive(str(dist / f'PyDM-v{version}-Windows-x64-Portable-Pyinstaller'), 'zip', root); shutil.rmtree(root, ignore_errors=True)"

extension:
	$(PYTHON) -c "import json, shutil; from pathlib import Path; m=Path('pydm-extension/manifest.json'); data=json.loads(m.read_text(encoding='utf-8')); v=data.get('version','0.0.0'); out=Path('$(DIST)')/f'pydm-extension-{v}'; out.parent.mkdir(parents=True, exist_ok=True); shutil.make_archive(str(out),'zip','pydm-extension'); print('Created', str(out)+'.zip')"

installer: portable
	$(PYTHON) scripts/build_installer.py

pydm: pydm-pyinstaller

pydm-host: pydm-host-pyinstaller

pydm-nuitka:
	$(NUITKA) --assume-yes-for-downloads --standalone --enable-plugin=pyside6 \
		--windows-console-mode=disable \
		--windows-icon-from-ico=src/pydm/assets/icon.ico \
		--include-data-dir=src/pydm/assets=assets \
		--company-name="TanmoyTheBoT" \
		--product-name="PyDM" \
		--file-version="$(VERSION)" \
		--product-version="$(VERSION)" \
		--copyright="TanmoyTheBoT" \
		--output-dir=$(DIST) --output-filename=pydm $(APP)

pydm-host-nuitka:
	$(NUITKA) --assume-yes-for-downloads --standalone \
		--windows-console-mode=force \
		--company-name="TanmoyTheBoT" \
		--product-name="PyDM Host" \
		--file-version="$(VERSION)" \
		--product-version="$(VERSION)" \
		--copyright="TanmoyTheBoT" \
		--output-dir=$(DIST) --output-filename=pydm-host $(HOST)

pydm-pyinstaller:
	$(PYINSTALLER) --noconfirm --clean --windowed --onefile --name pydm --icon src/pydm/assets/icon.ico --add-data "src/pydm/assets;src/pydm/assets" $(APP)

pydm-host-pyinstaller:
	$(PYINSTALLER) --noconfirm --clean --console --onefile --name pydm-host $(HOST)

clean:
	$(PYTHON) -c "import shutil; from pathlib import Path; [Path(path).unlink() if Path(path).is_file() else shutil.rmtree(Path(path)) if Path(path).is_dir() else None for path in ['dist', 'build', 'pydm.spec', 'pydm-host.spec', 'installer.iss']]"

help:
	@echo "Usage: make [target]"
	@echo "Targets:"
	@echo "  all               - clean and build pydm.exe and pydm-host.exe"
	@echo "  nuitka            - build with Nuitka"
	@echo "  pyinstaller       - build with PyInstaller and create a portable zip"
	@echo "  portable          - build with Nuitka and create a portable folder + zip"
	@echo "  portable-pyinstaller - build with PyInstaller and create a portable zip"
	@echo "  extension         - build the pydm-extension zip"
	@echo "  installer         - build the Inno Setup installer"
	@echo "  pydm              - build pydm.exe"
	@echo "  pydm-host         - build pydm-host.exe"
	@echo "  clean             - remove build artifacts"
