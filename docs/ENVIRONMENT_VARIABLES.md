# Environment Variables

## Logging Configuration

The Lifeboard application supports centralized logging configuration through environment variables.

### Logging Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | String | `INFO` | Sets the logging level. Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FILE_PATH` | String | `logs/lifeboard.log` | Path to the main log file (relative to project root) |
| `LOG_MAX_FILE_SIZE` | Integer | `10485760` | Maximum log file size in bytes before rotation (default: 10MB) |
| `LOG_BACKUP_COUNT` | Integer | `5` | Number of backup log files to keep during rotation |
| `LOG_CONSOLE_LOGGING` | Boolean | `true` | Enable/disable console output for logs. Set to `false` to disable |
| `LOG_INCLUDE_CORRELATION_IDS` | Boolean | `false` | Enable correlation ID tracking for request tracing |

### Examples

#### Basic Configuration
```bash
# Set debug level logging
export LOG_LEVEL=DEBUG

# Use custom log file location
export LOG_FILE_PATH=logs/app.log
```

#### Production Configuration
```bash
# Warning level logging with file-only output
export LOG_LEVEL=WARNING
export LOG_CONSOLE_LOGGING=false
export LOG_MAX_FILE_SIZE=52428800  # 50MB
export LOG_BACKUP_COUNT=10
```

#### Development with Correlation IDs
```bash
# Enable correlation ID tracking for debugging
export LOG_LEVEL=DEBUG
export LOG_INCLUDE_CORRELATION_IDS=true
```

### Environment File
You can also use a `.env` file in the project root:

```env
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/lifeboard.log
LOG_MAX_FILE_SIZE=10485760
LOG_BACKUP_COUNT=5
LOG_CONSOLE_LOGGING=true
LOG_INCLUDE_CORRELATION_IDS=false
```

### Notes

- Log files are stored in the `/logs` directory by default
- Log rotation occurs automatically when files exceed `LOG_MAX_FILE_SIZE`
- System information is logged during application startup
- All services use the same centralized logging configuration
- Changes to environment variables require application restart to take effect