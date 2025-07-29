from bs4 import BeautifulSoup

def ETL_XML(xml_file):
    events = BeautifulSoup(xml_file, "xml")
    events = events.findAll("Event")
    documents = []
    for event in events:
        document = {}
        document["ProviderName"] = event.find("Provider").get("Name")
        document["EventID"] = int(event.find("EventID").text)
        document["Version"] = int(event.find("Version").text)
        document["Level"] = int(event.find("Level").text)
        document["Task"] = int(event.find("Task").text)
        document["Opcode"] = event.find("Opcode").text
        document["Keywords"] = event.find("Keywords").text
        document["TimeCreated"] = datetime.strptime(event.find("TimeCreated").get("SystemTime"), "%Y-%m-%d %H:%M:%S")
        document["EventRecordID"] = int(event.find("EventRecordID").text)
        document["Channel"] = event.find("Channel").text
        document["Computer"] = event.find("Computer").text
        # document["Security"] = event.find("Security")
        event_data = event.find("EventData")

        if event_data:
            for data_item in event_data.find_all("Data"):
                document[data_item.get("Name")] = data_item.text
        
        documents.append(document)
    return documents