import torch
from transformers import AutoModel, AutoTokenizer

model_name = 'aristide'
tokenizer = AutoTokenizer.from_pretrained(model_name)

# Carica il tuo modello SLM preaddestrato da PyTorch
model = AutoModel.from_pretrained(model_name).to('cpu')  # Sostituisci con il tuo dispositivo CPU

# Inizia l'interrogazione automatica di testo
question = "Quale città è capitale dell'Italia?"  # Sostituisci la domanda desiderata
input_data = {"q": question}
output = model(**{tokenizer.encode(" ", return_tensors="pt")})[0]  # Sostituisci le tensori con quelli desiderati per l'interrogazione automatica di testo
print(f"La risposta alla tua domanda è: {output['answer']}")  # Sostituisci la funzione di stampa con quella desiderata per visualizzare il risultato in modo diverso