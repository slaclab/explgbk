__author__ = 'mshankar@slac.stanford.edu'

# Add all your SQL queries (if any) in this file.
QUERY_SELECT_EXPERIMENTS_FOR_INSTRUMENT = """
SELECT
    experiment.id as experiment_id,
    experiment.name as experiment_name
FROM
    regdb.experiment experiment
JOIN 
    regdb.instrument instrument 
ON  experiment.instr_id = instrument.id
    AND instrument.name = %(instrument_name)s
ORDER BY
    experiment_name
;
"""

QUERY_SELECT_ELOG_ENTRIES_FOR_EXPERIMENT = """
SELECT 
 e.insert_time DIV 1000000000 AS insert_time, e.author AS author, e.content AS content, e.content_type AS content_type, run.num AS run_num
FROM       entry e 
INNER JOIN header h ON e.hdr_id = h.id
INNER JOIN regdb.experiment exp ON h.exper_id = exp.id AND exp.name = %(experiment_name)s
LEFT JOIN  run run ON h.run_id = run.id
WHERE exp.name = %(experiment_name)s
ORDER BY insert_time DESC;
"""

# This should mirror the previous query as much as possible.
QUERY_SELECT_ELOG_ENTRY_FOR_EXPERIMENT = QUERY_SELECT_ELOG_ENTRIES_FOR_EXPERIMENT.replace("ORDER BY", " AND e.id = %(entry_id)s ORDER BY")


QUERY_INSERT_NEW_HEADER_WITH_RUN = """
INSERT INTO header (exper_id, run_id, relevance_time) 
     SELECT e.id as experiment_id, r.id as run_id, UNIX_TIMESTAMP()*1000000000 
     FROM run r JOIN regdb.experiment e ON r.exper_id=e.id AND e.name=%(experiment_name)s
     WHERE r.num=%(run_num)s LIMIT 1;
"""

QUERY_INSERT_NEW_HEADER_WITHOUT_RUN = """
INSERT INTO header (exper_id, relevance_time) 
     SELECT e.id as experiment_id, UNIX_TIMESTAMP()*1000000000 
     FROM regdb.experiment e 
     WHERE e.name=%(experiment_name)s  LIMIT 1;
"""

QUERY_INSERT_NEW_ELOG_ENTRY = """
INSERT INTO entry (hdr_id, insert_time, author, content, content_type) 
VALUES 
    (
    %(header_id)s, 
    UNIX_TIMESTAMP()*1000000000, 
    %(author)s, 
    %(content)s, 
    %(content_type)s
    );
"""
