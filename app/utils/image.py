"""Upload de imagens/documentos para o Supabase Storage / Cloudinary."""

import inspect
import logging
import os
import uuid

from fastapi import HTTPException, UploadFile

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "image/avif",
    "image/gif",
}
ALLOWED_DOC_TYPES = ALLOWED_IMAGE_TYPES | {"application/pdf"}
MAX_FILE_SIZE_MB = 10


async def upload_image(file: UploadFile, folder: str = "ads") -> str:
    """Faz upload de uma imagem e retorna a URL pública."""
    return await _upload(file, folder, ALLOWED_IMAGE_TYPES, "imagem")


async def upload_document(file: UploadFile, folder: str = "docs") -> str:
    """Upload de documento (ex.: BO de pessoa desaparecida). Aceita imagem ou PDF."""
    return await _upload(file, folder, ALLOWED_DOC_TYPES, "documento")


async def _upload(
    file: UploadFile, folder: str, allowed_types: set[str], label: str
) -> str:
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de {label} não permitido: {file.content_type}.",
        )
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"{label.capitalize()} excede o tamanho máximo de {MAX_FILE_SIZE_MB}MB.",
        )

    # 1. Tentar upload para o Google Cloud Storage (Bucket Firebase/GCP)
    try:
        import asyncio
        from google.cloud import storage

        def _sync_gcs_upload(data: bytes, path: str, content_type: str) -> str:
            client = storage.Client(project=settings.FIREBASE_PROJECT_ID)
            bucket_name = settings.FIREBASE_STORAGE_BUCKET or f"{settings.FIREBASE_PROJECT_ID}.firebasestorage.app"
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(path)
            blob.upload_from_string(data, content_type=content_type)
            # URL pública direta via GCS
            return f"https://storage.googleapis.com/{bucket_name}/{path}"

        ext = os.path.splitext(file.filename or "")[1] or ".jpg"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        storage_path = f"{folder}/{unique_name}"
        ctype = file.content_type or "image/jpeg"

        public_url = await asyncio.to_thread(_sync_gcs_upload, content, storage_path, ctype)
        return public_url
    except Exception as gcs_exc:
        logger.warning("Falha no upload para o Google Cloud Storage (%s), tentando fallback...", gcs_exc)

    # 2. Fallback para Cloudinary se configurado
    if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
        try:
            import asyncio
            import cloudinary
            import cloudinary.uploader

            cloudinary.config(
                cloud_name=settings.CLOUDINARY_CLOUD_NAME,
                api_key=settings.CLOUDINARY_API_KEY,
                api_secret=settings.CLOUDINARY_API_SECRET,
                secure=True,
            )
            result = await asyncio.to_thread(
                cloudinary.uploader.upload,
                content,
                folder=f"bnf/{folder}",
                resource_type="auto",
            )
            return result["secure_url"]
        except Exception as c_exc:
            logger.error("Falha no upload para o Cloudinary: %s", c_exc)

    # 3. Fallback para Base64 Data URL (para imagens ou vídeos leves caso storage falhe temporariamente)
    if (file.content_type in ALLOWED_IMAGE_TYPES or file.content_type in allowed_types) and len(content) <= 8 * 1024 * 1024:
        import base64
        logger.info("Utilizando fallback Base64 para upload (%s bytes, %s)", len(content), file.content_type)
        b64 = base64.b64encode(content).decode("ascii")
        return f"data:{file.content_type};base64,{b64}"

    raise HTTPException(status_code=502, detail="Falha no upload do arquivo. Tente novamente.")
