# app.py
import os
import logging
import traceback
import json
from flask import Flask, request, jsonify, render_template, send_from_directory # Aggiunto send_from_directory
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
import ollama
import mysql.connector


try:
    from db_config import DB_CONFIG
except ImportError:
    DB_CONFIG = None

# --- Configurazione ---
VECTORSTORE_DOCS_DIR = "vectorstore_docs"
OLLAMA_MODEL_NAME = os.environ.get("OLLAMA_MODEL_NAME", "MariaCarla")
OLLAMA_HOST = "http://localhost:11434"
CHROMA_DOCS_COLLECTION_NAME = "rag_documents_collection"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
vector_store_docs = None
db_connection = None

def get_ollama_completion(prompt_text, system_message=None, temperature=0.3, is_json=False):
    messages = []
    if system_message:
        messages.append({'role': 'system', 'content': system_message})
    messages.append({'role': 'user', 'content': prompt_text})

    try:
        client = ollama.Client(host=OLLAMA_HOST)
        response = client.chat(
            model=OLLAMA_MODEL_NAME,
            messages=messages,
            options={'temperature': temperature},
            format='json' if is_json else ''
        )
        content = response['message']['content']
        if is_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Errore JSON da Ollama: {e}. Raw: {content}")
                raise ValueError(f"Ollama non ha restituito JSON valido: {content}")
        return content
    except Exception as e:
        logger.error(f"Errore Ollama ({OLLAMA_MODEL_NAME}): {e}")
        logger.error(traceback.format_exc())
        raise

def get_db_connection():
    global db_connection
    if db_connection and db_connection.is_connected():
        return db_connection
    if not DB_CONFIG:
        logger.error("db_config.py non trovato o DB_CONFIG non definito.")
        return None
    try:
        logger.info(f"Connessione a MySQL: {DB_CONFIG['host']}/{DB_CONFIG['database']}")
        db_connection = mysql.connector.connect(**DB_CONFIG)
        if db_connection.is_connected():
            logger.info("Connessione MySQL OK.")
            return db_connection
    except mysql.connector.Error as err:
        logger.error(f"Errore connessione MySQL: {err}")
        db_connection = None
    return None

def get_db_schema_string():
    conn = get_db_connection()
    if not conn:
        return "Errore: Impossibile connettersi al database."
    
    schema_info = []
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        if not tables:
            return "Database vuoto o tabelle non trovate."

        schema_info.append("Schema Database:\n")
        for (table_name,) in tables:
            schema_info.append(f"Tabella: {table_name}\nColonne:")
            cursor.execute(f"DESCRIBE `{table_name}`") # Usa backtick per nomi tabelle con caratteri speciali
            columns = cursor.fetchall()
            for col in columns:
                schema_info.append(f"  - {col[0]} ({col[1]})")
            schema_info.append("\n")
        cursor.close()
        return "".join(schema_info)
    except mysql.connector.Error as err:
        logger.error(f"Errore MySQL ottenimento schema: {err}")
        return f"Errore ottenimento schema DB: {err}"

def execute_sql_query(sql_query):
    conn = get_db_connection()
    if not conn:
        return {"error": "Connessione DB non disponibile."}

    results = []
    column_names = []
    try:
        logger.info(f"Esecuzione SQL: {sql_query}")
        # Sanificazione (MINIMA - NON PER PRODUZIONE!)
        if not sql_query.strip().upper().startswith("SELECT"):
            logger.warning(f"Query non-SELECT bloccata: {sql_query}")
            return {"error": "Permesse solo query SELECT."}

        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql_query)
        
        if cursor.description:
            column_names = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()
            logger.info(f"Query OK, {len(results)} righe.")
        else:
            conn.commit() 
            logger.info(f"Query OK (senza risultati, rowcount: {cursor.rowcount}).")
        
        cursor.close()
        return {"columns": column_names, "rows": results, "rowcount": len(results)}
    except mysql.connector.Error as err:
        logger.error(f"Errore MySQL query '{sql_query}': {err}")
        return {"error": f"Errore MySQL: {err}"}
    except Exception as e:
        logger.error(f"Errore imprevisto query '{sql_query}': {e}")
        return {"error": f"Errore imprevisto: {e}"}

def load_document_vector_store():
    global vector_store_docs
    if not os.path.exists(VECTORSTORE_DOCS_DIR):
        logger.error(f"'{VECTORSTORE_DOCS_DIR}' non trovato. Esegui 'create_vectorstore_docs.py'.")
        return
    try:
        embedding_function = OllamaEmbeddings(model=OLLAMA_MODEL_NAME, base_url=OLLAMA_HOST)
        vector_store_docs = Chroma(
            persist_directory=VECTORSTORE_DOCS_DIR,
            embedding_function=embedding_function,
            collection_name=CHROMA_DOCS_COLLECTION_NAME
        )
        logger.info(f"Vector store documenti caricato. Elementi: {vector_store_docs._collection.count()}")
    except Exception as e:
        logger.error(f"Errore caricamento vector store documenti: {e}", exc_info=True)
        vector_store_docs = None

logger.info(f"Avvio App con modello Ollama: {OLLAMA_MODEL_NAME} su {OLLAMA_HOST}")
load_document_vector_store()
get_db_connection()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask_assistant():
    data = request.get_json()
    user_question = data.get('domanda')
    if not user_question:
        return jsonify({"risposta": "Domanda mancante."}), 400

    logger.info(f"Ricevuta domanda: {user_question}")
    response_text = "Non sono riuscito a elaborare la tua richiesta."

    try:
        # Logica di routing (da migliorare con LLM più potente per classificazione)
        keywords_db = ["database", "tabella", "tabelle", "query", "sql", "dati di", "record di", "elenca da"]
        is_db_query = any(keyword in user_question.lower() for keyword in keywords_db)

        if is_db_query:
            logger.info("Rilevata intenzione DB.")
            db_schema = get_db_schema_string()
            if "Errore" in db_schema: # Controlla errori dal DB
                return jsonify({"risposta": db_schema})

            # *** PROMPT SQL GENERATION MODIFICATO (SOLUZIONE 1) ***
            system_sql_gen = f"""Sei un esperto di MySQL. Il tuo compito è generare UNA SOLA query SQL SELECT valida per rispondere alla domanda dell'utente, basandoti sullo schema del database fornito.
IMPORTANTE: La tua risposta DEVE contenere ESCLUSIVAMENTE la query SQL, e nient'altro.
Non includere spiegazioni, commenti, testo introduttivo, tag di pensiero, o qualsiasi altra cosa prima o dopo la query SQL.
Se la domanda non può essere risposta con una singola query SELECT o richiede informazioni non presenti nello schema, la tua risposta DEVE essere ESATTAMENTE la stringa "NON POSSO GENERARE LA QUERY".

Schema Database:
{db_schema}
"""
            prompt_sql_gen = f"Domanda Utente: {user_question}\nQuery SQL:"
            # *** FINE MODIFICA PROMPT ***
            
            logger.info("Invio a LLM per generazione SQL...")
            generated_sql_raw = get_ollama_completion(prompt_sql_gen, system_message=system_sql_gen).strip()
            logger.info(f"SQL grezzo da LLM: '{generated_sql_raw}'")

            # Semplice pulizia di virgolette esterne che a volte i modelli aggiungono
            if generated_sql_raw.startswith('"') and generated_sql_raw.endswith('"'):
                generated_sql = generated_sql_raw[1:-1].strip()
            elif generated_sql_raw.startswith("'") and generated_sql_raw.endswith("'"):
                generated_sql = generated_sql_raw[1:-1].strip()
            else:
                generated_sql = generated_sql_raw

            logger.info(f"SQL pulito per esecuzione: '{generated_sql}'")

            print('-------> ',generated_sql)
            pulisco = generated_sql.split('</think>')
            generated_sql = pulisco[1].replace("\n","")
            if "NON POSSO GENERARE LA QUERY" in generated_sql.upper() or not generated_sql.upper().startswith("SELECT"):
                response_text = f"Non sono riuscito a generare una query SQL valida. (LLM ha detto: '{generated_sql_raw}')"
            else:
                query_results = execute_sql_query(generated_sql)
                if "error" in query_results:
                    response_text = f"Errore esecuzione SQL: {query_results['error']}\nSQL: {generated_sql}"
                elif not query_results.get("rows") and query_results.get("rowcount", 0) == 0 :
                    response_text = f"Query eseguita, nessun risultato.\nSQL: {generated_sql}"
                else:
                    results_for_llm = f"Query SQL Eseguita: {generated_sql}\nRisultati:\n"
                    results_for_llm += "Colonne: " + ", ".join(query_results['columns']) + "\n"
                    for i, row in enumerate(query_results['rows']):
                        results_for_llm += str(row) + "\n"
                    #if len(query_results['rows']) > 10: eliminato per superare le 15 righe
                    #    results_for_llm += f"... e altre {len(query_results['rows']) - 10} righe.\n"
                    print('-------> ',results_for_llm)
                    response_text = results_for_llm
               #     system_report_gen = "Your name is MariaCarla and you convert data from JSON to CSV."
               #     prompt_report_gen = f"""
               #     Convert these data from JSON format to CSV format, use a comma as the separator:
               #     Data:\n{results_for_llm}\n\n """
                    
               #     logger.info("Invio a LLM per generazione report da SQL...")
               #     response_text = get_ollama_completion(prompt_report_gen, system_message=system_report_gen)
        
        elif vector_store_docs:
            logger.info("Tentativo RAG su documenti.")
            embedding_function_docs = OllamaEmbeddings(model=OLLAMA_MODEL_NAME, base_url=OLLAMA_HOST)
            query_embedding = embedding_function_docs.embed_query(user_question)
            
            retrieved_docs = vector_store_docs.similarity_search_by_vector(embedding=query_embedding, k=3)
            if not retrieved_docs:
                context = "Nessuna informazione pertinente trovata nei documenti."
            else:
                context = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])
                sources = list(set(doc.metadata.get('source', 'N/A') for doc in retrieved_docs))
                logger.info(f"Fonti documenti: {sources}")

            system_rag_docs = "Rispondi in italiano basandoti ESCLUSIVAMENTE sul contesto. Se l'info non c'è, dillo."
            prompt_rag_docs = f"Contesto:\n{context}\n\nDomanda: {user_question}\n\nRisposta:"
            logger.info("Invio a LLM per RAG su documenti...")
            response_text = get_ollama_completion(prompt_rag_docs, system_message=system_rag_docs)
        else:
            logger.warning("Né intenzione DB chiara né vector store documenti disponibile.")
            response_text = "Non so se la domanda sia per il DB o i documenti, e il sistema documenti non è pronto."

    except ValueError as ve:
        logger.error(f"Errore valore: {ve}")
        response_text = f"Problema dati AI: {ve}"
    except Exception as e:
        logger.error(f"Errore generale /ask: {e}", exc_info=True)
        response_text = f"Errore interno: {e}"
    #if "<TABELLAHTML>" in response_text:
    #    return response_text
    return jsonify({"risposta": response_text.split('</think>')[1]})#elimina think


@app.route('/favicon.ico')
def favicon():
    # Assicurati di avere un file 'favicon.ico' nella tua cartella 'static'
    # o modifica il percorso se è altrove.
    # Se non hai una cartella static, creala o usa app.root_path
    static_folder = os.path.join(app.root_path, 'static')
    if not os.path.exists(os.path.join(static_folder, 'favicon.ico')):
        # Se non c'è un favicon.ico, potresti voler restituire un 204 No Content
        # per evitare errori 404 ripetuti, o servire un'icona di default se ne hai una.
        logger.warning("favicon.ico non trovato in static/. Restituisco 204.")
        return '', 204
    return send_from_directory(static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)