import cohere

# Initialize the Cohere client
api_key = "G9dS2KXTsHkezmYRtvvddiM2zKkY0xDjYZg38cEg"  # Replace with your Cohere API key
co = cohere.Client(api_key)

def parse_command_using_cohere(command):
    try:
        # Using 'command-light' model which works with generate()
        response = co.generate(
            model='command-light',
            prompt=command,
            max_tokens=50,
            temperature=0.5
        )

        return response.generations[0].text.strip()

    except Exception as e:
        return f"❌ Request Failed: {str(e)}"
