"""
Enterprise AI Test Utilities - Optimized for minimal code with maximum visual impact.
"""

import os
import sys
import io
import time
import base64
import random
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple

# Image processing
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def setup_project_path():
    """Setup project path and ensure directories exist."""
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    (Path(__file__).parent / 'images').mkdir(exist_ok=True)
    return project_root

# ═══════════════════════════════════════════════════════════════════════════════
# 🎨 VISUAL TERMINAL OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

class Style:
    """Terminal styling with visual icons."""
    BLUE = "\033[1;34m"; GREEN = "\033[1;32m"; RED = "\033[1;31m"
    YELLOW = "\033[1;33m"; PURPLE = "\033[1;35m"; CYAN = "\033[1;36m"
    BOLD = "\033[1m"; RESET = "\033[0m"

def print_header(title: str, style: str = "double"):
    """Print visually striking headers."""
    styles = {
        "double": (f"{Style.BLUE}{'═' * 80}\n{title.center(80)}\n{'═' * 80}{Style.RESET}", 2),
        "single": (f"{Style.CYAN}{'─' * 60}\n{title}\n{'─' * 60}{Style.RESET}", 1),
        "box": (f"{Style.BOLD}┌{'─' * 58}┐\n│ {title:<56} │\n└{'─' * 58}┘{Style.RESET}", 1)
    }
    border, spacing = styles.get(style, styles["single"])
    print(f"\n{border}\n" + "\n" * spacing)

def print_test(name: str, status: str = "running"):
    """Print test status with visual indicators."""
    icons = {"running": "🔄", "pass": "✅", "fail": "❌", "skip": "⏭️", "warn": "⚠️"}
    colors = {"running": Style.CYAN, "pass": Style.GREEN, "fail": Style.RED, "skip": Style.YELLOW, "warn": Style.YELLOW}
    color = colors.get(status, Style.RESET)
    icon = icons.get(status, "•")
    print(f"{color}{icon} {name:<50} [{status.upper()}]{Style.RESET}")

def print_chat(role: str, content: str, **meta):
    """Print chat messages with role-based styling."""
    styles = {
        "user": (Style.GREEN, "👤"), "assistant": (Style.PURPLE, "🤖"), 
        "system": (Style.YELLOW, "⚙️"), "tool": (Style.CYAN, "🔧")
    }
    color, icon = styles.get(role.lower(), (Style.RESET, "•"))
    extras = f" [{meta.get('model', '')}]" if meta.get('model') else ""
    if meta.get('images'): extras += f" 🖼️×{meta['images']}"
    print(f"{color}{icon} {role.title()}:{Style.RESET} {content}{extras}")

def separator(char: str = "─", length: int = 60):
    """Print visual separator."""
    print(f"{Style.CYAN}{char * length}{Style.RESET}")

# ═══════════════════════════════════════════════════════════════════════════════
# 🖼️ IMAGE PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════

def choose_random_image(resize: bool = True, target_size: Tuple[int, int] = (400, 268)) -> Optional[str]:
    """
    Randomly select and optionally resize an image from the images directory.
    
    Args:
        resize: Whether to resize the image
        target_size: Target dimensions (width, height)
        
    Returns:
        Base64 encoded image or None if no images found
    """
    if not HAS_PIL:
        print_test("PIL/Pillow not installed", "warn")
        return None
    
    images_dir = Path(__file__).parent / 'images'
    valid_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    image_files = [f for f in images_dir.glob('*') if f.suffix.lower() in valid_exts]
    
    if not image_files:
        print_test(f"No images found in {images_dir}", "warn")
        return None
    
    selected = random.choice(image_files)
    print_test(f"Selected: {selected.name}", "pass")
    
    if resize:
        return encode_image_to_base64(selected, target_size)
    else:
        return encode_image_to_base64(selected, None)

def resize_image(path: Union[str, Path], target_size: Tuple[int, int]) -> Optional[Image.Image]:
    """Resize image preserving aspect ratio and transparency."""
    if not HAS_PIL: return None
    try:
        img = Image.open(path)
        if img.width <= target_size[0] and img.height <= target_size[1]:
            return img
        
        ratio = min(target_size[0] / img.width, target_size[1] / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        
        # FIXED: Preserve transparency during resize
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            # Use LANCZOS for better quality with transparency
            resized = img.resize(new_size, Image.LANCZOS)
        else:
            resized = img.resize(new_size, Image.LANCZOS)
        
        return resized
    except Exception as e:
        print_test(f"Resize failed: {e}", "fail")
        return None

def encode_image_to_base64(path: Union[str, Path], max_size: Optional[Tuple[int, int]] = (400, 268)) -> Optional[str]:
    """Encode image to base64 with optional resizing."""
    if not HAS_PIL: return None
    try:
        img = resize_image(path, max_size) if max_size else Image.open(path)
        if not img: return None
        
        buffer = io.BytesIO()
        
        # FIXED: Handle RGBA images properly
        original_format = getattr(img, "format", None)
        
        # If image has transparency (RGBA or LA mode), preserve as PNG
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img_format = "PNG"
            save_kwargs = {}
        else:
            # For images without transparency, use original format or default to JPEG
            img_format = original_format if original_format in ['JPEG', 'JPG', 'PNG', 'WebP'] else "JPEG"
            
            # Convert to RGB if saving as JPEG (removes any alpha channel)
            if img_format == "JPEG" and img.mode != 'RGB':
                if img.mode == 'RGBA':
                    # Create white background for transparent areas
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
                    img = background
                else:
                    img = img.convert('RGB')
            
            save_kwargs = {"quality": 85} if img_format == "JPEG" else {}
        
        img.save(buffer, format=img_format, **save_kwargs)
        
        size_kb = len(buffer.getvalue()) / 1024
        print_test(f"Encoded: {size_kb:.1f}KB {img_format}", "pass")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print_test(f"Encoding failed: {e}", "fail")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# ⏱️ PERFORMANCE TIMING
# ═══════════════════════════════════════════════════════════════════════════════

class Timer:
    """Unified sync/async timer with visual output."""
    def __init__(self, description: str = "Operation"):
        self.description = description
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        duration = time.time() - self.start_time
        print_test(f"{self.description}: {duration:.2f}s", "pass")
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, *args):
        duration = time.time() - self.start_time
        print_test(f"{self.description}: {duration:.2f}s", "pass")

def run_async(coro):
    """Run async function in sync context."""
    return asyncio.run(coro)