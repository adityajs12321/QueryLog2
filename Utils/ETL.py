from bs4 import BeautifulSoup
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
import json
import os
import xml.etree.ElementTree as ET
import datetime

def ETL_XML(xml_file):
    # Initialize the chat model utilizing the provided API key
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai", api_key=api_key)
    
    # Extract the first event/record to use as a sample for the LLM
    soup = BeautifulSoup(xml_file, "xml")
    events = soup.find_all("Event")
    first_record = str(events[0]) if events else xml_file[:2000]
    
    prompt = f"""
    You are an expert developer.
    I have an XML file containing multiple records like the sample below.
    Please write a Python function named `parse_xml` that takes a single string argument `xml_string`
    and returns a standardized, flat JSON list of dictionaries containing all records.
    Infer the schema dynamically based on the tags and properties in the sample.
    Ensure your response ONLY contains the valid, executable Python code block. Include any necessary imports (like json, datetime, xml.etree.ElementTree) INSIDE the function.
    
    Sample XML Record:
    {first_record}
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # Extract the Python code from the LLM response
    code = response.content.strip()
    if code.startswith("```python"):
        code = code[9:-3]
    elif code.startswith("```"):
        code = code[3:-3]
        
    try:
        # Dynamically execute the generated function and run it on the file
        local_vars = {}
        exec(code, globals(), local_vars)
        if "parse_xml" in local_vars:
            return local_vars["parse_xml"](xml_file)
        else:
            print("LLM did not generate a 'parse_xml' function.")
            return []
    except Exception as e:
        print(f"Failed to execute LLM generated code: {e}")
        return []
    
if __name__ == "__main__":
    with open("/Users/adityajs/Downloads/ad_simulated_events.xml", "r") as f:
        xml_content = f.read()
    json_output = ETL_XML(xml_content)
    print(json.dumps(json_output, indent=2))