-- attach a DuckDB file as a catalog named annot_aid
-- ATTACH 'data/annot_aid.duckdb' AS annot_aid;

-- Switch to catalog (DuckDB equivalent of database)
USE ANNOT_AID;

-- Create schema in uppercase
CREATE SCHEMA IF NOT EXISTS MAPPING;
USE MAPPING;

-- Create tables with uppercase names & columns
CREATE TABLE IF NOT EXISTS BIOMARKER_AXES_SEL (
    BIOMARKER_ID VARCHAR,
    AXIS VARCHAR,
    AXIS_VALUE VARCHAR,
    USER_ID VARCHAR,
    UPDT_DT_TM TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ACTIVE_IND INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS BIOMARKER_LOINCS_SEL (
    BIOMARKER_ID VARCHAR,
    LOINC_NUM VARCHAR,
    CONFIDENCE INTEGER,
    RATIONALE VARCHAR,
    USER_ID VARCHAR,
    UPDT_DT_TM TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ACTIVE_IND INTEGER DEFAULT 1
);

-- Create BIOMARKERS table from CSV
CREATE OR REPLACE TABLE BIOMARKERS AS
SELECT ROW_NUMBER() OVER () AS BIOMARKER_ID,
       T.*
FROM read_csv_auto('data/biomarkers.csv', HEADER=TRUE, AUTO_DETECT=TRUE) T
;

-- Create LOINC table from CSV
CREATE OR REPLACE TABLE LOINC AS
SELECT T.*, iff(T.CLASSTYPE = 1, 'LAB', 'CLIN') as CLASS_TYPE_DESC
FROM read_csv_auto('data/loinc.csv', HEADER=TRUE, AUTO_DETECT=TRUE) T
where T.CLASSTYPE in (1,2);

create or replace table USERS as
select '1' as USER_ID, 'mrkfw' as USER_NAME
union all
select '2' as USER_ID, 'yjrnk' as USER_NAME;

select *
from LOINC;