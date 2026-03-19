# RAG Food System — Ranne Lourd Sanedrin

This project is an enhanced version of the RAG Food System originally developed by Callum James. It uses Retrieval Augmented Generation to answer food related questions by retrieving relevant information from a local food database and generating accurate responses using a large language model. This version has been migrated to cloud infrastructure using Upstash Vector Database and Groq Cloud API with an enhanced food database of 110 items.

---

## Cloud Migration Overview

This project has been migrated from a local setup to a fully cloud powered system. The local version used ChromaDB for vector storage and Ollama for embeddings and language model inference. The cloud version replaces these with Upstash Vector Database for managed serverless vector storage and Groq Cloud API for fast language model inference using custom LPU hardware. The migration removes all local dependencies meaning the system can run from any machine with just an internet connection and the required API keys.

**Architecture: Local vs Cloud**

| Component | Local Version (v1.0) | Cloud Version (v2.0) |
|---|---|---|
| Vector Database | ChromaDB (local disk) | Upstash Vector (serverless cloud) |
| Embeddings | Ollama mxbai-embed-large | Upstash built-in mxbai-embed-large-v1 |
| Language Model | Ollama llama3.2 (local) | Groq llama-3.1-8b-instant (cloud) |
| Setup required | Install Ollama + pull models | Set environment variables |
| Portability | Machine specific | Run from anywhere |
| Cost | Local compute only | Free tier available |

---

## Repository Structure
```
ragfood
├── cloud-version/     ← Upstash + Groq cloud implementation
├── data/              ← Enhanced food database with 110 items
├── docs/              ← Migration plan and documentation
├── local-version/     ← Original ChromaDB + Ollama implementation
├── rag_run.py         ← Main application file (cloud version)
├── .env               ← Environment variables (not committed)
└── README.md
```

---

## Environment Variables

Create a `.env` file in the project root with the following credentials:
```
UPSTASH_VECTOR_REST_TOKEN="your_token_here"
UPSTASH_VECTOR_REST_URL="your_url_here"
GROQ_API_KEY="your_groq_api_key_here"
```

Never commit your `.env` file to GitHub. It is already listed in `.gitignore`.

---

## Installation and Setup

**Cloud Version (v2.0)**

Clone the repository and navigate to the project folder. Install Python 3.11.9 as it is the recommended version for compatibility. Add your environment variables to the `.env` file before running.
```
git clone https://github.com/impulsifier/ragfood
cd ragfood
```
```
python -m pip install upstash-vector groq python-dotenv
```
```
python rag_run.py
```

**Local Version (v1.0)**

The local version requires Ollama installed and running with the required models pulled.
```
python -m pip install chromadb requests
```
```
ollama pull mxbai-embed-large
ollama pull llama3.2
```
```
python rag_run.py
```

---

## Performance Comparison: Local vs Cloud

| Metric | Local Version (v1.0) | Cloud Version (v2.0) |
|---|---|---|
| Setup time | 15 to 30 minutes | 2 to 5 minutes |
| First query latency | 3 to 8 seconds (CPU dependent) | 1 to 2 seconds (Groq LPU) |
| Embedding generation | Manual via Ollama | Automatic via Upstash |
| Portability | Local machine only | Any machine with API keys |
| Maintenance | Local model management | Managed cloud service |
| Cost | Electricity and hardware | Free tier available |

---

## Food Database

The database has been significantly enhanced from the original with 110 total food items across diverse categories.

**Original items:** 75 items covering basic fruits, vegetables, and international dishes

**Week 1 additions (15 items):**
Filipino cuisine including Adobo, Sinigang, Kare-Kare, Lechon, and Halo-Halo. Healthy foods including Quinoa, Kale, Salmon, Avocado, and Lentils. International dishes including Pad Thai, Paella, Butter Chicken, Tacos, and Croissant.

**Week 3 additions (20 items):**
World cuisines including Tom Yum, Massaman Curry, Hummus, Greek Salad, Shakshuka, Moussaka, Falafel, and Bibimbap. Health conscious options including Chia Seeds, Edamame, Turmeric, and Sweet Potato. Comfort foods including Beef Pho, Mac and Cheese, Ramen, Jollof Rice, Pierogi, Biryani, Goulash, and Brigadeiro.

---

## New Food Items Added

**Filipino Cuisine**

Adobo — The unofficial national dish of the Philippines made with chicken or pork marinated in vinegar, soy sauce, garlic, and bay leaves.

Sinigang — A sour tamarind based soup with pork, shrimp, or fish and fresh vegetables considered the ultimate Filipino comfort food.

Kare-Kare — A rich peanut sauce stew made with oxtail and vegetables traditionally served with fermented shrimp paste.

Lechon — A whole roasted pig slow cooked over charcoal until the skin is golden and crispy served at Filipino celebrations.

Halo-Halo — A colorful Filipino dessert of crushed ice, evaporated milk, sweetened beans, fruits, ube ice cream, and leche flan.

**Healthy Foods**

Quinoa — An ancient grain from South America containing all nine essential amino acids and naturally gluten-free.

Kale — A nutrient dense leafy green rich in vitamins K, A, and C with powerful antioxidants linked to reduced disease risk.

Salmon — A fatty fish rich in omega-3 acids providing 25 grams of protein per 100 grams beneficial for heart and brain health.

Avocado — A creamy fruit from Central America rich in heart healthy monounsaturated fats and essential vitamins.

Lentils — An affordable plant based protein source providing 18 grams of protein per cup and naturally vegan and gluten-free.

**International Dishes**

Pad Thai — A Thai stir fried rice noodle dish with eggs, tofu or shrimp, tamarind sauce, and crushed peanuts.

Paella — A traditional Spanish rice dish from Valencia cooked with saffron, olive oil, and a variety of proteins.

Butter Chicken — A mildly spiced Indian curry with tandoor grilled chicken in a creamy tomato based sauce.

Tacos — A traditional Mexican street food of corn or wheat tortillas filled with grilled meats, salsa, and guacamole.

Croissant — A buttery French pastry made with laminated dough creating hundreds of flaky layers eaten at breakfast.

---

## Sample Queries and Expected Responses

| Query | Expected Response |
|---|---|
| What is Adobo? | Filipino dish marinated in vinegar, soy sauce, garlic, and bay leaves |
| Which foods are high in protein? | Lentils and Salmon |
| Tell me about Filipino foods | Overview of Sinigang, Adobo, and Lechon |
| What vegan options are available? | Lentils, Kale, Avocado |
| What foods can be grilled? | Chicken and grilled meats |
| What is Sinigang? | Sour tamarind based Filipino soup |
| What are healthy gluten free foods? | Lentils, Quinoa, Kale |
| Tell me about Spanish cuisine | Overview of Paella and Spanish food culture |
| What is Halo-Halo? | Filipino dessert with crushed ice and mixed sweet ingredients |
| What international dishes use rice? | Nasi Lemak, Paella, Pad Thai |
| What are some healthy Mediterranean options? | Greek Salad, Hummus, Shakshuka |
| What are high protein low carb foods? | Salmon, Edamame, Lentils |
| Tell me about traditional comfort foods | Mac and Cheese, Ramen, Goulash |
| What foods are high in omega 3? | Salmon, Chia Seeds |
| What foods are gluten free and high in protein? | Lentils, Quinoa, Edamame |

---

## Troubleshooting

**ModuleNotFoundError: No module named upstash_vector**
Run `python -m pip install upstash-vector groq python-dotenv` using Python 3.11.9.

**Missing environment variable error**
Make sure your `.env` file exists in the project root with all three required credentials.

**Python version conflict**
Use Python 3.11.9. Python 3.14 is incompatible with the required packages.

**Groq authentication error**
Check your `GROQ_API_KEY` in the `.env` file and ensure it has not expired.

---

## Personal Reflection

This project provided a comprehensive and hands on introduction to Retrieval Augmented Generation as a practical AI development technique. Before this workshop my understanding of RAG was largely theoretical. Building and testing this system from scratch changed that significantly.

The most valuable technical insight was understanding how vector embeddings work in practice. When a query is entered the system converts it into a numerical vector and finds the most semantically similar vectors in the ChromaDB database. This means a question about protein rich foods can correctly retrieve information about salmon and lentils even if the exact phrase does not appear in those descriptions.

Setting up the environment presented real challenges. Python 3.14 was incompatible with ChromaDB due to Pydantic version conflicts requiring a downgrade to Python 3.11.9. The GitHub MCP server also initially failed because it was configured to use Docker which was not installed.

The most interesting part of testing was pushing the RAG system outside its food domain with random unrelated questions. Asking things like who would win in a fight between a lion and a gorilla and what is the meaning of life produced unexpected food related responses which clearly demonstrated the limitations of RAG systems. This showed that RAG is only as good as the data it is trained on and performs best when queries stay within its knowledge domain.

---

Original repository: https://github.com/gocallum/ragfood
```

---

Replace your entire README.md with this, save with `Ctrl + S` then push:
```
git add README.md
git commit -m "Update README with cloud migration overview and performance comparison"
git push