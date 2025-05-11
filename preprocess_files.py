# preprocess_files.py
import os
import pandas as pd
import logging
import shutil
from docx import Document as DocxDocument # Per file .doc

INPUT_DIR = "pre_data"
OUTPUT_DIR = "data" # Qui verranno messi i .txt
CLEAN_OUTPUT_DIR_FIRST = True # Imposta a False se vuoi mantenere i file in 'data'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("preprocess_files")

def extract_text_from_docx(docx_path):
    try:
        doc = DocxDocument(docx_path)
        full_text = [para.text for para in doc.paragraphs]
        return '\n'.join(full_text)
    except Exception as e:
        logger.error(f"Errore nell'estrazione testo da {docx_path}: {e}")
        return ""

def convert_files_to_text(input_folder, output_folder, clean_output=False):
    logger.info(f"Avvio pre-processamento da '{input_folder}' a '{output_folder}'")
    if not os.path.isdir(input_folder):
        logger.error(f"'{input_folder}' non trovata.")
        return False

    if clean_output:
        if os.path.exists(output_folder):
            logger.warning(f"Pulizia di '{output_folder}'...")
            shutil.rmtree(output_folder)
        os.makedirs(output_folder, exist_ok=True)
    else:
        os.makedirs(output_folder, exist_ok=True)
    logger.info(f"Directory di output '{output_folder}' assicurata.")

    files_processed = 0
    text_files_created = 0

    for filename in os.listdir(input_folder):
        input_filepath = os.path.join(input_folder, filename)
        if not os.path.isfile(input_filepath):
            continue

        logger.info(f"--- Processando file: {filename} ---")
        output_content = None
        output_filename_base = os.path.splitext(filename)[0]
        target_output_filename = None

        try:
            if filename.lower().endswith('.xlsx'):
                xls = pd.ExcelFile(input_filepath)
                temp_content = f"Fonte_Excel: {filename}\n\n"
                for i, sheet_name in enumerate(xls.sheet_names):
                    df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str).fillna('')
                    separator = '\t'
                    csv_content = df.to_csv(sep=separator, index=False, encoding='utf-8')
                    temp_content += f"--- Foglio: {sheet_name} ---\n{csv_content}\n\n"
                output_content = temp_content.strip()
                target_output_filename = f"{output_filename_base}_excel.txt"

            elif filename.lower().endswith('.docx'):
                doc_text = extract_text_from_docx(input_filepath)
                if doc_text:
                    output_content = f"Fonte_DOCX: {filename}\n\n{doc_text}"
                    target_output_filename = f"{output_filename_base}_docx.txt"

            elif filename.lower().endswith('.csv'):
                df = pd.read_csv(input_filepath, dtype=str, encoding='utf-8', on_bad_lines='skip').fillna('')
                separator = '\t' # Convertiamo CSV in TSV per coerenza, o lo lasciamo così?
                                  # Per ora, lo rendiamo testo semplice.
                # Potresti voler semplicemente copiare il CSV o convertirlo in un formato testuale diverso
                # Qui lo convertiamo in una rappresentazione testuale semplice
                csv_as_text = df.to_string(index=False)
                output_content = f"Fonte_CSV: {filename}\n\n{csv_as_text}"
                target_output_filename = f"{output_filename_base}_csv.txt"

            # PDF non viene convertito in .txt qui, create_vectorstore_docs.py lo gestirà direttamente

            if output_content and target_output_filename:
                output_filepath = os.path.join(output_folder, target_output_filename)
                with open(output_filepath, 'w', encoding='utf-8') as f_out:
                    f_out.write(output_content)
                logger.info(f"    -> Creato/Aggiornato file: {target_output_filename}")
                text_files_created += 1
            elif not filename.lower().endswith('.pdf'): # Ignora PDF per ora, ma logga altri non gestiti
                logger.warning(f"    File '{filename}' non processato (formato non gestito per conversione a TXT o errore).")

            files_processed +=1

        except Exception as e:
            logger.error(f"  ! Errore nell'elaborazione del file '{filename}': {e}")

    logger.info("--- Pre-processamento completato ---")
    logger.info(f"File totali analizzati: {files_processed}")
    logger.info(f"File di testo creati/aggiornati: {text_files_created}")
    return True

if __name__ == "__main__":
    if not os.path.exists(INPUT_DIR):
         logger.warning(f"'{INPUT_DIR}' non esiste. Creala e mettici i file.")
         exit(1)
    convert_files_to_text(INPUT_DIR, OUTPUT_DIR, clean_output=CLEAN_OUTPUT_DIR_FIRST)