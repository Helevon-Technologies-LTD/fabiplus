"""
File processing system for FABI+ media uploads
Handles thumbnail generation, image optimization, and metadata extraction
"""

import asyncio
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import ExifTags, Image, ImageOps

from .storage import FileMetadata


class ProcessingError(Exception):
    """Custom exception for file processing errors"""

    pass


class FileProcessor:
    """Base file processor"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.thumbnail_sizes = self.config.get(
            "thumbnail_sizes", [(150, 150), (300, 300), (600, 600)]
        )
        self.quality = self.config.get("quality", 85)
        self.optimize = self.config.get("optimize", True)

    async def process(self, content: bytes, metadata: FileMetadata) -> Dict[str, Any]:
        """Process file and return additional metadata"""

        result = {
            "thumbnails": {},
            "variants": {},
            "metadata": {},
            "processing_errors": [],
        }

        try:
            # Determine file type and process accordingly
            if metadata.content_type.startswith("image/"):
                await self._process_image(content, metadata, result)
            elif metadata.content_type.startswith("video/"):
                await self._process_video(content, metadata, result)
            elif metadata.content_type.startswith("audio/"):
                await self._process_audio(content, metadata, result)
            elif metadata.content_type == "application/pdf":
                await self._process_pdf(content, metadata, result)

        except Exception as e:
            result["processing_errors"].append(f"Processing failed: {str(e)}")

        return result

    async def _process_image(
        self, content: bytes, metadata: FileMetadata, result: Dict[str, Any]
    ):
        """Process image files"""
        try:
            image = Image.open(BytesIO(content))

            # Extract EXIF data
            exif_data = await self._extract_exif_data(image)
            result["metadata"].update(exif_data)

            # Store original dimensions
            result["width"] = image.width
            result["height"] = image.height

            # Auto-rotate based on EXIF orientation
            image = ImageOps.exif_transpose(image)

            # Generate thumbnails
            thumbnails = await self._generate_thumbnails(image, metadata)
            result["thumbnails"] = thumbnails

            # Generate optimized variants
            variants = await self._generate_image_variants(image, metadata)
            result["variants"] = variants

        except Exception as e:
            result["processing_errors"].append(f"Image processing failed: {str(e)}")

    async def _extract_exif_data(self, image: Image.Image) -> Dict[str, Any]:
        """Extract EXIF metadata from image"""
        exif_data = {}

        try:
            if hasattr(image, "_getexif") and image._getexif() is not None:
                exif = image._getexif()

                for tag_id, value in exif.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)

                    # Convert bytes to string for JSON serialization
                    if isinstance(value, bytes):
                        try:
                            value = value.decode("utf-8")
                        except UnicodeDecodeError:
                            value = str(value)

                    exif_data[tag] = value

                # Extract common metadata
                if "DateTime" in exif_data:
                    exif_data["date_taken"] = exif_data["DateTime"]

                if "Make" in exif_data and "Model" in exif_data:
                    exif_data["camera"] = f"{exif_data['Make']} {exif_data['Model']}"

        except Exception:
            # EXIF extraction is optional, don't fail if it doesn't work
            pass

        return exif_data

    async def _generate_thumbnails(
        self, image: Image.Image, metadata: FileMetadata
    ) -> Dict[str, str]:
        """Generate thumbnails for image"""
        thumbnails = {}

        for width, height in self.thumbnail_sizes:
            try:
                # Create thumbnail
                thumbnail = image.copy()
                thumbnail.thumbnail((width, height), Image.Resampling.LANCZOS)

                # Save thumbnail
                thumbnail_buffer = BytesIO()

                # Use JPEG for thumbnails to save space
                if thumbnail.mode in ("RGBA", "LA", "P"):
                    # Convert to RGB for JPEG
                    rgb_thumbnail = Image.new("RGB", thumbnail.size, (255, 255, 255))
                    rgb_thumbnail.paste(
                        thumbnail,
                        mask=thumbnail.split()[-1]
                        if thumbnail.mode == "RGBA"
                        else None,
                    )
                    thumbnail = rgb_thumbnail

                thumbnail.save(
                    thumbnail_buffer,
                    format="JPEG",
                    quality=self.quality,
                    optimize=self.optimize,
                )

                # Generate thumbnail filename
                size_name = f"{width}x{height}"
                thumbnail_filename = f"thumb_{size_name}_{metadata.filename}"

                # TODO: Save thumbnail to storage and get URL
                # For now, just store the size info
                thumbnails[size_name] = f"/media/thumbnails/{thumbnail_filename}"

            except Exception as e:
                # Don't fail entire processing if thumbnail generation fails
                continue

        return thumbnails

    async def _generate_image_variants(
        self, image: Image.Image, metadata: FileMetadata
    ) -> Dict[str, str]:
        """Generate optimized variants of image"""
        variants = {}

        try:
            # Generate web-optimized version
            web_image = image.copy()

            # Resize if too large
            max_web_size = self.config.get("max_web_size", (1920, 1080))
            if web_image.width > max_web_size[0] or web_image.height > max_web_size[1]:
                web_image.thumbnail(max_web_size, Image.Resampling.LANCZOS)

            # Save web version
            web_buffer = BytesIO()

            if web_image.mode in ("RGBA", "LA", "P"):
                # Convert to RGB for JPEG
                rgb_image = Image.new("RGB", web_image.size, (255, 255, 255))
                rgb_image.paste(
                    web_image,
                    mask=web_image.split()[-1] if web_image.mode == "RGBA" else None,
                )
                web_image = rgb_image

            web_image.save(
                web_buffer, format="JPEG", quality=self.quality, optimize=self.optimize
            )

            # TODO: Save variant to storage and get URL
            variants["web"] = f"/media/variants/web_{metadata.filename}"

        except Exception as e:
            # Variant generation is optional
            pass

        return variants

    async def _process_video(
        self, content: bytes, metadata: FileMetadata, result: Dict[str, Any]
    ):
        """Process video files"""
        try:
            # Video processing would require ffmpeg
            # For now, just extract basic info
            result["processing_errors"].append("Video processing not fully implemented")

            # TODO: Extract video metadata (duration, resolution, codec)
            # TODO: Generate video thumbnails
            # TODO: Generate preview clips

        except Exception as e:
            result["processing_errors"].append(f"Video processing failed: {str(e)}")

    async def _process_audio(
        self, content: bytes, metadata: FileMetadata, result: Dict[str, Any]
    ):
        """Process audio files"""
        try:
            # Audio processing would require mutagen or similar
            # For now, just extract basic info
            result["processing_errors"].append("Audio processing not fully implemented")

            # TODO: Extract audio metadata (duration, bitrate, artist, album)
            # TODO: Generate waveform visualization
            # TODO: Generate audio previews

        except Exception as e:
            result["processing_errors"].append(f"Audio processing failed: {str(e)}")

    async def _process_pdf(
        self, content: bytes, metadata: FileMetadata, result: Dict[str, Any]
    ):
        """Process PDF files"""
        try:
            from io import BytesIO

            import PyPDF2

            pdf_reader = PyPDF2.PdfReader(BytesIO(content))

            # Extract PDF metadata
            result["metadata"]["num_pages"] = len(pdf_reader.pages)

            if pdf_reader.metadata:
                result["metadata"]["pdf_title"] = pdf_reader.metadata.get("/Title", "")
                result["metadata"]["pdf_author"] = pdf_reader.metadata.get(
                    "/Author", ""
                )
                result["metadata"]["pdf_subject"] = pdf_reader.metadata.get(
                    "/Subject", ""
                )
                result["metadata"]["pdf_creator"] = pdf_reader.metadata.get(
                    "/Creator", ""
                )
                result["metadata"]["pdf_producer"] = pdf_reader.metadata.get(
                    "/Producer", ""
                )

            # TODO: Generate PDF thumbnails (first page)
            # TODO: Extract text content for search indexing

        except Exception as e:
            result["processing_errors"].append(f"PDF processing failed: {str(e)}")


class ImageProcessor(FileProcessor):
    """Specialized processor for images"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.watermark_enabled = self.config.get("watermark_enabled", False)
        self.watermark_text = self.config.get("watermark_text", "")
        self.auto_enhance = self.config.get("auto_enhance", False)

    async def _process_image(
        self, content: bytes, metadata: FileMetadata, result: Dict[str, Any]
    ):
        """Enhanced image processing"""
        await super()._process_image(content, metadata, result)

        try:
            image = Image.open(BytesIO(content))

            # Auto-enhance if enabled
            if self.auto_enhance:
                enhanced_variants = await self._auto_enhance_image(image, metadata)
                result["variants"].update(enhanced_variants)

            # Add watermark if enabled
            if self.watermark_enabled and self.watermark_text:
                watermarked_variants = await self._add_watermark(image, metadata)
                result["variants"].update(watermarked_variants)

        except Exception as e:
            result["processing_errors"].append(
                f"Enhanced image processing failed: {str(e)}"
            )

    async def _auto_enhance_image(
        self, image: Image.Image, metadata: FileMetadata
    ) -> Dict[str, str]:
        """Auto-enhance image (brightness, contrast, etc.)"""
        variants = {}

        try:
            # Auto-enhance using PIL
            enhanced = ImageOps.autocontrast(image)
            enhanced = ImageOps.equalize(enhanced)

            # Save enhanced version
            enhanced_buffer = BytesIO()
            enhanced.save(
                enhanced_buffer,
                format="JPEG",
                quality=self.quality,
                optimize=self.optimize,
            )

            # TODO: Save to storage
            variants["enhanced"] = f"/media/variants/enhanced_{metadata.filename}"

        except Exception:
            pass

        return variants

    async def _add_watermark(
        self, image: Image.Image, metadata: FileMetadata
    ) -> Dict[str, str]:
        """Add watermark to image"""
        variants = {}

        try:
            from PIL import ImageDraw, ImageFont

            watermarked = image.copy()
            draw = ImageDraw.Draw(watermarked)

            # Try to use a nice font, fall back to default
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except:
                font = ImageFont.load_default()

            # Position watermark in bottom right
            # Get text bounding box
            bbox = draw.textbbox((0, 0), self.watermark_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = watermarked.width - text_width - 10
            y = watermarked.height - text_height - 10

            # Add semi-transparent background
            draw.rectangle(
                [x - 5, y - 5, x + text_width + 5, y + text_height + 5],
                fill=(0, 0, 0, 128),
            )

            # Add text
            draw.text((x, y), self.watermark_text, font=font, fill=(255, 255, 255, 255))

            # Save watermarked version
            watermarked_buffer = BytesIO()
            watermarked.save(
                watermarked_buffer,
                format="JPEG",
                quality=self.quality,
                optimize=self.optimize,
            )

            # TODO: Save to storage
            variants["watermarked"] = f"/media/variants/watermarked_{metadata.filename}"

        except Exception:
            pass

        return variants


class DocumentProcessor(FileProcessor):
    """Specialized processor for documents"""

    async def _process_pdf(
        self, content: bytes, metadata: FileMetadata, result: Dict[str, Any]
    ):
        """Enhanced PDF processing"""
        await super()._process_pdf(content, metadata, result)

        try:
            # Extract text content for search indexing
            text_content = await self._extract_pdf_text(content)
            result["metadata"]["text_content"] = text_content[:1000]  # First 1000 chars
            result["metadata"]["text_length"] = len(text_content)

            # Generate PDF thumbnail
            thumbnail_url = await self._generate_pdf_thumbnail(content, metadata)
            if thumbnail_url:
                result["thumbnails"]["pdf_preview"] = thumbnail_url

        except Exception as e:
            result["processing_errors"].append(
                f"Enhanced PDF processing failed: {str(e)}"
            )

    async def _extract_pdf_text(self, content: bytes) -> str:
        """Extract text content from PDF"""
        try:
            from io import BytesIO

            import PyPDF2

            pdf_reader = PyPDF2.PdfReader(BytesIO(content))
            text_content = ""

            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"

            return text_content.strip()

        except Exception:
            return ""

    async def _generate_pdf_thumbnail(
        self, content: bytes, metadata: FileMetadata
    ) -> Optional[str]:
        """Generate thumbnail from first page of PDF"""
        try:
            # This would require pdf2image or similar
            # For now, return placeholder
            return f"/media/thumbnails/pdf_preview_{metadata.filename}.jpg"

        except Exception:
            return None
