-- Intermediate model — Year over Year percentage changes
-- Uses window functions to compare current vs same period last year

WITH staged AS (
    SELECT * FROM {{ ref('stg_fred_observations') }}
),

yoy AS (
    SELECT
        series_id,
        observation_date,
        observation_value                        AS current_value,
        obs_year,
        obs_month,
        obs_quarter,

        -- Previous year value using LAG window function
        LAG(observation_value, 12) OVER (
            PARTITION BY series_id
            ORDER BY observation_date
        )                                        AS value_1yr_ago,

        -- Previous month value
        LAG(observation_value, 1) OVER (
            PARTITION BY series_id
            ORDER BY observation_date
        )                                        AS value_1mo_ago,

        -- 12-month rolling average
        AVG(observation_value) OVER (
            PARTITION BY series_id
            ORDER BY observation_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        )                                        AS rolling_12mo_avg,

        -- 3-month rolling average
        AVG(observation_value) OVER (
            PARTITION BY series_id
            ORDER BY observation_date
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        )                                        AS rolling_3mo_avg

    FROM staged
),

final AS (
    SELECT
        series_id,
        observation_date,
        current_value,
        value_1yr_ago,
        value_1mo_ago,
        rolling_12mo_avg,
        rolling_3mo_avg,
        obs_year,
        obs_month,
        obs_quarter,

        -- Year over year change
        CASE
            WHEN value_1yr_ago IS NOT NULL
             AND value_1yr_ago != 0
            THEN ROUND(
                ((current_value - value_1yr_ago)
                / value_1yr_ago * 100)::NUMERIC, 2)
            ELSE NULL
        END                                      AS yoy_change_pct,

        -- Month over month change
        CASE
            WHEN value_1mo_ago IS NOT NULL
             AND value_1mo_ago != 0
            THEN ROUND(
                ((current_value - value_1mo_ago)
                / value_1mo_ago * 100)::NUMERIC, 2)
            ELSE NULL
        END                                      AS mom_change_pct

    FROM yoy
)

SELECT * FROM final