"""Extract PDF text in a short-lived worker. No file is retained on disk."""
import io
import json
import sys

MAX_PDF_BYTES = 10_000_000
MAX_PAGES = 200
MAX_TEXT = 1_000_000


def extract_pdf(data):
    from pypdf import PdfReader

    if not data or len(data) > MAX_PDF_BYTES:
        raise ValueError('Choose a PDF up to 10 MB.')
    if not data.lstrip().startswith(b'%PDF-'):
        raise ValueError('This file is not a valid PDF.')
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError('This PDF is password-protected. Export an unlocked copy and try again.')
        if not 0 < len(reader.pages) <= MAX_PAGES:
            raise ValueError('Choose a PDF with 1 to 200 pages.')
        pages, skipped, size = [], [], 0
        for number, page in enumerate(reader.pages, 1):
            contents = page.get_contents()
            if contents is not None and len(contents.get_data()) > 5_000_000:
                raise ValueError('A PDF page is too complex. Export a smaller PDF and try again.')
            text = (page.extract_text() or '').replace('\x00', '').strip()
            if not text:
                skipped.append(number)
                continue
            size += len(text)
            if size > MAX_TEXT:
                raise ValueError('This PDF contains too much text. Split it into smaller files.')
            pages.append({'page': number, 'text': text})
        if not pages:
            raise ValueError('No readable text found. Scanned PDFs need OCR first; upload a PDF with selectable text.')
        warning = ('Pages without readable text were skipped: ' + ', '.join(map(str, skipped)) +
                   '. Images and scans are not read; use OCR if they contain information.') if skipped else ''
        return {'pages': pages, 'total_pages': len(reader.pages), 'warning': warning}
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('This PDF could not be read. It may be damaged; export a new copy and try again.') from exc


if __name__ == '__main__':
    try:
        print(json.dumps(extract_pdf(sys.stdin.buffer.read(MAX_PDF_BYTES + 1)), ensure_ascii=False))
    except ImportError:
        print(json.dumps({'error': 'PDF support is not installed. Run the project setup from the README.'}))
    except ValueError as exc:
        print(json.dumps({'error': str(exc)}))
