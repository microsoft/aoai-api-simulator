import os

from openai import AzureOpenAI
from flask import Flask, request, render_template

aoai_api_key = os.getenv("TEST_OPENAI_KEY")
if not aoai_api_key:
    raise Exception("TEST_OPENAI_KEY environment variable is required")

aoai_api_endpoint = os.getenv("TEST_OPENAI_ENDPOINT")
if not aoai_api_endpoint:
    raise Exception("TEST_OPENAI_ENDPOINT environment variable is required")

aoai_api_deployment = os.getenv("TEST_OPENAI_DEPLOYMENT")
if not aoai_api_deployment:
    raise Exception("TEST_OPENAI_DEPLOYMENT environment variable is required")

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

    print("Sending request to API...", flush=True)
    aoai_client = AzureOpenAI(
        api_key=aoai_api_key,
        api_version="2023-12-01-preview",
        azure_endpoint=aoai_api_endpoint,
        max_retries=0,
    )

    messages = body["messages"]
    response = aoai_client.chat.completions.create(model=aoai_api_deployment, messages=messages)

    print(response.choices)
    content = response.choices[0].message.content
    role = response.choices[0].message.role
    return {"role": role, "content": content}


if __name__ == "__main__":
    app.run()
