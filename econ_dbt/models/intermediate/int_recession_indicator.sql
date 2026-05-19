-- Intermediate model — Sahm Rule Recession Indicator
-- Triggers when 3-month avg unemployment rises 0.5pp above 12-month low

WITH unemployment AS (
    SELECT
        observation_date,
        current_value                            AS unrate,

        -- 3-month rolling average of unemployment
        AVG(current_value) OVER (
            ORDER BY observation_date
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        )                                        AS unrate_3mo_avg,

        -- 12-month minimum (lowest unemployment in past year)
        MIN(current_value) OVER (
            ORDER BY observation_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        )                                        AS unrate_12mo_min

    FROM {{ ref('int_yoy_changes') }}
    WHERE series_id = 'UNRATE'
),

sahm AS (
    SELECT
        observation_date,
        unrate,
        unrate_3mo_avg,
        unrate_12mo_min,

        -- Sahm Rule value = 3mo avg minus 12mo min
        ROUND((unrate_3mo_avg - unrate_12mo_min)::NUMERIC, 2)
                                                 AS sahm_rule_value,

        -- Recession signal triggers at 0.5
        CASE
            WHEN (unrate_3mo_avg - unrate_12mo_min) >= 0.5
            THEN TRUE
            ELSE FALSE
        END                                      AS recession_signal,

        -- Economic regime classification
        CASE
            WHEN (unrate_3mo_avg - unrate_12mo_min) >= 0.5
            THEN 'RECESSION SIGNAL'
            WHEN (unrate_3mo_avg - unrate_12mo_min) >= 0.3
            THEN 'ELEVATED RISK'
            WHEN (unrate_3mo_avg - unrate_12mo_min) >= 0.1
            THEN 'WATCH'
            ELSE 'NORMAL'
        END                                      AS economic_regime

    FROM unemployment
)

SELECT * FROM sahm