import json
import os
import openai
from dotenv import load_dotenv
from prompt import prompt

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


class OpenAIGenerator:
    """
    GPT3.5 turbo class that uses a prompt to generate a dataset.
    Dataset is then saved in a csv file to be used for fine-tune LLM.
    """

    def __init__(self):
        # Set the API key
        self.prompt = prompt
        self.response = None

    def model(self):
        """
        Generate a response from the prompt.
        """
        self.response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": self.prompt,
                },
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        # say if the response is ready
        print("response ready")

    def generate_csv(self):
        """
        Generate a csv file from the response.
        """
        response = self.response["choices"][0]["message"]["content"]
        try:
            response_to_json = json.loads(response)
            with open("llama.csv", "a", encoding="utf-8") as file:
                # if file is not empty don't write the header
                if os.stat("llama.csv").st_size == 0:
                    file.write("instruction,input,output\n")

                for data in response_to_json:
                    # write the data to the file
                    try:
                        file.write(
                            f"{data['instruction'].replace(',', '')},"
                            f"{data['input'].replace(',', '')},"
                            f"{json.dumps(data['output']).replace(',', ';')}\n"
                        )
                    except KeyError:
                        pass
        except json.decoder.JSONDecodeError:
            print("JSONDecodeError")


if __name__ == "__main__":
    # create a class
    generator = OpenAIGenerator()
    # get the model
    for i in range(3):
        print(f"iteration {i}")
        generator.model()
        generator.generate_csv()
