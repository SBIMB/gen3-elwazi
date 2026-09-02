import requests
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from gen3.auth import Gen3Auth
from gen3.metadata import Gen3Metadata
import json

def generate_tags(entry):
    tags = []
    entry_type = entry.get('ENTRYTYPE', '').lower()
    if entry_type == 'article':
        tags.append({"name": "Journal Article", "category": "Publication Type"})
    elif entry_type in ['inproceedings', 'conference']:
        tags.append({"name": "Conference Paper", "category": "Publication Type"})
    elif entry_type:
        tags.append({"name": entry_type.capitalize(), "category": "Publication Type"})

    raw_keywords = [tag.strip() for tag in entry.get('keywords', '').split(',') if tag]

    study_sites = ['agincourt', 'nairobi', 'soweto']
    data_types = ['clinical', 'genomic', 'survey', 'metadata']

    for kw in raw_keywords:
        kw_lower = kw.lower()
        if kw_lower in study_sites:
            tags.append({"name": kw.title(), "category": "Study Site"})
        elif kw_lower in data_types:
            tags.append|({"name": kw.title(), "category": "Data Type"})
        else:
            tags.append({"name": kw.capitalize(), "category": "Research Area"})

    abstract = entry.get('abstract', '').lower()
    if 'agincourt' in abstract and not any(t.get('name') == 'Agincourt' for t in tags):
        tags.append({"name": "Agincourt", "category": "Study Site"})

    return tags

github_bib_url = "https://raw.githubusercontent.com/SBIMB/gen3-elwazi/refs/heads/dev/discovery/journals.bib"
endpoint = "https://gen3-dev.core.wits.ac.za"
auth = Gen3Auth(endpoint, refresh_file="credentials(2).json")
mds = Gen3Metadata(auth_provider=auth)

print("Fetching BibTex from {github_bib_url}...")
response = requests.get(github_bib_url)

if response.status_code != 200:
    print("Failed to fetch. HTTP status: {response.status_code}")
    exit(1)

bib_database = bibtexparser.loads(response.text)
print(f"Successfully loaded {len(bib_database.entries)} papers from Bibtex")

for entry in bib_database.entries:
    guid = entry.get('ID') #This will act as our custom GUID

    metadata_payload = {
        "_guid_type": "discovery_metadata",
        "gen3_discovery": {
            "paper_id": guid,
            "title": entry.get('title', 'Unknown Title'),
            "authors": entry.get('author', 'Unknown Author').replace(' and ', ', '),
            "years": entry.get('year', 'Unknown'),
            "journal": entry.get('journal', 'Unknown Journal'),
            "abstract": entry.get('abstract', 'No abstract available.'),
            "paper_url": entry.get('url') or (f"https://doi.org/{entry.get('doi')}" if entry.get('doi') else ""),
            "tags": generate_tags(entry),
            "authz": ["/programs/MADIVA"] #Hard coded for now
        }
    }

    print(f"Pushing metadata for {guid} to Gen3 MDS...")
    mds.create(guid=guid, metadata=metadata_payload, overwrite=True)

print("BibTeX ETL pipeline complete")