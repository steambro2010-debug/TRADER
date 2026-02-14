import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

CLINIC_NAME = "Malathi Dental Clinic"
DOCTOR_NAME = "Dr. Malathi Thandapani, BDS"
TREATMENTS = [
    "Consultation",
    "Scaling",
    "Tooth Extraction",
    "Root Canal Treatment",
    "Dental Filling",
    "Crown Fixing",
    "Teeth Whitening",
    "Braces Consultation",
    "Implant Consultation",
    "Pediatric Dental Checkup",
]
PAYMENT_METHODS = ["Cash", "GPay", "PhonePe", "Card"]


class FileManager:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.data_dir = self.base_dir / "data"
        self.patients_dir = self.data_dir / "Patients"
        self.records_file = self.data_dir / "MASTER_RECORDS.docx"
        self._ensure_structure()

    def _ensure_structure(self) -> None:
        self.patients_dir.mkdir(parents=True, exist_ok=True)
        if not self.records_file.exists():
            doc = Document()
            doc.add_heading(f"{CLINIC_NAME} - Master Records", level=1)
            doc.add_paragraph(f"Doctor: {DOCTOR_NAME}")
            doc.add_paragraph("\n")
            doc.save(self.records_file)

    @staticmethod
    def clean_patient_name(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9 _-]", "", name).strip()
        cleaned = re.sub(r"\s+", "_", cleaned)
        return cleaned or "Unknown_Patient"

    def patient_dir(self, patient_name: str) -> Path:
        folder_name = self.clean_patient_name(patient_name)
        path = self.patients_dir / folder_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def generate_bill_pdf(
        self,
        patient_name: str,
        visit_date: str,
        treatment: str,
        amount: str,
        payment_method: str,
    ) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        patient_folder = self.patient_dir(patient_name)
        bill_path = patient_folder / f"BILL_{timestamp}.pdf"

        c = canvas.Canvas(str(bill_path), pagesize=A4)
        width, height = A4

        c.setFont("Helvetica-Bold", 22)
        c.drawString(20 * mm, height - 25 * mm, CLINIC_NAME)

        c.setFont("Helvetica", 12)
        c.drawString(20 * mm, height - 33 * mm, DOCTOR_NAME)

        c.setLineWidth(0.8)
        c.line(20 * mm, height - 37 * mm, width - 20 * mm, height - 37 * mm)

        y = height - 55 * mm
        c.setFont("Helvetica", 12)
        fields = [
            ("Patient Name", patient_name),
            ("Date", visit_date),
            ("Treatment", treatment),
            ("Amount", f"₹ {amount}"),
            ("Payment Mode", payment_method),
        ]

        for label, value in fields:
            c.drawString(25 * mm, y, f"{label}:")
            c.setFont("Helvetica-Bold", 12)
            c.drawString(65 * mm, y, str(value))
            c.setFont("Helvetica", 12)
            y -= 12 * mm

        c.setLineWidth(0.4)
        c.line(20 * mm, 45 * mm, width - 20 * mm, 45 * mm)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(20 * mm, 35 * mm, "Thank you for visiting Malathi Dental Clinic.")

        c.showPage()
        c.save()
        return bill_path

    def append_master_record(
        self,
        patient_name: str,
        visit_date: str,
        treatment: str,
        amount: str,
        payment_method: str,
        bill_path: Path,
    ) -> None:
        if not self.records_file.exists():
            self._ensure_structure()

        doc = Document(self.records_file)
        doc.add_paragraph("=" * 60)
        doc.add_paragraph(f"Patient Name: {patient_name}")
        doc.add_paragraph(f"Date: {visit_date}")
        doc.add_paragraph(f"Treatment: {treatment}")
        doc.add_paragraph(f"Amount: ₹ {amount}")
        doc.add_paragraph(f"Payment Method: {payment_method}")
        doc.add_paragraph(f"Bill File: {bill_path}")
        doc.add_paragraph("")
        doc.save(self.records_file)

    def list_all_bills(self) -> list[Path]:
        return sorted(self.patients_dir.glob("**/*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)

    def search_patient_bills(self, query: str) -> list[Path]:
        query = query.lower().strip()
        if len(query) < 2:
            return []

        matches = []
        for patient_folder in self.patients_dir.iterdir():
            if patient_folder.is_dir() and query in patient_folder.name.lower():
                matches.extend(patient_folder.glob("*.pdf"))
        return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)


def open_path(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception as exc:
        raise RuntimeError(f"Unable to open: {path}\n{exc}") from exc


class AppCard(QFrame):
    """Reusable elevated panel to group related UI sections."""

    def __init__(self, title: str = "", subtitle: str = "") -> None:
        super().__init__()
        self.setObjectName("card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 22, 24, 22)
        self.layout.setSpacing(14)

        if title:
            title_label = QLabel(title)
            title_label.setObjectName("cardTitle")
            self.layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("cardSubtitle")
            subtitle_label.setWordWrap(True)
            self.layout.addWidget(subtitle_label)


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str, action_text: str = "Back", action=None) -> None:
        super().__init__()
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        subtitle_label.setWordWrap(True)

        text_col.addWidget(title_label)
        text_col.addWidget(subtitle_label)

        root.addLayout(text_col)
        root.addStretch(1)

        if action is not None:
            action_btn = QPushButton(action_text)
            action_btn.setObjectName("secondaryButton")
            action_btn.clicked.connect(action)
            root.addWidget(action_btn)


class DashboardPage(QWidget):
    def __init__(self, on_new, on_search, on_bills, on_records):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 30, 34, 30)
        root.setSpacing(20)

        banner = AppCard(CLINIC_NAME, DOCTOR_NAME)
        banner.layout.setSpacing(10)
        welcome = QLabel("Clinic Dashboard")
        welcome.setObjectName("heroTitle")
        message = QLabel("Select an action to manage patients, billing, and records.")
        message.setObjectName("heroSubtitle")
        banner.layout.addWidget(welcome)
        banner.layout.addWidget(message)
        root.addWidget(banner)

        actions_card = AppCard("Quick Actions", "Core workflows for day-to-day clinic operations")
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        actions = [
            ("New Patient", "Register a visit and create bill", True, on_new),
            ("Search Patient", "Find patient bills quickly", False, on_search),
            ("View Bills", "Browse all generated bills", False, on_bills),
            ("Records", "Open master records and folders", False, on_records),
        ]

        for idx, (label, hint, primary, callback) in enumerate(actions):
            btn = QPushButton(f"{label}\n{hint}")
            btn.setObjectName("primaryAction" if primary else "dashboardAction")
            btn.setMinimumHeight(95)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(callback)
            row, col = divmod(idx, 2)
            grid.addWidget(btn, row, col)

        actions_card.layout.addLayout(grid)
        root.addWidget(actions_card)
        root.addStretch(1)


class NewPatientPage(QWidget):
    def __init__(self, fm: FileManager, on_back):
        super().__init__()
        self.fm = fm
        self.on_back = on_back

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 30, 34, 30)
        root.setSpacing(20)

        root.addWidget(
            PageHeader(
                "New Patient",
                "Enter patient visit details and generate a printable bill.",
                action=on_back,
            )
        )

        form_card = AppCard("Patient Visit Form", "All fields are required for bill generation")
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Patient full name")

        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setDisplayFormat("dd-MM-yyyy")
        self.date_input.setCalendarPopup(True)

        self.treatment_input = QComboBox()
        self.treatment_input.addItems(TREATMENTS)

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("e.g. 1500")

        self.payment_input = QComboBox()
        self.payment_input.addItems(PAYMENT_METHODS)

        form.addRow("Patient Name", self.name_input)
        form.addRow("Date", self.date_input)
        form.addRow("Treatment", self.treatment_input)
        form.addRow("Amount (₹)", self.amount_input)
        form.addRow("Payment Method", self.payment_input)

        form_card.layout.addLayout(form)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        back_btn = QPushButton("Cancel")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.on_back)

        save_btn = QPushButton("Save & Generate Bill")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self.save_patient)

        action_row.addWidget(back_btn)
        action_row.addWidget(save_btn)
        form_card.layout.addLayout(action_row)

        root.addWidget(form_card)
        root.addStretch(1)

    def save_patient(self) -> None:
        name = self.name_input.text().strip()
        amount = self.amount_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Validation", "Patient name is required.")
            return

        if not amount.isdigit():
            QMessageBox.warning(self, "Validation", "Amount must be a valid number.")
            return

        visit_date = self.date_input.date().toString("dd-MM-yyyy")
        treatment = self.treatment_input.currentText()
        payment_method = self.payment_input.currentText()

        try:
            bill_path = self.fm.generate_bill_pdf(name, visit_date, treatment, amount, payment_method)
            self.fm.append_master_record(name, visit_date, treatment, amount, payment_method, bill_path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save patient details.\n{exc}")
            return

        QMessageBox.information(
            self,
            "Saved",
            f"Patient saved successfully.\nBill created at:\n{bill_path}",
        )
        self.name_input.clear()
        self.amount_input.clear()


class BillsListPage(QWidget):
    def __init__(self, fm: FileManager, title: str, subtitle: str, on_back, search_mode: bool = False):
        super().__init__()
        self.fm = fm
        self.search_mode = search_mode

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 30, 34, 30)
        root.setSpacing(20)

        root.addWidget(PageHeader(title, subtitle, action=on_back))

        list_card = AppCard("Bills", "Double-click any entry to open the PDF bill")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by patient name (minimum 2 characters)")
        self.search_input.textChanged.connect(self.refresh_list)
        if self.search_mode:
            list_card.layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.open_selected_bill)
        list_card.layout.addWidget(self.list_widget)

        root.addWidget(list_card)
        root.addStretch(1)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_list()

    def refresh_list(self) -> None:
        self.list_widget.clear()
        try:
            if self.search_mode:
                query = self.search_input.text()
                bills = self.fm.search_patient_bills(query)
                if len(query.strip()) < 2:
                    self.list_widget.addItem("Type at least 2 characters to search.")
                    return
            else:
                bills = self.fm.list_all_bills()

            if not bills:
                self.list_widget.addItem("No bills found.")
                return

            for bill in bills:
                item = QListWidgetItem(f"{bill.parent.name}  |  {bill.name}")
                item.setData(Qt.UserRole, str(bill))
                self.list_widget.addItem(item)
        except Exception as exc:
            self.list_widget.addItem(f"Unable to load bills: {exc}")

    def open_selected_bill(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.UserRole)
        if not path_str:
            return

        bill_path = Path(path_str)
        if not bill_path.exists():
            QMessageBox.warning(self, "Missing file", "Selected bill does not exist.")
            self.refresh_list()
            return

        try:
            open_path(bill_path)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Open failed", str(exc))


class RecordsPage(QWidget):
    def __init__(self, fm: FileManager, on_back):
        super().__init__()
        self.fm = fm

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 30, 34, 30)
        root.setSpacing(20)

        root.addWidget(
            PageHeader(
                "Records",
                "Access master records document and patient bill folders.",
                action=on_back,
            )
        )

        records_card = AppCard("Record Tools", "Open documents and folders from local storage")

        open_records_btn = QPushButton("Open MASTER_RECORDS.docx")
        open_records_btn.setObjectName("primaryButton")
        open_records_btn.clicked.connect(self.open_records)

        open_patients_btn = QPushButton("Open Patients Folder")
        open_patients_btn.setObjectName("secondaryButton")
        open_patients_btn.clicked.connect(self.open_patients_folder)

        records_card.layout.addWidget(open_records_btn)
        records_card.layout.addWidget(open_patients_btn)
        records_card.layout.addStretch(1)

        root.addWidget(records_card)
        root.addStretch(1)

    def open_records(self) -> None:
        try:
            self.fm._ensure_structure()
            open_path(self.fm.records_file)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Unable to open records file.\n{exc}")

    def open_patients_folder(self) -> None:
        try:
            self.fm._ensure_structure()
            open_path(self.fm.patients_dir)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Unable to open patients folder.\n{exc}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(CLINIC_NAME)
        self.resize(1300, 820)

        self.fm = FileManager(Path(__file__).resolve().parent)

        main = QWidget()
        main_layout = QHBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Major UI change: persistent navigation rail for clearer app hierarchy.
        nav = QFrame()
        nav.setObjectName("navRail")
        nav.setFixedWidth(250)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(22, 26, 22, 26)
        nav_layout.setSpacing(10)

        clinic_label = QLabel(CLINIC_NAME)
        clinic_label.setObjectName("navClinic")
        doctor_label = QLabel(DOCTOR_NAME)
        doctor_label.setObjectName("navDoctor")
        doctor_label.setWordWrap(True)

        nav_layout.addWidget(clinic_label)
        nav_layout.addWidget(doctor_label)
        nav_layout.addSpacing(12)

        self.stack = QStackedWidget()

        self.dashboard = DashboardPage(
            on_new=lambda: self.switch_page(self.new_patient_page),
            on_search=lambda: self.switch_page(self.search_page),
            on_bills=lambda: self.switch_page(self.view_bills_page),
            on_records=lambda: self.switch_page(self.records_page),
        )
        self.new_patient_page = NewPatientPage(self.fm, self.go_home)
        self.search_page = BillsListPage(
            self.fm,
            "Search Patient",
            "Search by patient name and open matching bills.",
            self.go_home,
            search_mode=True,
        )
        self.view_bills_page = BillsListPage(
            self.fm,
            "View Bills",
            "View all generated bills across patients.",
            self.go_home,
        )
        self.records_page = RecordsPage(self.fm, self.go_home)

        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.new_patient_page)
        self.stack.addWidget(self.search_page)
        self.stack.addWidget(self.view_bills_page)
        self.stack.addWidget(self.records_page)

        nav_items = [
            ("Dashboard", self.dashboard),
            ("New Patient", self.new_patient_page),
            ("Search Patient", self.search_page),
            ("View Bills", self.view_bills_page),
            ("Records", self.records_page),
        ]

        self.nav_buttons: dict[QPushButton, QWidget] = {}
        for label, page in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("navButton")
            btn.clicked.connect(lambda _, p=page: self.switch_page(p))
            nav_layout.addWidget(btn)
            self.nav_buttons[btn] = page

        nav_layout.addStretch(1)

        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.stack)

        main_layout.addWidget(nav)
        main_layout.addWidget(content, 1)

        self.setCentralWidget(main)
        self.switch_page(self.dashboard)
        self.showMaximized()

    def switch_page(self, page: QWidget) -> None:
        self.stack.setCurrentWidget(page)
        for button, target_page in self.nav_buttons.items():
            button.setProperty("active", target_page is page)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def go_home(self):
        self.switch_page(self.dashboard)


def apply_dark_theme(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QWidget {
            background-color: #0f1318;
            color: #eaf0f6;
            font-size: 14px;
            font-family: 'Segoe UI';
        }

        QFrame#navRail {
            background-color: #111b25;
            border-right: 1px solid #243342;
        }

        QLabel#navClinic {
            font-size: 18px;
            font-weight: 700;
            color: #f5fbff;
        }

        QLabel#navDoctor {
            color: #99aec3;
            font-size: 12px;
        }

        QPushButton#navButton {
            text-align: left;
            padding: 11px 14px;
            border-radius: 10px;
            border: 1px solid transparent;
            background-color: transparent;
            color: #d9e4ef;
            font-weight: 600;
        }

        QPushButton#navButton:hover {
            background-color: #192633;
            border: 1px solid #2c3d4f;
        }

        QPushButton#navButton[active="true"] {
            background-color: #213246;
            border: 1px solid #4f7aa0;
            color: #ffffff;
        }

        QFrame#card {
            background-color: #151d27;
            border: 1px solid #243343;
            border-radius: 14px;
        }

        QLabel#cardTitle {
            font-size: 17px;
            font-weight: 700;
            color: #f2f7fb;
        }

        QLabel#cardSubtitle {
            color: #9fb2c4;
            font-size: 13px;
        }

        QLabel#pageTitle {
            font-size: 24px;
            font-weight: 700;
            color: #f4f8fc;
        }

        QLabel#pageSubtitle {
            color: #9cb0c3;
            font-size: 13px;
        }

        QLabel#heroTitle {
            font-size: 28px;
            font-weight: 700;
            color: #ffffff;
        }

        QLabel#heroSubtitle {
            color: #b6c7d7;
            font-size: 14px;
        }

        QPushButton {
            border: 1px solid #304353;
            border-radius: 10px;
            padding: 10px 14px;
            background-color: #202d3b;
            color: #edf4fb;
            font-weight: 600;
        }

        QPushButton:hover {
            background-color: #2a3a4a;
            border: 1px solid #42627e;
        }

        QPushButton:pressed {
            background-color: #1a2530;
        }

        QPushButton#primaryButton, QPushButton#primaryAction {
            background-color: #2d7ff9;
            border: 1px solid #3a90ff;
            color: #ffffff;
            font-weight: 700;
        }

        QPushButton#primaryButton:hover, QPushButton#primaryAction:hover {
            background-color: #3f8eff;
        }

        QPushButton#secondaryButton {
            background-color: #1e2a36;
            border: 1px solid #344b60;
        }

        QPushButton#dashboardAction {
            text-align: left;
            padding: 14px;
        }

        QPushButton#primaryAction {
            text-align: left;
            padding: 14px;
        }

        QLineEdit, QDateEdit, QComboBox {
            background-color: #0f1822;
            border: 1px solid #34495d;
            border-radius: 9px;
            padding: 8px 10px;
            min-height: 22px;
            color: #eaf2fb;
        }

        QLineEdit:focus, QDateEdit:focus, QComboBox:focus {
            border: 1px solid #4a9dff;
            background-color: #101c28;
        }

        QListWidget {
            background-color: #0f1822;
            border: 1px solid #34495d;
            border-radius: 9px;
            padding: 6px;
        }

        QListWidget::item {
            padding: 10px 8px;
            border-radius: 8px;
        }

        QListWidget::item:hover {
            background-color: #1d2b39;
        }

        QListWidget::item:selected {
            background-color: #2b4560;
            color: #ffffff;
        }
        """
    )


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    apply_dark_theme(app)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
