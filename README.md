# Malathi Dental Clinic - Desktop Management App

Offline dental clinic management and billing desktop app built with Python + PySide6.

## Features
- Dark-themed fullscreen desktop UI
- Dashboard with New Patient, Search Patient, View Bills, Records
- PDF bill generation (`ReportLab`)
- Master visit record maintenance in Word (`python-docx`)
- Offline local data storage only

## Run locally
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   python main.py
   ```

## Data storage
- `data/Patients/<Patient_Name>/BILL_<timestamp>.pdf`
- `data/MASTER_RECORDS.docx`

## Build EXE with PyInstaller
1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Build one-file windowed executable:
   ```bash
   pyinstaller --noconfirm --onefile --windowed --name MalathiDentalClinic main.py
   ```
3. Output executable will be in `dist/`.

## Notes
- App is fully offline and does not require internet or database server.
- First run auto-creates required folders/files under `data/`.
