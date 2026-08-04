import yaml
import json 

def auto_generate_mappings_from_schema(schema_path):
    with open(schema_path, 'r') as f:
        schema = yaml.safe_load(f)
        
    auto_mappings = {"nodes": {}}
    
    for node_name, node_details in schema.items():
        if not isinstance(node_details, dict) or 'properties' not in node_details:
            continue
            
        node_maps = {}
        
        for prop_name, prop_details in node_details['properties'].items():
            # 1. Hunt for the enum list (checking both top-level and nested structures)
            enums = []
            if 'enum' in prop_details:
                enums.extend(prop_details['enum'])
            
            for key in ['anyOf', 'oneOf']:
                if key in prop_details and isinstance(prop_details[key], list):
                    for item in prop_details[key]:
                        if isinstance(item, dict) and 'enum' in item:
                            enums.extend(item['enum'])
            
            # 2. If we found enums, extract the leading number
            if enums:
                prop_map = {}
                for valid_enum in enums:
                    parts = valid_enum.split('-', 1)
                    # Maps 333 -> "333-don't know"
                    if len(parts) == 2 and parts[0].isdigit():
                        prop_map[int(parts[0])] = valid_enum
                        
                if prop_map:
                    node_maps[prop_name] = prop_map
                    
        if node_maps:
            auto_mappings["nodes"][node_name] = node_maps
            
    return auto_mappings

if __name__ == "__main__":
    schema_path = "schema.json"
    auto_generate_mappings_from_schema(schema_path)


# 1. Call the function and assign it to a variable
dynamic_mappings = auto_generate_mappings_from_schema(schema_path)

# 2. Add your global missing codes manually (since they aren't in the schema)
dynamic_mappings["global"] = {
    "missing_codes": {
        -333: 333, -444: 444, -777: 777, -888: 888, -999: 999, -111: 111, -222: 222
    }
}

with open("enum_mappings.yaml", "w") as f:
    yaml.dump(dynamic_mappings, f, default_flow_style=False, sort_keys=False)

print("Successfully generated and saved enum_mappings.yaml")