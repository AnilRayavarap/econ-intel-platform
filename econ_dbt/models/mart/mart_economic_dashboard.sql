-- Mart model — Final table for Tableau dashboard
-- One row per series per date with all metrics

WITH observations AS (
    SELECT * FROM {{ ref('int_yoy_changes') }}
),

series_meta AS (
    SELECT
        series_id,
        series_name,
        frequency,
        units,
        source
    FROM econ.dim_series
),

recession AS (
    SELECT
        observation_date,
        sahm_rule_value,
        recession_signal,
        economic_regime
    FROM {{ ref('int_recession_indicator') }}
),

final AS (
    SELECT
        o.series_id,
        s.series_name,
        s.frequency,
        s.units,
        s.source,
        o.observation_date,
        o.current_value,
        o.value_1yr_ago,
        o.value_1mo_ago,
        o.yoy_change_pct,
        o.mom_change_pct,
        o.rolling_12mo_avg,
        o.rolling_3mo_avg,
        o.obs_year,
        o.obs_month,
        o.obs_quarter,

        -- Recession indicators (only for unemployment series)
        r.sahm_rule_value,
        r.recession_signal,
        r.economic_regime,

        -- Trend direction
        CASE
            WHEN o.mom_change_pct > 0 THEN 'UP'
            WHEN o.mom_change_pct < 0 THEN 'DOWN'
            ELSE 'FLAT'
        END                                      AS trend_direction,

        -- Value status vs rolling average
        CASE
            WHEN o.current_value > o.rolling_12mo_avg * 1.05
            THEN 'ABOVE_AVERAGE'
            WHEN o.current_value < o.rolling_12mo_avg * 0.95
            THEN 'BELOW_AVERAGE'
            ELSE 'NORMAL'
        END                                      AS value_status

    FROM observations o
    LEFT JOIN series_meta s
        ON o.series_id = s.series_id
    LEFT JOIN recession r
        ON o.observation_date = r.observation_date
        AND o.series_id = 'UNRATE'
)

SELECT * FROM final