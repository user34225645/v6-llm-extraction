import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import List, Literal, Optional

import fitz
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from pydantic import BaseModel, Field


# Set logging level to INFO
logging.basicConfig(level=logging.INFO)


###
# FHIR simplified structure
###
interpretation_choices = Literal["normal", "high", "low", "not_present", "not_interpreted"]


class Component(BaseModel):
    title: str = Field(description="Título do componente")
    value: int | float | str = Field(
        description="Valor do componente como string, caso seja um valor alfanumérico"
    )
    value_unit: str = Field(description="Unidade de medida do valor do componente")
    reference_range_high: Optional[int | float | str] = Field(
        None, description="Valor limite de referência como string, caso seja um valor alfanumérico"
    )
    reference_range_low: Optional[int | float | str] = Field(
        None, description="Valor mínimo de referência como string, caso seja um valor alfanumérico"
    )
    reference_range_qualitative: Optional[str] = Field(
        ...,
        description=(
            "Valor completo do intervalo de referência como string, caso ambos"
            " reference_range_high e reference_range_low sejam null ou seja um valor"
            " alfanumérico como um texto"
        ),
    )
    interpretation: interpretation_choices = Field(
        description=(
            "Se o resultado do componente está ou não no intervalo de refência dada as"
            " informações do paciente contidas nas imagens"
        )
    )
    page_num: int = Field(description="Página em que ele se encontra")


class Observation(BaseModel):
    title: str = Field(description="Título do observation")
    components: List[Component] = Field(description="Lista de componentes do observation")
    method: str = Field(None, description="Método do exame")
    material: str = Field(None, description="Material utilizado no exame")


class Observations(BaseModel):
    observations: List[Observation] = Field(description="Lista de observations")


###
# Prompts
###
with open("prompts/extract_prompt.md", "r", encoding="utf-8") as file:
    extract_prompt = file.read()


###
# Utilities
###
def get_pdf_text(doc: fitz.Document) -> list[str]:
    text = []
    for index, page in enumerate(doc):
        page_info = f"Página {index + 1} de {doc.page_count}\n"
        text.append(page_info + page.get_text())
    return text


###
# Gemini helpers
###
async def extract_full(
    doc_text: list[str], patient_data_text: str, client: genai.Client, model: str = "gemini-2.5-flash"
) -> Observations:
    max_attempts = 3
    cooldown = 3

    full_doc_text = "\n".join(doc_text)

    for attempt in range(1, max_attempts + 1):
        try:
            # The temperature is a function of the attempt number, it starts at 0.0 and increases by 0.375 for each attempt for consistency
            temperature = min(1.5, (attempt - 1) * 0.375)


            logging.info(f"Attempt {attempt} of {max_attempts} with temperature {temperature}")

            response = await client.aio.models.generate_content(
                model=model,
                contents=[
                    extract_prompt,
                    f"<patient_data>{patient_data_text}</patient_data>",
                    f"<full_doc_text>{full_doc_text}</full_doc_text>",
                ],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": Observations,
                    "temperature": temperature,
                    "thinking_config": types.ThinkingConfig(thinking_budget=6144),
                    "max_output_tokens": 6144 + 16384
                },
            )

            if response.parsed is None:
                logging.info(response.text)
                # raise a exception to retry the request
                raise Exception("Can't parse the response, check the logs for more information")
            return response.parsed

        except Exception as e:
            if attempt == max_attempts:
                logging.error(f"Attempt {attempt} of {max_attempts} failed. No more retries.")
            else:
                cooldown = cooldown + 2
                logging.error(f"Attempt {attempt} of {max_attempts} failed: {e}. Retrying in {cooldown} seconds...")
                await asyncio.sleep(cooldown)

###
# OpenAI helpers
###
async def extract_full_openai(
    doc_text: list[str], patient_data_text: str, client: AsyncOpenAI, model: str = "gpt-5-mini") -> Observations:
    full_doc_text = "\n".join(doc_text)
    response = await client.responses.parse(
        model=model,
        instructions=extract_prompt,
        input=f"<patient_data>{patient_data_text}</patient_data>\n<full_doc_text>{full_doc_text}</full_doc_text>",
        text_format=Observations,
        reasoning={"effort": "low"},
    )
    return response.output_parsed


###
# Pipeline
###
async def extract_pipeline(
    doc_path: str, patient_data_text: str, client: genai.Client | AsyncOpenAI, output_dir: Optional[str] = None
) -> Observations:
    """Pipeline that processes a complete PDF."""
    doc = fitz.open(doc_path)
    doc_text = get_pdf_text(doc)

    if isinstance(client, genai.Client):
        observations = await extract_full(doc_text, patient_data_text, client)
    else:
        observations = await extract_full_openai(doc_text, patient_data_text, client)

    # Define the output directory
    if output_dir is None:
        # Save in /result directory relative to this script
        script_dir = Path(__file__).parent
        output_dir = str(script_dir / "result")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    file_name = Path(doc_path).stem
    save_path = os.path.join(output_dir, f"{file_name}.json")

    # Save as json
    with open(save_path, "w", encoding="utf-8") as file:
        file.write(observations.model_dump_json(indent=4, ensure_ascii=False))

    logging.info(f"Saved results to: {save_path}")
    return observations


async def main():
    """Main function to process a single PDF based on CLI arguments."""
    parser = argparse.ArgumentParser(description="Process PDF lab results and extract observations")
    parser.add_argument("--model", type=str, required=True, choices=["openai", "gemini"],
                        help="Model to use for extraction (openai or gemini)")
    parser.add_argument("--pdf-path", type=str, required=True,
                        help="Path to the PDF file to process")
    parser.add_argument("--patient-data", type=str, default="Idade: 18, Sexo: Masculino, Condições de saúde: N/A",
                        help="Patient data text")

    args = parser.parse_args()

    # Validate PDF file exists
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        logging.error(f"PDF file not found: {args.pdf_path}")
        return

    # Initialize the appropriate client
    if args.model == "gemini":
        client = genai.Client()
    else:  # openai
        client = AsyncOpenAI()

    # Process the PDF
    logging.info(f"Processing PDF: {args.pdf_path} with model: {args.model}")
    await extract_pipeline(str(pdf_path), args.patient_data, client)


if __name__ == "__main__":
    asyncio.run(main())