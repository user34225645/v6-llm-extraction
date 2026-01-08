# LLM Comparison Study of Brazilian EHR Data Extraction Pipelines

A tool to extract structured medical lab results from PDF documents using AI models (OpenAI or Gemini).

## Overview

This project provides two versions of PDF processing:
- **v1.py**: Direct full-document extraction
- **v6.py**: Segmented extraction with PDF pre-processing (more accurate for multi-page documents)

Both versions extract lab observations, components, reference ranges, and interpretations from medical PDF reports and save them as structured JSON files.

## Requirements

- Python 3.13
- [uv](https://github.com/astral-sh/uv) package manager
- API keys:
  - Google AI Studio API key (for Gemini) - set as `GOOGLE_API_KEY` environment variable
  - OpenAI API key (for OpenAI) - set as `OPENAI_API_KEY` environment variable

## Installation

1. Install dependencies using uv:
```bash
uv sync
```

2. Set up environment variables:
```bash
# For Gemini
export GOOGLE_API_KEY="your-gemini-api-key"

# For OpenAI
export OPENAI_API_KEY="your-openai-api-key"
```

## Usage

### Basic Command Structure

```bash
uv run <script> --model <model_name> --pdf-path <path_to_pdf>
```

### Arguments

- `--model`: (Required) Choose AI model: `openai` or `gemini`
- `--pdf-path`: (Required) Path to the PDF file to process
- `--patient-data`: (Optional) Patient information string
  - Default: `"Idade: 18, Sexo: Masculino, Condições de saúde: N/A"`

### Examples

#### Using v1.py (Direct Extraction)

```bash
# With Gemini
uv run v1.py --model gemini --pdf-path /path/to/lab_results.pdf

# With OpenAI
uv run v1.py --model openai --pdf-path /path/to/lab_results.pdf

# With custom patient data
uv run v1.py --model gemini --pdf-path /path/to/lab_results.pdf --patient-data "Idade: 45, Sexo: Feminino, Condições de saúde: Diabetes"
```

#### Using v6.py (Segmented Extraction)

```bash
# With Gemini
uv run v6.py --model gemini --pdf-path /path/to/lab_results.pdf

# With OpenAI
uv run v6.py --model openai --pdf-path /path/to/lab_results.pdf

# With custom patient data
uv run v6.py --model gemini --pdf-path /path/to/lab_results.pdf --patient-data "Idade: 45, Sexo: Feminino, Condições de saúde: Diabetes"
```

## Output

Results are saved to the `result/` directory in the same location as the scripts.

**Output file**: `result/<pdf_filename>.json`

Example: If you process `lab_exam_2024.pdf`, the output will be saved as `result/lab_exam_2024.json`
