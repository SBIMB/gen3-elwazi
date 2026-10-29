#!/bin/bash
#SBATCH --job-name=gen3_delete
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --time=24:00:00
#SBATCH --output=delete_%j.log

echo "Starting automated Gen3 deletion process..."

# Activate your virtual environment
# (Change this to the actual path of your venv folder)
source etl_env/bin/activate

# Run the script using the venv's Python, passing the automated answers
python3 -u delete_data.py <<EOF
all
all
EOF

# Deactivate the venv just to be clean
deactivate

echo "Deletion script completed."