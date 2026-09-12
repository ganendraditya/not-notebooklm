import os
import io
import json
import zipfile
import asyncio
import logging
import concurrent.futures
import uuid as uuid_pkg
from typing import List, AsyncGenerator
from sqlalchemy.orm import Session

from database import Document
from utils.file_utils import TEMP_ZIPS_DIR, get_doc_file_path
from utils.pdf_utils import get_authentic_document_pdf

logger = logging.getLogger("uvicorn.error")

async def generate_bulk_zip_stream(
    chat_id: str,
    doc_ids: List[int],
    db: Session
) -> AsyncGenerator[str, None]:
    """
    Generates SSE events and streams progress for packaging authentic full-text PDFs into a ZIP file.
    """
    docs = db.query(Document).filter(Document.id.in_(doc_ids), Document.chat_id == chat_id).all()
    if not docs:
        yield f"data: {json.dumps({'type': 'error', 'message': 'No documents found for download'})}\n\n"
        return

    doc_records = [(d.id, d.filename, d.title or d.filename, d.doi or "", d.url or "") for d in docs]
    total_count = len(doc_records)
    task_id = str(uuid_pkg.uuid4())
    zip_file_path = os.path.join(TEMP_ZIPS_DIR, f"{task_id}.zip")

    queue: asyncio.Queue = asyncio.Queue()

    def worker_sync():
        seen_names = set()
        processed_count = 0
        downloaded_count = 0
        skipped_docs = []
        
        with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
            def process_single(doc_info):
                d_id, d_fn, d_title, d_doi, d_url = doc_info
                try:
                    pdf_data, clean_name = get_authentic_document_pdf(chat_id, d_fn)
                    if pdf_data:
                        return d_fn, d_title, d_doi, d_url, clean_name, pdf_data, None
                    
                    file_path = get_doc_file_path(chat_id, d_fn)
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            file_bytes = f.read()
                        if file_bytes:
                            return d_fn, d_title, d_doi, d_url, d_fn, file_bytes, None
                    
                    return d_fn, d_title, d_doi, d_url, d_fn, None, None
                except Exception as e:
                    logger.error(f"[Worker Sync PDF Error]: {e}")
                    return d_fn, d_title, d_doi, d_url, d_fn, None, str(e)

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(total_count, 6)) as executor:
                futures = [executor.submit(process_single, info) for info in doc_records]
                for fut in concurrent.futures.as_completed(futures):
                    orig_fn, item_title, item_doi, item_url, clean_fn, pdf_bytes, err = fut.result()
                    processed_count += 1
                    if pdf_bytes:
                        downloaded_count += 1
                        base_name = clean_fn
                        counter = 1
                        while base_name in seen_names:
                            root, ext = os.path.splitext(clean_fn)
                            base_name = f"{root}_{counter}{ext}"
                            counter += 1
                        seen_names.add(base_name)
                        zf.writestr(base_name, pdf_bytes)
                    else:
                        skipped_docs.append({
                            "filename": orig_fn,
                            "title": item_title,
                            "doi": item_doi,
                            "url": item_url or (f"https://doi.org/{item_doi}" if item_doi else "N/A")
                        })
                    
                    calc_percent = round((processed_count / max(1, total_count)) * 100)
                    queue.put_nowait({
                        "type": "progress",
                        "current": processed_count,
                        "total": total_count,
                        "downloaded_count": downloaded_count,
                        "skipped_count": len(skipped_docs),
                        "percent": calc_percent,
                        "filename": orig_fn,
                        "is_skipped": pdf_bytes is None
                    })

            if skipped_docs:
                summary_lines = [
                    "================================================================================",
                    "NOTBOOKLM - RINGKASAN UNDUHAN DOKUMEN",
                    "================================================================================",
                    f"Total Dokumen Dipilih : {total_count}",
                    f"Naskah Lengkap PDF Berhasil Diunduh : {downloaded_count}",
                    f"Dokumen Dilewati (Hanya Abstrak / Paywalled) : {len(skipped_docs)}",
                    "================================================================================",
                    "",
                    "DAFTAR DOKUMEN YANG DILEWATI (NASKAH LENGKAP TIDAK DAPAT DIUNDUH OTOMATIS):",
                    ""
                ]
                for idx, item in enumerate(skipped_docs, 1):
                    summary_lines.append(f"{idx}. {item['title']}")
                    summary_lines.append(f"   Status : Naskah Berbayar (Paywalled) / Proteksi Repositori (HTTP 403)")
                    summary_lines.append(f"   DOI / Tautan Resmi : {item['url']}")
                    summary_lines.append("")
                summary_lines.append("Silakan unduh naskah lengkap melalui tautan resmi penerbit di atas.")
                zf.writestr("_CATATAN_DOKUMEN_DILEWATI.txt", "\n".join(summary_lines))
        
        if downloaded_count == 0 and len(skipped_docs) > 0:
            try:
                if os.path.exists(zip_file_path):
                    os.remove(zip_file_path)
            except Exception:
                pass
            queue.put_nowait({
                "type": "error",
                "message": "Tidak ada naskah lengkap PDF yang dapat diunduh (dokumen yang dipilih hanya berstatus metadata / abstrak)."
            })
        else:
            total_size_mb = round(os.path.getsize(zip_file_path) / (1024 * 1024), 2) if os.path.exists(zip_file_path) else 0.0
            queue.put_nowait({
                "type": "complete",
                "task_id": task_id,
                "total": total_count,
                "downloaded_count": downloaded_count,
                "skipped_count": len(skipped_docs),
                "percent": 100,
                "filename": f"NotbookLM_Sources_{downloaded_count}_files.zip",
                "total_size_mb": total_size_mb,
                "download_url": f"/chats/{chat_id}/documents/download_zip/{task_id}"
            })
        queue.put_nowait(None)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, worker_sync)

    while True:
        item = await queue.get()
        if item is None:
            break
        yield f"data: {json.dumps(item)}\n\n"
