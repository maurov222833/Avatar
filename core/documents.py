"""Entregables verificables (spec 003, U11).

Los números salen de los datos de entrada. Un descuadre se informa, no se tapa.
Las bibliotecas de oficina no están en el entorno: el .docx y el .xlsx se
escriben como OOXML mínimo, que es el formato real de esos archivos.
"""
from __future__ import annotations

import os
import zipfile
from typing import Dict, Iterable, List, Optional, Tuple
from xml.sax.saxutils import escape

FINANCIAL_WARNING = (
    "Borrador de trabajo. Antes de presentarlo ante un banco, una autoridad "
    "tributaria o terceros, debe revisarlo un contador o profesional habilitado. "
    "Avatar no certifica estados financieros."
)


def accounting_equation(assets: float, liabilities: float, equity: float) -> Optional[str]:
    if round(assets - (liabilities + equity), 2) != 0:
        return "DESCUADRE: activos no igualan pasivo más patrimonio"
    return None


def cash_reconciles(closing_cash: float, balance_cash: float) -> Optional[str]:
    if round(closing_cash - balance_cash, 2) != 0:
        return "DESCUADRE: el efectivo del flujo no coincide con el balance"
    return None


def atomic_write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".partial"
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.replace(tmp, path)


def build_docx(path: str, title: str, sections: List[Tuple[str, str]]) -> str:
    body = [f"<w:p><w:r><w:t>{escape(title)}</w:t></w:r></w:p>"]
    for heading, text in sections:
        body.append(f"<w:p><w:r><w:t>{escape(heading)}</w:t></w:r></w:p>")
        body.append(f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>")
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body)}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return path


def docx_text(path: str) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    chunks = []
    for part in xml.split("<w:t>")[1:]:
        chunks.append(part.split("</w:t>")[0])
    return "\n".join(chunks)


def build_xlsx(path: str, sheets: Dict[str, List[List[str]]]) -> str:
    """Celdas como texto XML. Un valor que empieza por '=' se guarda como fórmula."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    sheet_xml = []
    for name, rows in sheets.items():
        xml_rows = []
        for r_index, row in enumerate(rows, start=1):
            cells = []
            for c_index, value in enumerate(row):
                col = chr(ord("A") + c_index)
                ref = f"{col}{r_index}"
                if str(value).startswith("="):
                    cells.append(f'<c r="{ref}"><f>{escape(str(value)[1:])}</f></c>')
                else:
                    cells.append(
                        f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
                    )
            xml_rows.append(f'<row r="{r_index}">{"".join(cells)}</row>')
        sheet_xml.append((name, "".join(xml_rows)))
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_xml[0][0])}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{sheet_xml[0][1]}</sheetData></worksheet>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return path


def xlsx_has_formula(path: str) -> bool:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    return "<f>" in xml


def verify_reference(reference: Dict[str, str], corpus: Iterable[Dict[str, str]]) -> bool:
    """Solo entra una referencia que coincide con una fuente consultada."""
    for item in corpus:
        if (
            item.get("title") == reference.get("title")
            and item.get("author") == reference.get("author")
            and str(item.get("year")) == str(reference.get("year"))
        ):
            return True
    return False
