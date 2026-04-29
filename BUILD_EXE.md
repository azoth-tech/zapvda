# Building Standalone EXE (Windows)

## Step 1: Install PyInstaller
```bash
pip install pyinstaller
```

## Step 2: Build the EXE
```bash
pyinstaller vda.spec --clean
```

Or use the command-line method:
```bash
pyinstaller --onefile --windowed --name "ZapOrion_VDA_Analyzer" --hidden-import duckdb --hidden-import polars --hidden-import requests main.py
```

## Step 3: Find the output
The executable will be in the `dist/` folder:
```
dist/ZapOrion_VDA_Analyzer.exe
```

## Step 4: Distribute
Copy the EXE file to any Windows PC. No Python installation needed!
The database will be created in `%USERPROFILE%/.zaporion/vda/` on first run.

## Notes
- First build may take 2-5 minutes
- Final EXE size: ~80-150 MB (includes Python + Qt + DuckDB + Polars)
- For smaller size, use `--onedir` instead of `--onefile`
