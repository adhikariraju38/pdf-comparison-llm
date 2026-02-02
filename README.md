# PDF Comparison Service

A powerful backend system that compares two PDFs using LLM analysis and generates a detailed text-based comparison report showing exactly what changed between documents.

## Features

- **LLM-Powered Analysis**: Uses OpenAI, Anthropic Claude, Google Gemini, or custom LLM endpoints to intelligently detect and explain differences
- **Text-Based Comparison**: Clear side-by-side tables showing SOURCE vs COPY text for each difference
- **Detailed Reasoning**: LLM explains why each difference was identified and categorizes change types
- **Comprehensive Summary**: Provides methodology explanation, similarity scores, and statistics
- **Flexible Configuration**: Fully configurable LLM settings through the UI (provider, model, temperature, etc.)
- **Simple Web UI**: Easy-to-use interface for testing and using the service
- **RESTful API**: Well-documented API endpoints for integration
- **4 LLM Providers**: OpenAI, Anthropic, Google Gemini, and custom endpoints

## Architecture

- **Backend**: Python + FastAPI
- **PDF Processing**: PyMuPDF (text extraction), ReportLab (PDF generation), pdf2image (rendering)
- **LLM Integration**: OpenAI, Anthropic, or custom endpoint support
- **Comparison**: Hybrid text extraction + LLM semantic analysis
- **Frontend**: Vanilla HTML/JavaScript

## Prerequisites

### System Requirements

- Python 3.13+ (or 3.10+)
- poppler-utils (for pdf2image)

### Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install poppler-utils
```

**macOS:**
```bash
brew install poppler
```

## Installation

### 1. Clone or navigate to the repository

```bash
cd PDF_COMPARISON
```

### 2. Create virtual environment using uv

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Python dependencies

```bash
uv pip install -r requirements.txt
```

### 4. Create environment file (optional)

```bash
cp .env.example .env
```

Edit `.env` if you want to customize settings (all settings can also be configured through the UI).

## Usage

### Start the Server

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at:
- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Using the Web UI

1. Open http://localhost:8000 in your browser
2. Upload two PDF files:
   - **Source PDF**: The reference document
   - **Copy PDF**: The document to compare against the source
3. Configure LLM settings:
   - Select provider (OpenAI, Anthropic, or Custom)
   - Enter your API key
   - Select/enter the model name
   - Adjust temperature (0.1 recommended for consistent comparisons)
   - (Optional) Enter custom endpoint if using custom provider
4. Click **Start Comparison**
5. Monitor progress in real-time
6. Download the annotated comparison PDF when complete

### Using the API

#### 1. Start a Comparison

```bash
curl -X POST http://localhost:8000/api/compare \
  -F "source_file=@source.pdf" \
  -F "copy_file=@copy.pdf" \
  -F 'llm_config={"provider":"openai","api_key":"sk-...","model":"gpt-4","temperature":0.1}'
```

Response:
```json
{
  "job_id": "uuid-here",
  "status": "processing",
  "message": "Comparison started"
}
```

#### 2. Check Status

```bash
curl http://localhost:8000/api/status/{job_id}
```

Response:
```json
{
  "job_id": "uuid-here",
  "status": "processing",
  "progress": 45,
  "current_step": "Analyzing page 3 of 10...",
  "error": null
}
```

#### 3. Get Results

```bash
curl http://localhost:8000/api/result/{job_id}
```

#### 4. Download PDF

```bash
curl http://localhost:8000/api/download/{job_id} -o comparison.pdf
```

Or open in browser:
```
http://localhost:8000/api/download/{job_id}
```

## LLM Provider Configuration

### OpenAI

- **Provider**: `openai`
- **Models**: `gpt-4`, `gpt-4-turbo-preview`, `gpt-3.5-turbo`
- **API Key**: Starts with `sk-`
- **Get API Key**: https://platform.openai.com/api-keys

### Anthropic (Claude)

- **Provider**: `anthropic`
- **Models**: `claude-3-opus-20240229`, `claude-3-sonnet-20240229`, `claude-3-haiku-20240307`
- **API Key**: Starts with `sk-ant-`
- **Get API Key**: https://console.anthropic.com/

### Google Gemini

- **Provider**: `gemini`
- **Models**: `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-pro`
- **API Key**: Starts with `AIza`
- **Get API Key**: https://aistudio.google.com/app/apikey
- **Note**: Free tier has strict rate limits. For production use, upgrade to a paid plan at https://console.cloud.google.com/. The system includes retry logic with exponential backoff for rate limit errors.

### Custom Provider

- **Provider**: `custom`
- **Endpoint**: Your custom API endpoint URL
- **Model**: Your model identifier
- **API Key**: Your custom API key
- **Format**: Must accept OpenAI-compatible message format

## Project Structure

```
PDF_COMPARISON/
├── app/
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Configuration management
│   ├── models/
│   │   └── schemas.py             # Pydantic models
│   ├── services/
│   │   ├── pdf_extractor.py       # PDF text extraction
│   │   ├── llm_service.py         # LLM provider abstraction
│   │   ├── comparison_engine.py   # Core comparison logic
│   │   └── pdf_generator.py       # Output PDF generation
│   ├── utils/
│   │   └── annotation.py          # Red box annotations
│   └── api/
│       └── endpoints.py           # API routes
├── static/
│   ├── index.html                 # Web UI
│   └── js/app.js                  # Frontend JavaScript
├── uploads/                        # Temporary uploaded PDFs
├── outputs/                        # Generated comparison PDFs
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/api/compare` | POST | Upload PDFs and start comparison |
| `/api/status/{job_id}` | GET | Get job status |
| `/api/result/{job_id}` | GET | Get comparison results (JSON) |
| `/api/download/{job_id}` | GET | Download comparison PDF |
| `/api/health` | GET | Health check |
| `/docs` | GET | API documentation (Swagger) |

## Configuration

All configuration can be set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE_MB` | 50 | Maximum PDF file size |
| `UPLOAD_DIR` | ./uploads | Directory for uploaded files |
| `OUTPUT_DIR` | ./outputs | Directory for output PDFs |
| `COMPARISON_DPI` | 300 | Resolution for PDF rendering |
| `MAX_PAGES_PER_JOB` | 100 | Maximum pages per comparison |
| `SIMILARITY_THRESHOLD` | 0.85 | Similarity threshold |
| `DEBUG` | False | Enable debug mode |

## Output Format

The generated comparison PDF includes:

1. **Summary Page**:
   - Metadata (date, LLM used, page counts)
   - Statistics (similarity score, differences found)
   - Methodology explanation
   - How to read the report

2. **Page-by-Page Text Comparison**:
   - Each page shows similarity rating and LLM reasoning
   - Differences listed with type (Content Change, Addition, Deletion, Formatting)
   - **Side-by-side text tables** showing:
     - **SOURCE** column: What was in the original document
     - **COPY** column: What appears in the compared document
   - LLM reasoning for each difference
   - Color-coded backgrounds (yellow for source, blue for copy)
   - No visual annotations - pure text-based comparison

## Troubleshooting

### Common Issues

**1. "poppler-utils not found"**
```bash
# Install poppler-utils (see Prerequisites section)
sudo apt-get install poppler-utils
```

**2. "Failed to build pydantic-core"**
- Make sure you're using Python 3.10+ or update package versions

**3. "LLM API error"**
- Verify your API key is correct
- Check API key has sufficient credits/quota
- Ensure you're using the correct model name

**4. "Job failed: timeout"**
- Large PDFs may take longer - check logs for specific error
- Consider reducing DPI setting in configuration

**5. "Gemini quota exceeded" (Error 429)**
- Free tier has very limited quotas (RPM and daily limits)
- **Solution 1**: Upgrade to paid API at https://console.cloud.google.com/
- **Solution 2**: Wait for quota to reset (shown in error message)
- **Solution 3**: Use a different LLM provider (OpenAI or Anthropic)
- The system includes automatic retry logic with exponential backoff
- If all retries fail, comparison continues with fallback analysis

### Logs

Enable debug logging by setting `DEBUG=True` in `.env` or running with:
```bash
DEBUG=True uvicorn app.main:app --reload
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Structure

- **Services**: Independent, reusable business logic
- **API**: Thin layer handling HTTP requests
- **Models**: Pydantic schemas for validation
- **Utils**: Helper functions and utilities

## Security Notes

- API keys are never stored on the server
- API keys should be provided through the UI for each comparison
- For production, consider adding authentication
- Use HTTPS in production environments
- Set appropriate CORS origins in configuration

## Performance

- **Small PDFs (1-10 pages)**: ~10-30 seconds
- **Medium PDFs (10-50 pages)**: ~1-5 minutes
- **Large PDFs (50-100 pages)**: ~5-15 minutes

Performance depends on:
- Number of pages
- LLM response time
- DPI setting
- Amount of text per page

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions, please open an issue on the project repository.

## Acknowledgments

- PyMuPDF for PDF extraction
- ReportLab for PDF generation
- FastAPI for the web framework
- OpenAI and Anthropic for LLM capabilities
