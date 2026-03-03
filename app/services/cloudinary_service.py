import cloudinary
import cloudinary.uploader
from fastapi import UploadFile
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
)


async def upload_tender_attachment(file: UploadFile, tender_number: str) -> dict:
    """Upload a single file to Cloudinary and return its metadata."""
    try:
        contents = await file.read()
        result = cloudinary.uploader.upload(
            contents,
            folder=f"tenders/{tender_number}",
            resource_type="auto",  # handles PDFs, images, docs
            public_id=f"{tender_number}_{file.filename}",
            overwrite=True,
        )
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "file_name": file.filename,
            "file_type": file.content_type,
            "size": result.get("bytes"),
        }
    except Exception as exc:
        logger.error(
            "Cloudinary upload failed",
            extra={"file": file.filename, "error": str(exc)},
        )
        raise


async def delete_tender_attachment(public_id: str) -> None:
    """Delete a file from Cloudinary by public_id."""
    try:
        cloudinary.uploader.destroy(public_id, resource_type="raw")
    except Exception as exc:
        logger.error(
            "Cloudinary delete failed",
            extra={"public_id": public_id, "error": str(exc)},
        )
        raise
