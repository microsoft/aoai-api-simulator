import os
import time
from locust import HttpUser, task, constant

api_key = os.getenv("SIMULATOR_API_KEY")


class DocIntelligenceBasic(HttpUser):
    wait_time = constant(1)  # wait 1 second between requests

    @task
    def hello_world(self):
        url = "formrecognizer/documentModels/prebuilt-receipt:analyze?api-version=2023-07-31"
        response = self.client.post(
            url,
            files={"file": open("./tools/test-client/receipt.png", "rb")},
            headers={
                "ocp-apim-subscription-key": api_key,
                "Content-Type": "application/octet-stream",
                "Accept": "application/json",
            },
        )

        if response.status_code != 202:
            raise Exception(f"Expected status code 202, got {response.status_code}")

        location = response.headers["Operation-Location"]
        for _ in range(20):
            response = self.client.get(
                location,
                headers={
                    "ocp-apim-subscription-key": api_key,
                },
                name="doc_intelligence_analyze_result",
            )
            if response.status_code != 200:
                raise Exception("Document analysis failed")

            status = response.json().get("status")
            if status == "succeeded":
                return
            if status != "running":
                raise Exception(f"Document analysis returned status='{status}'")

            time.sleep(5)

        raise Exception("Document analysis took too long")
