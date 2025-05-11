# create_vectorstore_docs.py
import os
import logging
import shutil
import time
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader, # Per leggere PDF
    DirectoryLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings # Importante!
import ollama # Per il check

# --- Configurazione ---
# Directory che contiene i .txt pre-processati e potenzialmente i PDF
DATA_DIR_TXT = "data"
# Directory che contiene i PDF originali (se non li sposti in DATA_DIR_TXT)
DATA_DIR_PDF = "pre_data" # O DATA_DIR_TXT se i PDF sono lì
VECTORSTORE_DIR = "vectorstore_docs"
OLLAMA_MODEL_NAME = os.environ.get("OLLAMA_MODEL_NAME", "qwen2:0.5b") # Usa il tuo modello
OLLAMA_HOST = "http://localhost:11434"
CHROMA_COLLECTION_NAME = "rag_documents_collection"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("create_vectorstore_docs")

# get_ollama_embedding non serve più qui se usiamo OllamaEmbeddings con Chroma

def build_document_vector_store():
    start_time = time.time()
    vector_store_path = os.path.abspath(VECTORSTORE_DIR)

    logger.info(f"Verifica connessione a Ollama ({OLLAMA_HOST})...")
    try:
        ollama.Client(host=OLLAMA_HOST).list()
        logger.info("Connessione a Ollama riuscita.")
    except Exception as e:
        logger.error(f"CRITICO: Impossibile connettersi a Ollama: {e}. Interruzione.")
        return False

    if os.path.exists(vector_store_path):
        logger.warning(f"Rimozione vector store esistente in {vector_store_path}.")
        try:
            shutil.rmtree(vector_store_path)
        except OSError as e:
            logger.error(f"Errore rimozione {vector_store_path}: {e}. Interruzione.")
            return False

    documents = []
    # Carica .TXT dalla directory 'data' (pre-processati)
    logger.info(f"Caricamento file .txt da '{DATA_DIR_TXT}'...")
    if os.path.exists(DATA_DIR_TXT):
        loader_txt = DirectoryLoader(DATA_DIR_TXT, glob="**/*.txt", loader_cls=TextLoader, show_progress=True, use_multithreading=True, silent_errors=True)
        documents.extend(loader_txt.load())
    else:
        logger.warning(f"Directory '{DATA_DIR_TXT}' non trovata per i file .txt.")

    # Carica .PDF dalla directory specificata (es. 'pre_data' o 'data')
    logger.info(f"Caricamento file .pdf da '{DATA_DIR_PDF}'...")
    if os.path.exists(DATA_DIR_PDF):
        loader_pdf = DirectoryLoader(DATA_DIR_PDF, glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=True, use_multithreading=True, silent_errors=True)
        documents.extend(loader_pdf.load())
    else:
        logger.warning(f"Directory '{DATA_DIR_PDF}' non trovata per i file .pdf.")


    if not documents:
        logger.error("Nessun documento (.txt o .pdf) caricato. Impossibile creare il vector store.")
        return False
    logger.info(f"Caricati {len(documents)} documenti totali.")

    logger.info("Divisione documenti in chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=750, chunk_overlap=150) # Chunk più piccoli per modelli piccoli
    chunks = text_splitter.split_documents(documents)
    logger.info(f"Documenti divisi in {len(chunks)} chunks.")

    if not chunks:
        logger.error("Nessun chunk generato.")
        return False

    logger.info(f"Creazione embeddings e vector store (Modello: {OLLAMA_MODEL_NAME})...")
    embeddings_start_time = time.time()
    try:
        # Usa OllamaEmbeddings direttamente con Chroma
        embedding_function = OllamaEmbeddings(
            model=OLLAMA_MODEL_NAME,
            base_url=OLLAMA_HOST
        )
        vector_store = Chroma.from_documents(
            documents=chunks, # Passa i chunks direttamente
            embedding=embedding_function, # Lascia che Chroma gestisca gli embedding
            persist_directory=vector_store_path,
            collection_name=CHROMA_COLLECTION_NAME
        )
        # vector_store.persist() # from_documents dovrebbe già persistere se persist_directory è specificato

        embeddings_duration = time.time() - embeddings_start_time
        logger.info(f"Creazione vector store completata in {embeddings_duration:.2f} secondi.")
        total_duration = time.time() - start_time
        logger.info(f"Processo completato in {total_duration:.2f} secondi.")
        return True
    except Exception as e:
        logger.error(f"ERRORE CRITICO durante creazione vector store: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("--- Avvio Script Creazione Vector Store Documenti ---")
    if build_document_vector_store():
        logger.info("--- Script completato con successo ---")
    else:
        logger.error("--- Script terminato con errori ---")