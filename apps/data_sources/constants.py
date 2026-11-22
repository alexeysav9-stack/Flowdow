"""Centralized limits and configuration for the Data Sources module."""

# Maximum allowed file upload size (20 Megabytes)
MAX_DATA_SOURCE_FILE_SIZE = 20 * 1024 * 1024

# Maximum allowed rows per dataset (DoS prevention)
MAX_DATA_SOURCE_ROWS = 50_000

# Maximum allowed columns per dataset
MAX_DATA_SOURCE_COLUMNS = 200

# Maximum decompression ratio for XLSX OpenXML archive (Zip-bomb defense)
MAX_XLSX_DECOMPRESSION_RATIO = 100.0

# Maximum total uncompressed size for XLSX archive (100 Megabytes)
MAX_XLSX_UNCOMPRESSED_SIZE = 100 * 1024 * 1024

# Allowed file extensions
ALLOWED_DATA_EXTENSIONS = {".csv", ".xlsx"}

# Allowed delimiters for CSV auto-detection
CSV_CANDIDATE_DELIMITERS = [",", ";", "\t", "|"]
