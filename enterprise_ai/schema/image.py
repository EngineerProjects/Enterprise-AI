"""
Image handling schemas for Enterprise AI.

This module defines data models for handling images in messages and responses.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import base64
import mimetypes


class ImageFormat(Enum):
    """Supported image formats."""
    
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    WEBP = "webp"
    BMP = "bmp"
    TIFF = "tiff"
    
    @classmethod
    def from_mime_type(cls, mime_type: str) -> Optional["ImageFormat"]:
        """Get format from MIME type."""
        mime_to_format = {
            "image/jpeg": cls.JPEG,
            "image/png": cls.PNG,
            "image/gif": cls.GIF,
            "image/webp": cls.WEBP,
            "image/bmp": cls.BMP,
            "image/tiff": cls.TIFF,
        }
        return mime_to_format.get(mime_type.lower())
    
    def to_mime_type(self) -> str:
        """Get MIME type for format."""
        format_to_mime = {
            self.JPEG: "image/jpeg",
            self.PNG: "image/png", 
            self.GIF: "image/gif",
            self.WEBP: "image/webp",
            self.BMP: "image/bmp",
            self.TIFF: "image/tiff",
        }
        return format_to_mime[self]


@dataclass
class ImageMetadata:
    """Metadata about an image."""
    
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[ImageFormat] = None
    size_bytes: Optional[int] = None
    source: Optional[str] = None  # "file", "url", "base64", etc.
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    encoding: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "source": self.source,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "encoding": self.encoding,
            "extra_data": self.extra_data,
        }
        if self.format:
            result["format"] = self.format.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageMetadata":
        """Create from dictionary."""
        format_val = data.get("format")
        image_format = ImageFormat(format_val) if format_val else None
        
        return cls(
            width=data.get("width"),
            height=data.get("height"),
            format=image_format,
            size_bytes=data.get("size_bytes"),
            source=data.get("source"),
            original_filename=data.get("original_filename"),
            mime_type=data.get("mime_type"),
            encoding=data.get("encoding"),
            extra_data=data.get("extra_data", {}),
        )


@dataclass
class ImageInfo:
    """Information about an image in a message."""
    
    data: str  # Base64 encoded image data or URL
    metadata: ImageMetadata = field(default_factory=ImageMetadata)
    alt_text: Optional[str] = None
    
    def is_base64(self) -> bool:
        """Check if image data is base64 encoded."""
        return self.data.startswith("data:") or self.metadata.source == "base64"
    
    def is_url(self) -> bool:
        """Check if image data is a URL."""
        return self.data.startswith(("http://", "https://")) or self.metadata.source == "url"
    
    def get_base64_data(self) -> Optional[str]:
        """Extract base64 data portion."""
        if self.is_base64() and self.data.startswith("data:"):
            # Extract from data URL format
            if "," in self.data:
                return self.data.split(",", 1)[1]
        elif self.metadata.source == "base64":
            return self.data
        return None
    
    def get_mime_type(self) -> Optional[str]:
        """Get MIME type of the image."""
        if self.metadata.mime_type:
            return self.metadata.mime_type
        
        if self.is_base64() and self.data.startswith("data:"):
            # Extract from data URL
            prefix = self.data.split(",")[0]
            if ":" in prefix and ";" in prefix:
                return prefix.split(":")[1].split(";")[0]
        
        if self.is_url():
            # Guess from URL extension
            return mimetypes.guess_type(self.data)[0]
        
        return None
    
    def to_data_url(self) -> str:
        """Convert to data URL format."""
        if self.is_base64() and self.data.startswith("data:"):
            return self.data
        
        mime_type = self.get_mime_type() or "image/jpeg"
        base64_data = self.get_base64_data() or self.data
        return f"data:{mime_type};base64,{base64_data}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "data": self.data,
            "metadata": self.metadata.to_dict(),
            "alt_text": self.alt_text,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImageInfo":
        """Create from dictionary."""
        metadata = ImageMetadata.from_dict(data.get("metadata", {}))
        return cls(
            data=data["data"],
            metadata=metadata,
            alt_text=data.get("alt_text"),
        )
    
    @classmethod
    def from_base64(
        cls,
        base64_data: str,
        mime_type: Optional[str] = None,
        alt_text: Optional[str] = None,
        **metadata_kwargs: Any
    ) -> "ImageInfo":
        """Create from base64 data."""
        metadata = ImageMetadata(
            mime_type=mime_type,
            source="base64",
            **metadata_kwargs
        )
        
        if mime_type and not base64_data.startswith("data:"):
            data = f"data:{mime_type};base64,{base64_data}"
        else:
            data = base64_data
        
        return cls(data=data, metadata=metadata, alt_text=alt_text)
    
    @classmethod
    def from_url(
        cls,
        url: str,
        alt_text: Optional[str] = None,
        **metadata_kwargs: Any
    ) -> "ImageInfo":
        """Create from URL."""
        metadata = ImageMetadata(
            source="url",
            mime_type=mimetypes.guess_type(url)[0],
            **metadata_kwargs
        )
        return cls(data=url, metadata=metadata, alt_text=alt_text)