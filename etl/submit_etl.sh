#!/bin/bash
#SBATCH --job-name=gen3_etl
#SBATCH --partition=batch
#SBACTH --output=etl_%j.log
#SBATCH --error=etl_%j.err
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G

# ETL directory
cd ~/gen3-elwazi/etl

# Act venv
source etl_env/bin/activate

# Upload script
python3 -u upload_data.py
