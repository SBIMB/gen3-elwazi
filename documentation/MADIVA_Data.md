# Exploring the MADIVA Data
**NB: This database is strictly access controlled and should only be accessed with adequate permissions.**

The current instance of Gen3 utilises the harmonised dataset from the `Postgres` database, `madiva`. These include the tables `individuals`, `individualsesindicators`, `individualevents` and `ncdindicators`.  


## Database Entries
The nature of filtering that occurred as part of the cleanup process descirbed in the `ETL.md` file, ensured that only IDs that existed in all tables mentioned above were included in the new payloads to be ingested by the system. Taken directly from the database, the queries below reflect the total IDs existing in the `individuals` table and the ones intersecting across all tables in question.

```SQL
madiva=> SELECT COUNT(*) as total_rows, COUNT(DISTINCT individual_id) as unique_patients FROM individuals;
 total_rows | unique_patients 
------------+-----------------
     574598 |          574598
(1 row)

madiva=> SELECT count(*) FROM individuals;
 count  
--------
 574598
(1 row)

madiva=> SELECT COUNT(DISTINCT i.individual_id) as valid_intersected_patients
FROM individuals i
INNER JOIN ncdindicators n ON i.individual_id = n.individual_id
INNER JOIN individualsesindicators ses ON i.individual_id = ses.individual_id;
 valid_intersected_patients 
----------------------------
                      67463
(1 row)
```
This results in the total number of ingested subject records being 67463, as is currently reflected on the website. 

It should also be noted that unfortunately there are a significant number of unrecorded entries across the harmonised data. 
For example, the ingested entries in the Gen3 system for the `ethnicity` variable contain missing values which make up 89% of the total category (i.e., only about 6868 subjects across the 67463 valid entries have a recorded ethnicity).

This was questionable, but confirmed through the database, which showed of the total `individuals`, there were only about 54% of total recorded ethnicity values. 
```SQL
madiva=> SELECT 
    COUNT(*) as total_records,
    COUNT(ethnicity) as records_with_ethnicity,
    (COUNT(*) - COUNT(ethnicity)) as missing_ethnicity
FROM individuals;
 total_records | records_with_ethnicity | missing_ethnicity 
---------------+-----------------------+-------------------
        574598 |                 265401 |            309197
(1 row) 
```

## Quality Control
Upon the ingestion of the curated payloads, some entries were flagged and rejected by the system.
These included discrepancies in both the recorded values and variable names. 

Some entries were manually adjusted, while one other record `3months` for `tobac_age_stp` was removed from the  `ncd_lifestyle` node entirely, as it involved an upheaval of the corresponding data dictionary entry.

Additionally, through further inspection of the data, there are approximately 2000 records with extreme physiological values - possibly due to some enum codes and values being recorded incorrectly, or downstream errors in calculations, such as for `bmi`. These records have **not** been removed from the system, to allow for understanding the scope of the data.
