"""Multi-layer file validation for MP3 uploads.

Defense-in-depth approach:
1. Extension check - only .mp3
2. File size check - max 50MB
3. Magic bytes check - must start with MPEG audio frame headers or ID3 tags
4. MIME type check via python-magic
5. Embedded executable scan - check for PE/ELF/script headers in file body
"""
import os
import uuid
import shutil
from typing import Tuple, Optional
from config import MAX_UPLOAD_SIZE_BYTES, UPLOAD_DIR, QUARANTINE_DIR, ALLOWED_EXTENSIONS

# MP3 magic bytes
MP3_MAGIC_BYTES = [
    b'\xff\xfb',  # MPEG Audio Layer 3, no CRC
    b'\xff\xf3',  # MPEG Audio Layer 3, with CRC  
    b'\xff\xf2',  # MPEG Audio Layer 3, variant
    b'\xff\xfa',  # MPEG Audio Layer 3, variant
    b'\xff\xe3',  # MPEG Audio Layer 3, variant
    b'\xff\xe2',  # MPEG Audio Layer 3, variant
    b'ID3',       # ID3v2 tag header (most common for modern MP3s)
]

# Dangerous byte signatures to scan for inside the file
DANGEROUS_SIGNATURES = [
    b'MZ',           # PE (Windows executable)
    b'\x7fELF',     # ELF (Linux executable)
    b'#!',           # Script shebang
    b'PK\x03\x04',  # ZIP archive (could contain malware)
    b'\xca\xfe\xba\xbe',  # Java class / Mach-O fat binary
]


def validate_extension(filename: str) -> Tuple[bool, str]:
    """Check file extension."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid file extension '{ext}'. Only .mp3 files are allowed."
    return True, ""


def validate_file_size(file_size: int) -> Tuple[bool, str]:
    """Check file size."""
    if file_size > MAX_UPLOAD_SIZE_BYTES:
        max_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        return False, f"File too large. Maximum size is {max_mb}MB."
    if file_size == 0:
        return False, "File is empty."
    return True, ""


def validate_magic_bytes(file_data: bytes) -> Tuple[bool, str]:
    """Check that the file starts with valid MP3 magic bytes."""
    for magic in MP3_MAGIC_BYTES:
        if file_data[:len(magic)] == magic:
            return True, ""
    return False, "File does not appear to be a valid MP3 (invalid header bytes)."


def validate_mime_type(file_data: bytes) -> Tuple[bool, str]:
    """Check MIME type using python-magic."""
    try:
        import magic
        mime = magic.from_buffer(file_data[:8192], mime=True)
        valid_mimes = {'audio/mpeg', 'audio/mp3', 'audio/x-mp3', 'audio/x-mpeg'}
        if mime not in valid_mimes:
            return False, f"Invalid file type detected: '{mime}'. Only MP3 audio files are allowed."
        return True, ""
    except ImportError:
        # python-magic not installed, skip this check
        return True, ""
    except Exception as e:
        return False, f"Error validating file type: {str(e)}"


def scan_for_embedded_threats(file_data: bytes) -> Tuple[bool, str]:
    """Scan file body for embedded executable signatures.
    Skips the first 128 bytes (legitimate MP3 header area) and checks
    for dangerous byte patterns that could indicate hidden payloads.
    """
    # Check from byte 128 onward to avoid false positives from MP3 headers
    scan_region = file_data[128:]
    
    for sig in DANGEROUS_SIGNATURES:
        if sig in scan_region:
            return False, f"Suspicious content detected in file (possible embedded payload). Upload rejected."
    return True, ""


def validate_mp3(filename: str, file_data: bytes) -> Tuple[bool, str]:
    """Run all validation checks on an uploaded MP3 file.
    Returns (is_valid, error_message).
    """
    checks = [
        validate_extension(filename),
        validate_file_size(len(file_data)),
        validate_magic_bytes(file_data),
        validate_mime_type(file_data),
        scan_for_embedded_threats(file_data),
    ]
    
    for is_valid, error in checks:
        if not is_valid:
            return False, error
    
    return True, ""


def save_mp3(file_data: bytes, original_filename: str) -> Tuple[Optional[str], str]:
    """Save a validated MP3 file with a UUID filename.
    Returns (saved_path, error_message).
    """
    # Generate safe filename
    file_id = uuid.uuid4().hex
    safe_filename = f"{file_id}.mp3"
    save_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(file_data)
        return save_path, ""
    except Exception as e:
        return None, f"Failed to save file: {str(e)}"


def quarantine_file(file_data: bytes, original_filename: str, reason: str) -> str:
    """Move a suspicious file to quarantine for inspection."""
    file_id = uuid.uuid4().hex
    safe_filename = f"{file_id}_QUARANTINED_{original_filename.replace(os.sep, '_')}"
    quarantine_path = os.path.join(QUARANTINE_DIR, safe_filename)
    
    os.makedirs(QUARANTINE_DIR, exist_ok=True)
    with open(quarantine_path, 'wb') as f:
        f.write(file_data)
    
    # Write reason file
    with open(quarantine_path + ".reason.txt", 'w') as f:
        f.write(f"Original filename: {original_filename}\nReason: {reason}\n")
    
    return quarantine_path
