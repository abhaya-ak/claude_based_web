-- ScamShield QA SQL Integrity Checks
-- Every query must return 0 rows (0 violations)

-- 1. Check for orphaned report indicators (no corresponding scam report)
SELECT id, report_id FROM reports_reportindicator
WHERE report_id NOT IN (SELECT id FROM reports_scamreport);

-- 2. Check for orphaned report evidence (no corresponding scam report)
SELECT id, report_id FROM reports_reportevidence
WHERE report_id NOT IN (SELECT id FROM reports_scamreport);

-- 3. Check for orphaned attempt answers (no corresponding attempt)
SELECT id, attempt_id FROM literacy_attemptanswer
WHERE attempt_id NOT IN (SELECT id FROM literacy_simulatorattempt);

-- 4. Check for orphaned attempt answers (no corresponding scenario)
SELECT id, scenario_id FROM literacy_attemptanswer
WHERE scenario_id NOT IN (SELECT id FROM literacy_simulatorscenario);

-- 5. Check for simulator scenario tactic mismatch (is_scam=false must have tactic=NONE)
SELECT id, is_scam, tactic FROM literacy_simulatorscenario
WHERE (is_scam = FALSE AND tactic <> 'NONE')
   OR (is_scam = TRUE AND tactic = 'NONE');

-- 6. Check for attempt scenario count (must be exactly 5 scenarios)
SELECT id, cardinality(scenario_ids) FROM literacy_simulatorattempt
WHERE cardinality(scenario_ids) <> 5;

-- 7. Check for completed attempts missing score_pct or completed_at
SELECT id, status, score_pct, completed_at FROM literacy_simulatorattempt
WHERE status = 'COMPLETED' AND (score_pct IS NULL OR completed_at IS NULL);

-- 8. Check for scanner config singleton violation
SELECT count(*) FROM scanner_scannerconfig HAVING count(*) > 1;

-- 9. Check for heuristic rules with uppercase patterns or blank patterns
SELECT id, pattern FROM scanner_heuristicrule
WHERE pattern <> LOWER(pattern) OR LENGTH(TRIM(pattern)) = 0;
