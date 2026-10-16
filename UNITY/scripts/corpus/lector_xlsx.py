"""
lector_xlsx.py
Lector nativo de archivos .xlsx usando únicamente la biblioteca estándar de Python (zipfile + xml.etree.ElementTree).
No requiere dependencias externas como pandas ni openpyxl.
"""
import zipfile
import xml.etree.ElementTree as ET
import os

def leer_xlsx(ruta_archivo, sheet_index=1):
    """
    Lee una hoja de un archivo Excel .xlsx y retorna una lista de filas (list of lists).
    """
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"No se encontró el archivo: {ruta_archivo}")

    with zipfile.ZipFile(ruta_archivo, 'r') as z:
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                texts = [t.text for t in si.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t') if t.text]
                shared_strings.append(''.join(texts))

        sheet_file = f'xl/worksheets/sheet{sheet_index}.xml'
        if sheet_file not in z.namelist():
            sheet_files = sorted([f for f in z.namelist() if f.startswith('xl/worksheets/sheet') and f.endswith('.xml')])
            if not sheet_files:
                raise ValueError(f"No se encontraron hojas en {ruta_archivo}")
            sheet_file = sheet_files[sheet_index - 1] if sheet_index - 1 < len(sheet_files) else sheet_files[0]

        sheet_tree = ET.fromstring(z.read(sheet_file))
        rows_data = []

        for row in sheet_tree.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
            row_cells = {}
            for c in row.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                r = c.attrib.get('r', '')
                col = ''.join([ch for ch in r if ch.isalpha()])
                t = c.attrib.get('t')
                v = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                val = ''
                if v is not None and v.text is not None:
                    if t == 's':
                        idx = int(v.text)
                        val = shared_strings[idx] if idx < len(shared_strings) else v.text
                    else:
                        val = v.text
                elif c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is') is not None:
                    is_elem = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is')
                    t_elem = is_elem.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                    if t_elem is not None:
                        val = t_elem.text
                row_cells[col] = val.strip()

            if row_cells:
                def col_to_num(col_str):
                    num = 0
                    for ch in col_str:
                        num = num * 26 + (ord(ch.upper()) - ord('A') + 1)
                    return num

                sorted_cols = sorted(row_cells.keys(), key=col_to_num)
                max_col_num = col_to_num(sorted_cols[-1])
                row_list = [''] * max_col_num
                for col_name, cell_val in row_cells.items():
                    row_list[col_to_num(col_name) - 1] = cell_val
                rows_data.append(row_list)

        return rows_data
