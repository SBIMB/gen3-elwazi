import json
from dictionaryutils import dump_schemas_from_dir

compiled_schema = dump_schemas_from_dir('./my-dictionary')

with open('schema.json', 'w') as f:
   json.dump(compiled_schema,f, indent=2)
print("Dictionary compiled.")
