"""Bounded local OCR for user-selected CPU inspection; never an assay.

Readable text provides candidates only, not proof of package identity or condition.
No network requests or model/price lookup is performed.
"""
import csv
import io
import os
import re
import shutil
import subprocess
from PIL import Image, ImageOps, ImageEnhance


def candidates_from_text(text):
    normalized = re.sub(r'[^A-Z0-9]+', ' ', text.upper())
    patterns = [
        (r'\bINTEL\b.*\bCORE\s*2\s*DUO\b', 'Intel Core 2 Duo'),
        (r'\bINTEL\b.*\bCORE\s*2\s*QUAD\b', 'Intel Core 2 Quad'),
        (r'\bINTEL\b.*\bCORE\s*I([3579])\b', None),
        (r'\bINTEL\b.*\bXEON\b', 'Intel Xeon'),
        (r'\bINTEL\b.*\bPENTIUM\b', 'Intel Pentium'),
        (r'\bINTEL\b.*\bCELERON\b', 'Intel Celeron'),
        (r'\bAMD\b.*\bRYZEN\b', 'AMD Ryzen'),
        (r'\bAMD\b.*\bATHLON\b', 'AMD Athlon'),
        (r'\bAMD\b.*\bSEMPRON\b', 'AMD Sempron'),
    ]
    found = []
    for pattern, label in patterns:
        match = re.search(pattern, normalized)
        if match:
            found.append(label or 'Intel Core i' + match.group(1))
    return sorted(set(found))


def _trusted_text(tsv):
    lines = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter='\t'):
        try:
            if float(row.get('conf', '-1')) < 60:
                continue
        except (ValueError, TypeError):
            continue
        word = (row.get('text') or '').strip()
        if word:
            key = tuple(row.get(k) for k in ('page_num', 'block_num', 'par_num', 'line_num'))
            lines.setdefault(key, []).append(word[:80])
    return '\n'.join(' '.join(words) for words in lines.values())[:1600]


def read_processor_markings(image_path):
    result = {'status': 'unresolved', 'candidates': [], 'observed_text': [],
              'message': 'No supported CPU family could be read. Add a straight-on close-up of the marked lid.'}
    binary = shutil.which('tesseract')
    if not binary:
        result.update(status='unavailable', message='CPU lettering reader is unavailable. Manual confirmation is required.')
        return result
    try:
        with Image.open(image_path) as original:
            image = ImageOps.exif_transpose(original).convert('L')
            image.thumbnail((1600, 1600))
            w, h = image.size
            views = [image, image.crop((w // 5, h // 5, w * 4 // 5, h * 4 // 5))]
            texts, candidates = [], set()
            for view in views:
                view = ImageOps.autocontrast(view)
                view = ImageEnhance.Contrast(view).enhance(1.5)
                buffer = io.BytesIO()
                view.save(buffer, format='PNG')
                proc = subprocess.run([binary, 'stdin', 'stdout', '-l', 'eng', '--psm', '6', 'tsv'],
                                      input=buffer.getvalue(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                      timeout=3, check=True, env={**os.environ, 'OMP_THREAD_LIMIT': '1'})
                text = _trusted_text(proc.stdout.decode('utf-8', errors='replace'))
                matches = candidates_from_text(text)
                # Keep raw lettering only when it supports a CPU family candidate.
                if matches:
                    texts.append(text)
                    candidates.update(matches)
            result.update(candidates=sorted(candidates), observed_text=list(dict.fromkeys(texts)))
            if candidates:
                result.update(status='candidate' if len(candidates) == 1 else 'conflict',
                              message='Lettering suggests a CPU family; confirm the markings and physical item. Exact model, condition and metal content are unverified.')
    except (OSError, ValueError, subprocess.SubprocessError):
        result.update(status='unavailable', message='CPU lettering could not be read within the inspection limit. Manual confirmation is required.')
    return result
