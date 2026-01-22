# 🔄 Converter Bot for Telegram

A powerful, optimized Telegram bot for converting files between multiple formats. Runs locally in Docker with minimal resource usage.

## ✨ Features

- **Multiple Format Support**: Documents, images, video, audio, 3D models, e-books, and data files
- **Works Everywhere**: Telegram Web, Desktop, and Mobile
- **Multiple Files**: Convert multiple files at once (same format)
- **Conversion History**: Track and recover previous conversions
- **Fast Local Processing**: All conversions happen locally
- **Docker Optimized**: Runs in a lightweight container
- **User-Friendly UI**: Intuitive inline keyboard buttons

## 📁 Supported Formats

| Category      | Input Formats                             | Output Formats                                 |
| ------------- | ----------------------------------------- | ---------------------------------------------- |
| **Documents** | CSV, PDF, DOCX, XML, JSON, YAML, MD, TXT  | CSV, PDF, DOCX, XML, JSON, YAML, MD, TXT, HTML |
| **E-Books**   | FB2, EPUB, MOBI                           | FB2, EPUB, MOBI, PDF, TXT                      |
| **Images**    | GIF, SVG, ICO, PNG, JPEG, WEBP, BMP, TIFF | GIF, SVG, ICO, PNG, JPEG, WEBP, BMP, TIFF, PDF |
| **Video**     | WEBM, MP4, AVI, MKV, MOV, FLV             | WEBM, MP4, AVI, MKV, GIF, MP3                  |
| **Audio**     | MP3, WAV, OGG, FLAC, AAC, M4A             | MP3, WAV, OGG, FLAC, AAC                       |
| **3D Models** | OBJ, FBX, GLB, GLTF, STL, DAE             | OBJ, GLB, GLTF, STL                            |
| **Data**      | ETS, XLSX, XLS                            | XLSX, CSV, JSON, XML, PDF                      |

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Telegram Bot Token (you already have it!)

### Installation

1. **Clone/Download the project**:

   ```bash
   cd E:\Converter_bot
   ```

2. **Configure environment** (optional - defaults are set):

   ```bash
   # Edit .env if you want to change settings
   notepad .env
   ```

3. **Build and run with Docker**:

   ```bash
   docker-compose up -d --build
   ```

4. **Check logs**:
   ```bash
   docker-compose logs -f
   ```

### Bot Information

- **Bot Username**: @convertationsbot
- **Bot ID**: 8575519773

## 📱 Usage

1. **Start the bot**: Send `/start` to @convertationsbot
2. **Send a file**: Upload any supported file
3. **Select format**: Choose target format from the menu
4. **Download**: Get your converted file

### Commands

| Command         | Description              |
| --------------- | ------------------------ |
| `/start`        | Start the bot            |
| `/help`         | Show help guide          |
| `/convert`      | Start conversion mode    |
| `/history`      | View conversion history  |
| `/recover <id>` | Recover previous file    |
| `/settings`     | Bot settings             |
| `/formats`      | Show supported formats   |
| `/stats`        | Your statistics          |
| `/cancel`       | Cancel current operation |

## 🐳 Docker Commands

```bash
# Start the bot
docker-compose up -d

# Stop the bot
docker-compose down

# View logs
docker-compose logs -f converter_bot

# Rebuild after changes
docker-compose up -d --build

# Check status
docker-compose ps

# Restart
docker-compose restart
```

## ⚙️ Configuration

Edit `.env` file to customize:

```env
# Bot Token
BOT_TOKEN=your_token_here

# Log Level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# Max concurrent conversions (default: 3)
MAX_CONCURRENT_CONVERSIONS=3

# External APIs (optional)
CLOUDCONVERT_ENABLED=false
CLOUDCONVERT_API_KEY=
```

## 📊 Resource Usage

The bot is optimized for minimal resource consumption:

- **CPU**: 0.5-2 cores (limited)
- **Memory**: 512MB-2GB (limited)
- **Storage**: Temporary files auto-cleaned

## 🔒 Security

- Runs as non-root user in container
- Read-only filesystem (except temp/data)
- No-new-privileges security option
- Files stored only during conversion
- Auto-cleanup of old files

## 📂 Project Structure

```
Converter_bot/
├── main.py                 # Bot entry point
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose config
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables
├── src/
│   ├── config.py          # Configuration
│   ├── converters/        # Format converters
│   │   ├── base.py        # Base converter class
│   │   ├── document_converter.py
│   │   ├── image_converter.py
│   │   ├── video_converter.py
│   │   ├── audio_converter.py
│   │   ├── model3d_converter.py
│   │   ├── ebook_converter.py
│   │   ├── data_converter.py
│   │   └── converter_factory.py
│   ├── handlers/          # Telegram handlers
│   │   ├── command_handlers.py
│   │   ├── callback_handlers.py
│   │   └── file_handlers.py
│   ├── ui/                # User interface
│   │   ├── keyboards.py   # Inline keyboards
│   │   └── messages.py    # Message templates
│   └── utils/             # Utilities
│       ├── history.py     # History management
│       └── file_manager.py # File handling
├── data/                  # Persistent data
└── temp/                  # Temporary files
```

## 🔧 Development

### Run locally (without Docker)

1. Create virtual environment:

   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Install system dependencies:
   - FFmpeg (for audio/video)
   - Calibre (for e-books)
   - Cairo (for SVG)

4. Run:
   ```bash
   python main.py
   ```

## 📝 Notes

- **File Size Limit**: 50MB via Telegram servers, 2GB with local Bot API
- **History Retention**: 30 days
- **Concurrent Conversions**: 3 (configurable)
- **Temp File Cleanup**: Every 5 minutes, files older than 1 hour

## 🐛 Troubleshooting

### Bot not responding

```bash
# Check if container is running
docker-compose ps

# Check logs for errors
docker-compose logs --tail=100 converter_bot
```

### Conversion fails

- Check if file format is supported
- Verify file isn't corrupted
- Check container logs for specific error

### Out of memory

```bash
# Increase memory limit in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G
```

## 📄 License

MIT License - Feel free to modify and use as needed.

## 🤝 Support

For issues or questions, check the logs or modify the code as needed. The bot is fully self-contained and runs locally on your machine.
