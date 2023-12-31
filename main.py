import json
import os
import sys
import re
import time
import openai
import pandas as pd
from dotenv import load_dotenv
from src.duplicates_verification import DuplicatesVerification
from src.prompt import Prompt

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


class OpenAIGenerator:
    """
    GPT3.5 turbo class that uses a prompt to generate a dataset.
    Dataset is then saved in a csv file to be used for fine-tune LLM.
    """

    def __init__(self):
        # Set the API key
        with open("dataforge-config.json", "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.prompt = Prompt()
        self.response = None

    def model(self, prompt_content):
        """
        Generate a response from the prompt.
        """
        self.response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "user",
                    "content": prompt_content,
                },
            ],
            temperature=0.5,
            max_tokens=3000,
        )

    def write_csv(self, subject):
        """
        Generate a csv file from the response.
        """
        response = self.response["choices"][0]["message"]["content"]

        try:
            response_to_json = json.loads(response)
            with open(
                    f"src/datasets/generated/llama-{subject}-dataset.csv",
                    "a",
                    encoding="utf-8"
            ) as f:
                # if file is not empty don't write the header
                if os.stat(f"src/datasets/generated/llama-{subject}-dataset.csv").st_size == 0:
                    f.write("instruction;input;output;text\n")

                for data in response_to_json:
                    # write the data to the file
                    try:
                        f.write(
                            f"{data['instruction']};" +
                            f"{data['input']};" +
                            f"{json.dumps(data['output'])}\n"
                        )

                    except KeyError:
                        pass
            f.close()

        except json.decoder.JSONDecodeError as e:
            print("JSONDecodeError")
            print(e)

    def generate_dataset(self, identifier, subject):
        """
        Generate a dataset from the prompt.
        """
        filename = None
        nb_iterations = 0
        # get the model
        print(f"subject: {subject}")

        if identifier == 1:
            nb_iterations = self.config["first-step-iterations"]
            filename = f"src/datasets/manual/manual-questions-{subject}.csv"
        if identifier == 2:
            nb_iterations = self.config["second-step-iterations"]
            filename = f"src/datasets/generated/llama-{subject}-dataset.csv"

        for i in range(nb_iterations):
            print(f"iteration: {i + 1}")
            dyn_prompt = self.prompt.get_prompt(f=filename, subject=subject, identifier=identifier)
            self.model(prompt_content=dyn_prompt)
            self.write_csv(subject=subject)
            print(f"generated {(i + 1) * 5} responses")
            time.sleep(3)

    def merge_input_output(self, dataset):
        """
        Merge input and output columns.
        """
        # merge input and output columns
        dataset['text'] = dataset['input'] + '->: ' + dataset['output']
        return dataset

    def add_manual_questions(self, manual_questions, dataset):
        """
        Add manual questions to the dataset.
        """
        df = pd.read_csv(manual_questions, delimiter=";")

        with open(dataset, "a", encoding="utf-8") as f:
            for i in range(df.shape[0]):
                f.write(
                    "Tu es un analyseur de données charge d'aider les étudiants à trouver des "
                    "ressources répond au mieux en format JSON.;" +
                    f"{df.iloc[i, 1]};" +
                    '{"topic": %s, "subject": %s};\n' % (df.iloc[i, 2], df.iloc[i, 3])
                )
        f.close()

    def combine_datasets(self):
        """
        Combine all datasets into one.
        """
        found = False
        # you should have header like other csv: instruction,input,output only one time
        # create header in the first file
        with open(
                'src/datasets/bigbrain-dataset.csv',
                'w',
                encoding="utf-8"
        ) as f:
            f.write("instruction;input;output;text\n")

        # check any files from any directory
        for _, _, files in os.walk("."):
            for file in files:
                if re.search(r'llama-.*-dataset.csv', file):
                    found = True
                    df = pd.read_csv(f'src/datasets/generated/{file}', delimiter=";")
                    df.to_csv(
                        'src/datasets/bigbrain-dataset.csv',
                        mode='a',
                        header=False,
                        index=False,
                        encoding="utf-8",
                        sep=";"
                    )
                    print(f"Combined {file} into bigbrain-dataset.csv")

        if not found:
            return print("No csv file found")
        return print("Done combining datasets")

    def pipeline(self, execution_list):
        """
        Run the pipeline
        """
        if "--first-generation" in execution_list:
            # First generation of data
            self.generate_dataset(identifier=1, subject=execution_list[
                execution_list.index("--subject") + 1])

            # add manual questions
            for f1, f2 in zip(os.listdir(), os.listdir()):
                if re.search(r'src/datasets/generated/llama-.*-dataset.csv', f1) and re.search(
                        r'src/datasets/manual/manual-questions-.*.csv',
                        f2):
                    self.add_manual_questions(f2, f1)

        if "--second-generation" in execution_list:
            # Second generation of data
            self.generate_dataset(identifier=2, subject=execution_list[
                execution_list.index("--subject") + 1])

        if "--combine" in execution_list:
            # Merge input and output columns
            self.combine_datasets()
            df = pd.read_csv('src/datasets/bigbrain-dataset.csv', delimiter=";")
            df = df.apply(self.merge_input_output, axis=1)
            df.to_csv('src/datasets/bigbrain-dataset.csv', index=False, encoding="utf-8", sep=";")

        if "--no-duplicates" in execution_list:
            # Verify duplicates
            for file in os.listdir():
                if re.search(r'src/datasets/bigbrain-dataset.csv', file):
                    duplicates = DuplicatesVerification(file=file)
                    duplicates.verify_duplicates()


if __name__ == "__main__":
    generator = OpenAIGenerator()
    subject_list = list(generator.config["themes_dict"].keys())

    args = sys.argv[1:]
    list_args = [
        "--first-generation",
        "--second-generation",
        "--combine",
        "--no-duplicates",
        "--subject"
    ]

    if not args or not set(args).issubset(set(list_args + subject_list)) or args == "--help":
        print("Please use: "
              "\n--first-generation to generate a dataset "
              "from manual questions (gathered from students)"
              "\n--second-generation to generate a dataset based on the first generation"
              "\n--combine to combine all datasets into one"
              "\n--no-duplicate to verify duplicates in the csv files"
              "\n--subject <subject> to specify a subject to generate a dataset from")

    if "--first-generation" not in args and "--second-generation" not in args:
        generator.pipeline(execution_list=args)
    else:
        if "--subject" not in args:
            print("Please specify a subject using --subject <subject>")

        else:
            if args[args.index("--subject") + 1] not in subject_list:
                print("Please specify a valid subject")
            else:
                generator.pipeline(execution_list=args)
