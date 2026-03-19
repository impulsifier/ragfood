import os
import json
from dotenv import load_dotenv
from upstash_vector import Index
from groq import Groq, APIError, AuthenticationError, RateLimitError

# Load environment variables from .env
load_dotenv()

# Validate required credentials at startup
for _var in ["UPSTASH_VECTOR_REST_URL", "UPSTASH_VECTOR_REST_TOKEN", "GROQ_API_KEY"]:
    if not os.environ.get(_var):
        raise EnvironmentError(f"Missing required environment variable: {_var}")

# Constants
JSON_FILE = "foods.json"
LLM_MODEL = "llama-3.1-8b-instant"
TOP_K = 3

# Clients
vector_index = Index(
    url=os.environ["UPSTASH_VECTOR_REST_URL"],
    token=os.environ["UPSTASH_VECTOR_REST_TOKEN"],
)
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

# Load data
with open(JSON_FILE, "r", encoding="utf-8") as f:
    food_data = json.load(f)

# Build enriched text for a food item
def build_enriched_text(item):
    text = item["text"]
    if "region" in item:
        text += f" This food is popular in {item['region']}."
    if "type" in item:
        text += f" It is a type of {item['type']}."
    return text

# Upsert all food items (idempotent overwrite)
print(f"📦 Upserting {len(food_data)} documents to Upstash Vector...")
vector_index.upsert(
    [
        (
            item["id"],
            build_enriched_text(item),
            {
                "text": item["text"],
                "region": item.get("region", ""),
                "type": item.get("type", ""),
            },
        )
        for item in food_data
    ]
)
print("✅ Documents indexed in Upstash Vector.")

# RAG query
def rag_query(question):
    # Step 1: Query Upstash Vector with raw question text (embedding done server-side)
    results = vector_index.query(data=question, top_k=TOP_K, include_metadata=True)

    # Step 2: Extract documents from results
    top_docs = [r.metadata["text"] for r in results]
    top_ids = [r.id for r in results]

    # Step 3: Show friendly explanation of retrieved documents
    print("\n🧠 Retrieving relevant information to reason through your question...\n")

    for i, doc in enumerate(top_docs):
        print(f"🔹 Source {i + 1} (ID: {top_ids[i]}):")
        print(f"    \"{doc}\"\n")

    print("📚 These seem to be the most relevant pieces of information to answer your question.\n")

    # Step 4: Build prompt from context
    context = "\n".join(top_docs)

    prompt = f"""Use the following context to answer the question.

Context:
{context}

Question: {question}
Answer:"""

    # Step 5: Generate answer with Groq
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=LLM_MODEL,
        )
        return chat_completion.choices[0].message.content.strip()
    except AuthenticationError:
        return "❌ Groq authentication failed. Check your GROQ_API_KEY."
    except RateLimitError:
        return "⏳ Groq rate limit reached. Please wait a moment before retrying."
    except APIError as e:
        return f"⚠️ Groq API error: {e}. Please try again shortly."


# Interactive loop
print("\n🧠 RAG is ready. Ask a question (type 'exit' to quit):\n")
while True:
    question = input("You: ")
    if question.lower() in ["exit", "quit"]:
        print("👋 Goodbye!")
        break
    answer = rag_query(question)
    print("🤖:", answer)
