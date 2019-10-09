

This package is a collection of Python code snippets that are maybe worth 
recycling / reusing.


install
====

```bash
pip install git+https://github.com/dustinlennon/pytrope.git
```

pytrope.matplotlib_extras
====

[Introduction to pytrope.matplotlib_extras](https://dlennon.org/notebook/20191007_pytrope)


### jitter

Add an absolute or relative jitter to a series.


### ClippedLocator, ClippedFormatter

Retool the standard matplotlib locator and formatter objects to handle clipped data on 
the axes.


### adjust_colorbar

Adjust a colorbar's height to match the adjacent axes


### add_caption

Add a caption below the axes; automatically handle the breaking up of the
text into lines / pieces less wide than the axes width.


pytrope.psycopg2_extras
====


[Introduction to pytrope.psycopg2_extras](https://dlennon.org/notebook/20191009_pytrope)

### class DatabaseManager

The DatabaseManager class encapsulates a generic "dbexecute" method intended to return a 
collection of records as a pandas.DataFrame.  There is also a "copyto" method to copy a
pandas.DataFrame into a PostgreSQL table (via psycopg2).  If the table exists prior to the
call, it will be replaced.

### class SqlQueryManager

The SqlQueryManager provides a collection of methods to maintain incremental query results
in a simple way.  Each new incremental query added to the object may reference previous 
partial queries through a transparently appended SQL WITH clause.  So it is possible to 
build a complex query through it's constituent parts:

```sql
WITH
rider_date AS (
SELECT
  rider_id, 
  MIN(trip_id) as trip_id,
  trip_date
FROM
  trips
GROUP BY 
  rider_id, trip_date
),
full_date_range AS (
SELECT 
  DATE(generate_series) AS cur_date,
  DATE(generate_series) - INTEGER '14' as pmau_start,
  DATE(generate_series) - INTEGER '8' as pmau_end,
  DATE(generate_series) - INTEGER '7' as mau_start,      
  DATE(generate_series) - INTEGER '1' as mau_end
FROM 
  generate_series('2019-06-01'::timestamp, '2019-08-05'::timestamp, '1 day')
)    
SELECT DISTINCT 
  D.cur_date, 
  R.rider_id
FROM
  full_date_range AS D
CROSS JOIN
  rider_date AS R
WHERE
  D.mau_start <= R.trip_date AND R.trip_date <= D.mau_end
ORDER BY
  cur_date
```

is constructed, in three Python blocks, as:

```python
# define the rider_date partial query
rider_date = """
  SELECT
    rider_id, 
    MIN(trip_id) as trip_id,
    trip_date
  FROM
    trips
  GROUP BY 
    rider_id, trip_date
"""
sqm.set_pq('rider_date', rider_date, order_by = ['rider_id', 'trip_date'])

# define the full_date_range partial query
full_date_range = """
  SELECT 
    DATE(generate_series) AS cur_date,
    DATE(generate_series) - INTEGER '{pmau_start}' as pmau_start,
    DATE(generate_series) - INTEGER '{pmau_end}' as pmau_end,
    DATE(generate_series) - INTEGER '{mau_start}' as mau_start,      
    DATE(generate_series) - INTEGER '{mau_end}' as mau_end
  FROM 
    generate_series('{start_date}'::timestamp, '{end_date}'::timestamp, '1 day')
""".format(**{
  'pmau_start' : 2*period_len,
  'pmau_end': period_len + 1,
  'mau_start' : period_len,
  'mau_end' : 1, 
  'start_date': start_date,
  'end_date' : end_date
})
sqm.set_pq('full_date_range', full_date_range, order_by = ['cur_date']) 

# define the mau_bins partial query
mau_bins = """
  SELECT DISTINCT 
    D.cur_date, 
    R.rider_id
  FROM
    full_date_range AS D
  CROSS JOIN
    rider_date AS R
  WHERE
    D.mau_start <= R.trip_date AND R.trip_date <= D.mau_end
"""
sqm.set_pq('mau_bins', mau_bins, order_by = ['cur_date'], verbose=True)
```

where 'mau_bins' may reference 'full_date_range' and 'rider_date' without 
explicitly defining them in the same block.  This allows query components to 
be described more succinctly and in a less encumbered manner.  Because our
target environment is Jupyter notebook, we use a very simple dependency model.
If a partial query is removed, so too are all subsequent partial queries.  For 
example, in the above, if 'full_date_range' is removed from the SqlQueryManager, 
'mau_bins' will also be removed.