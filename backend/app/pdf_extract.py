"""Local-only OCR fallback: macOS Vision or Tesseract rus+eng; no external AI."""
import shutil, subprocess, tempfile,sys
from pathlib import Path
from pypdf import PdfReader
from .config import ROOT

def extract_pages(path):
    reader=PdfReader(path)
    if len(reader.pages)>250:raise ValueError('Лимит 250 страниц на документ')
    pages=[p.extract_text() or '' for p in reader.pages]
    if sum(map(len,pages))>100*len(pages):return pages,'pdf-text'
    import pypdfium2 as pdfium
    doc=pdfium.PdfDocument(str(path));binary=ROOT/'runtime/ocr_macos';tesseract=shutil.which('tesseract')
    use_vision=sys.platform=='darwin' and binary.exists()
    if not use_vision and not tesseract:raise ValueError('Скан без текстового слоя: установите Tesseract rus+eng (или macOS Vision на macOS)')
    with tempfile.TemporaryDirectory() as directory:
        for i in range(len(pages)):
            if len(pages[i].strip())>100:continue
            image=Path(directory)/f'{i}.png';doc[i].render(scale=2.4).to_pil().save(image)
            args=[str(binary),str(image)] if use_vision else [tesseract,str(image),'stdout','-l','rus+eng']
            result=subprocess.run(args,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=100,check=True)
            pages[i]=result.stdout.strip()
    if not any(len(p)>100 for p in pages):raise ValueError('OCR не смог извлечь текст')
    return pages,'local-ocr:vision' if use_vision else 'local-ocr:tesseract'
