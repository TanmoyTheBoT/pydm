PYINSTALLER = uv run pyinstaller
PYTHON = uv run python
APP = src/pydm/app.py
HOST = src/pydm/native_host.py
DIST = dist

.PHONY: all clean pydm pydm-host package help

all: clean pydm pydm-host

pydm:
	$(PYINSTALLER) --noconfirm --clean --windowed --onefile --name pydm --icon src/pydm/assets/icon.ico --add-data "src/pydm/assets;src/pydm/assets" $(APP)

pydm-host:
	$(PYINSTALLER) --noconfirm --clean --console --onefile --name pydm-host $(HOST)

package: all
	$(PYTHON) -c "import zipfile; from pathlib import Path; dist = Path('$(DIST)'); out = dist / 'pydm-distribution.zip'; with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as archive: [archive.write(dist / name, arcname=name) for name in ['pydm.exe', 'pydm-host.exe', 'com.pydm.host.json']]; print(f'Created distribution: {out}')"

clean:
	$(PYTHON) -c "import shutil; from pathlib import Path; [Path(path).unlink() if Path(path).is_file() else shutil.rmtree(Path(path)) if Path(path).is_dir() else None for path in ['dist', 'build', 'pydm.spec', 'pydm-host.spec']]"

help:
	@echo "Usage: make [target]"
	@echo "Targets:"
	@echo "  all       - clean and build pydm.exe and pydm-host.exe"
	@echo "  pydm      - build pydm.exe"
	@echo "  pydm-host - build pydm-host.exe"
	@echo "  package   - build all and zip the dist files"
	@echo "  clean     - remove build artifacts"
