import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from pdf_import import extract_pdf
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject


def fixture(texts, password=None):
    writer = PdfWriter()
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    font_id = writer._add_object(font)
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        if text:
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font_id})})
            content = DecodedStreamObject()
            content.set_data(f'BT /F1 12 Tf 50 700 Td ({text}) Tj ET'.encode())
            page[NameObject('/Contents')] = writer._add_object(content)
    if password: writer.encrypt(password)
    out = io.BytesIO(); writer.write(out)
    return out.getvalue()


class PdfTests(unittest.TestCase):
    def test_page_numbers_and_text_survive_blank_pages(self):
        result = extract_pdf(fixture(['Launch: 12 November 2026.', '', 'Owner: Olena. Budget: 4200 PLN.']))
        self.assertEqual([p['page'] for p in result['pages']], [1, 3])
        self.assertIn('4200 PLN', result['pages'][1]['text'])
        self.assertEqual(result['total_pages'], 3)
        self.assertIn('2', result['warning'])

    def test_no_text_is_actionable(self):
        with self.assertRaisesRegex(ValueError, 'OCR'): extract_pdf(fixture(['']))

    def test_locked_pdf_rejected(self):
        with self.assertRaisesRegex(ValueError, 'password'): extract_pdf(fixture(['Private'], 'secret'))

    def test_invalid_and_oversized_pdf(self):
        for data in [b'not a PDF', b'%PDF-broken', b'x' * 10_000_001]:
            with self.assertRaises(ValueError): extract_pdf(data)

    def test_page_limit(self):
        with self.assertRaisesRegex(ValueError, '200 pages'): extract_pdf(fixture([''] * 201))

if __name__ == '__main__': unittest.main()
