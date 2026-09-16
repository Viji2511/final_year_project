# MRep

Use standard 64-bit CPython 3.13, Node.js, for generate-only mode. Docker is only required for optional full execution. Select Python 3.13, not the experimental free-threaded 3.13t interpreter.

## Windows PowerShell setup

Run from the repository root. If your existing `venv` already uses standard Python 3.13, skip the first command:

```powershell
py -3.13 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env # Only if .env does not already exist
```

Fill in both API keys in `.env`. Model names can be overridden there. The default Python 3.13 installation uses text-based equation extraction. Pix2Tex image OCR is excluded because its legacy LaTeX dependency conflicts with the ANTLR runtime used by SymPy. Scanned/image-only equations therefore require a separately configured OCR integration. Unused host ML/evaluation dependencies have been removed; generated experiments install their own dependencies inside Docker.

```powershell
.\venv\Scripts\python.exe pipeline.py path/to/paper.pdf paper_001
.\venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
```

In another terminal:

```powershell
curl.exe -X POST "http://localhost:8000/run?paper_id=paper_001" -F "file=@paper.pdf"
curl.exe "http://localhost:8000/result/paper_001"
```

Paper IDs accept letters, digits, underscores and hyphens, with a letter or digit first (maximum 100 characters).

## Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open the URL printed by Vite. Set `VITE_API_URL` in `frontend/.env` if the backend is not at `http://localhost:8000`.

## Checks

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm.cmd run build
```

## Current limitations

Jobs and results are held in memory: run one API worker; restarting the server loses job status. `complete` means execution finished; inspect `passed` for the validation outcome. Fidelity currently compares extracted numeric targets only. The evaluation modules are empty placeholders; SSIM and symbolic verification are not implemented. Tables may contain multiple baseline models, so target selection still needs review before interpreting fidelity as a scientific reproduction score. PDF extraction is heuristic and can miss vector charts and equations. Full execution runs require working API credentials, model access, and Docker, and may incur API charges.

## Generate-only mode (default)

No Docker installation is needed. Start the API and frontend as above, then upload a PDF.
The pipeline runs stages 1-4 and saves the generated files under `outputs/`.
The result includes `repo_dir`, the exact output folder on the backend machine.
Stage 5 is skipped; `fidelity_score` and `passed` are null, not a success/failure judgment.
API keys are still required for extraction and code generation.

To explicitly configure the mode, add this to your root `.env`:

```dotenv
PIPELINE_MODE=generate_only
```

Restart the backend after changing `.env`. Later, set `PIPELINE_MODE=full` to enable
Docker execution and validation. Full mode requires Docker Desktop with Linux containers.
