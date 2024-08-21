import os

from openai import AzureOpenAI
from flask import Flask, request, render_template


aoai_api_key = os.getenv("AZURE_OPENAI_KEY")
if not aoai_api_key:
    raise Exception("AZURE_OPENAI_KEY environment variable is required")

aoai_api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
if not aoai_api_endpoint:
    raise Exception("AZURE_OPENAI_ENDPOINT environment variable is required")

aoai_api_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
if not aoai_api_deployment:
    raise Exception("AZURE_OPENAI_DEPLOYMENT environment variable is required")

simulator_api_key = os.getenv("SIMULATOR_API_KEY")
if not simulator_api_key:
    raise Exception("SIMULATOR_API_KEY environment variable is required")

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api", methods=["POST"])
def foo():
    return {"message": "👋 aoai-api-simulator is running"}


@app.route("/api/chat", methods=["POST"])
def api_chat():
    body = request.get_json()
    target_endpoint = body["target_endpoint"]

    if target_endpoint == "live":
        print("Sending request to live API...", flush=True)
        aoai_client = AzureOpenAI(
            api_key=aoai_api_key, api_version="2023-12-01-preview", azure_endpoint=aoai_api_endpoint, max_retries=0
        )
    else:
        print("Sending request to simulated API...", flush=True)
        aoai_client = AzureOpenAI(
            api_key=simulator_api_key,
            api_version="2023-12-01-preview",
            azure_endpoint="http://localhost:8000",
            max_retries=0,
        )

    messages = body["messages"]
    response = aoai_client.chat.completions.create(model=aoai_api_deployment, messages=messages)

    print(response.choices)
    content = response.choices[0].message.content
    role = response.choices[0].message.role
    return {"role": role, "content": content}


if __name__ == "__main__":
    app.run(debug=True)
