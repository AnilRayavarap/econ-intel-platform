-- Staging model — clean raw FRED observations
-- Casts types, renames columns, filters invalid values

WITH source AS (
    SELECT
        series_id,
        observation_date,
        value,
        captured_date,
        captured_ts,
        is_revised,
        quality_flag
    FROM econ.fact_observations
),

cleaned AS (
    SELECT
        series_id,
        observation_date,
        value                                    AS observation_value,
        captured_date,
        captured_ts,
        is_revised,
        quality_flag,
        EXTRACT(YEAR  FROM observation_date)     AS obs_year,
        EXTRACT(MONTH FROM observation_date)     AS obs_month,
        EXTRACT(QUARTER FROM observation_date)   AS obs_quarter
    FROM source
    WHERE value IS NOT NULL
      AND quality_flag = 'PASSED'
)

SELECT * FROM cleaned