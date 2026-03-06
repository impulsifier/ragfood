# RAG Food System — Ranne Lourd Sanedrin

This project is an enhanced version of the RAG Food System originally developed by Callum James. It uses Retrieval Augmented Generation to answer food related questions by retrieving relevant information from a local food database and generating accurate responses using a large language model. This version adds 15 new food items covering Filipino cuisine, healthy foods, and popular international dishes.

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

## Installation and Setup

Clone the repository and navigate to the project folder. Install Python 3.11.9 as it is the recommended version for compatibility with ChromaDB. Run the dependency installation command and pull the required Ollama models before starting the application.
```
git clone https://github.com/impulsifier/ragfood
cd ragfood
```
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

---

## Personal Reflection

This project provided a comprehensive and hands on introduction to Retrieval Augmented Generation as a practical AI development technique. Before this workshop my understanding of RAG was largely theoretical. Building and testing this system from scratch changed that significantly.

The most valuable technical insight was understanding how vector embeddings work in practice. When a query is entered the system converts it into a numerical vector and finds the most semantically similar vectors in the ChromaDB database. This means a question about protein rich foods can correctly retrieve information about salmon and lentils even if the exact phrase does not appear in those descriptions.

Setting up the environment presented real challenges. Python 3.14 was incompatible with ChromaDB due to Pydantic version conflicts requiring a downgrade to Python 3.11.9. The GitHub MCP server also initially failed because it was configured to use Docker which was not installed.

These troubleshooting experiences were frustrating in the moment but ultimately deepened my understanding of dependency management and environment configuration. Adding the 15 food items also taught me the importance of description quality in RAG systems. The more detailed the text the better the system performs at retrieving relevant results.

The next steps include experimenting with different embedding models to compare retrieval accuracy. Building a RAG system around a different domain such as a business knowledge base is also a priority. This project has given me a strong foundation to continue growing as an AI Builder.

---

Original repository: https://github.com/gocallum/ragfood
```

---

Paste this into your README.md, save, and push with:
```
git add README.md
git commit -m "Update README with enhancements and personal reflection"
git push