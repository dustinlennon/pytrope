# We work with a local PostgreSQL server configured for SSL connections.  
# Psycopg2 is the typical, low-level connection / cursor library for 
# interfacing python with postgresql.

import pandas as pd
import psycopg2
from psycopg2.sql import SQL, Identifier
import sqlalchemy
import datetime

class DatabaseManager(object):

  def __init__(self, dsn):
    self.dsn = dsn

  @classmethod
  def _createtable_sql(cls, df, table_name):
    """
    Create a dummy connection that constructs a CREATE TABLE SQL 
    statement in accordance with the pandas DataFrame and the given 
    table_name.
    """
    engine = sqlalchemy.create_engine("postgresql+psycopg2://")
    db = pd.io.sql.SQLDatabase(engine)
    table = pd.io.sql.SQLTable(table_name, db, frame=df, index=False, schema='uber')
    sql = table.sql_schema()
    return sql

  def copyto(self, df, table_name):
    """
    copy the given pandas dataframe to the database
    """

    def _gen(cur, _df):
      """
      A helper generator to build the insert query.  This is much faster
      than using the syntactic sugar provided via the sqlalchemy package.
      """
      ss = ",".join(["%s" for _ in range(_df.shape[1])])
      for r in _df.values:
        yield cur.mogrify("({ss})".format(ss=ss),r).decode('ascii')

    with psycopg2.connect(self.dsn) as conn:    
      with conn.cursor() as cur:
        try:
          cur.execute(SQL("DROP TABLE {} CASCADE").format(Identifier(table_name)))
        except psycopg2.errors.UndefinedTable:
          conn.rollback()

        sql = self._createtable_sql(df, table_name)
        cur.execute(sql)

        sql = SQL("INSERT INTO {} VALUES ").format(Identifier(table_name)).as_string(conn) + ",".join( _gen(cur, df) )
        cur.execute(sql)

  def dbexecute(self, sql):
    """
    execute SQL and return the results in a pandas DataFrame
    """
    result = None
    with psycopg2.connect(self.dsn) as conn:
      with conn.cursor() as cur:
        cur.execute(sql)
        if cur.description is None:
          return

        col_names = [c.name for c in cur.description]
        records = []
        for r in cur:
          records.append(r)
        result = pd.DataFrame(records, columns=col_names)      
    return result


# ----

class SqlQueryManager(object):
  def __init__(self, database_manager):
    self._incremental_query_dict = {}
    self._cached_dataframe_dict = {}
    self._query_deps = []
    self.dbm =  database_manager
    
  def __dir__(self):
    """
    Expose cached dataframe keys; for tab completion purposes.
    """
    a = object.__dir__(self) + list( self._cached_dataframe_dict.keys() )
    return sorted(a)
    
  def __getattr__(self, name):
    """
    Enable cached dataframe keys as object attributes
    """
    if name in self._cached_dataframe_dict:
      return self._cached_dataframe_dict[name]
    else:
      raise AttributeError
      
  @property
  def pq(self):
    return self._incremental_query_dict
  
  @property
  def cache(self):
    return self._cached_dataframe_dict
    
  def with_clause(self):
    """
    Create a SQL WITH clause that includes the stored incremental queries.
    """
    if len(self._incremental_query_dict) > 0:
      s = "\n".join([
        "WITH",
        ",\n".join(["{k} AS ({v})".format(k=k, v=v) for k,v in self._incremental_query_dict.items()])
      ])
    else:
      s = ""
    return s

  def _clear_from(self, i):
    """
    Remove queries from index i to end.  This is a trivial way to 
    maintain incremental query dependencies in a jupyter framework.
    """
    for k in self._query_deps[i:]:
      self._incremental_query_dict.pop(k, None)
      self._cached_dataframe_dict.pop(k, None)
    self._query_deps = self._query_deps[:i]
  
  def set_pq(self, key, pq, order_by = [], verbose=False):
    """
    Update incremental query, execute SQL, and save the results to a pandas
    DataFrame
    """
    
    try:
      i = self._query_deps.index(key)
    except ValueError:
      pass
    else:
      self._clear_from(i)
      
    if len(order_by) == 0:
      order_by_clause = ""
    else:
      order_by_clause = "\n".join([
        "ORDER BY",
        ",".join(order_by)
      ])
    
    sql = """
      {with_clause}
      {pq}
      {order_by_clause}
    """.format(**{
      'with_clause' : self.with_clause(), 
      'pq' : pq,
      'order_by_clause' : order_by_clause
    })
    
    if verbose:
      print(sql)
    
    try:
      df = self.dbm.dbexecute(sql)
    except psycopg2.errors.Error as e:      
      print(sql)
      raise(e)
    else:
      self._incremental_query_dict.update({key : pq})
      self._cached_dataframe_dict.update({key : df})
      self._query_deps.append(key)

# ----

if __name__ == '__main__':
  import pandas as pd
  import datetime
  import pytrope.psycopg2_extras as extras

  # For remote work, perhaps: forward postgresql traffic:
  #    ssh -N -o 'ServerAliveInterval 30' deploy@dlennon.org -L 5432:192.168.1.102:5432

  # PostgreSQL connection string
  dsn = r"host=localhost port=5432 dbname=sandbox user=deploy sslmode=require options=-c\ search_path=uber"

  dbm = extras.DatabaseManager(dsn)
  sqm = extras.SqlQueryManager(dbm)

  kw = {
    'header' : 0,
    'names' : ['trip_date', 'rider_id', 'trip_id', 'city_id', 'status'],
    'converters' : {
      'trip_date' : lambda x: datetime.datetime.strptime(x, "%Y-%m-%d").date()
    }
  }

  url = r"https://dlennon.org/assets/data/c3fa25a0181ebf13a301b28154a6c5fb.bz2"
  trips_data = pd.read_csv(url, **kw)

  # Copy the trips_data pandas.DataFrame to a PostgreSQL table, 'trips'
  dbm.copyto(trips_data, 'trips')  

  # Create a partial query, 'rider_date'
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

  # Add the partial query to the SqlQueryManager object
  sqm.set_pq('rider_date', rider_date, order_by = ['rider_id', 'trip_date'])

  # rider_date is available as an attribute of sqm, a pandas.DataFrame
  sqm.rider_date.head()

  # Create a second partial query, 'full_date_range'
  period_len  = 7
  start_date  = datetime.date(2019, 6, 1)
  end_date    = datetime.date(2019, 8, 5)

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

  # 'full_date_range' is available as a component of the SQL WITH clause
  print( sqm.with_clause() )

  # create the pre-aggregated, per-(date,user) 'mau'
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
  sqm.set_pq('mau_bins', mau_bins, order_by = ['cur_date'])

  # Plot of 7-day MAU, "WAU", over time
  sqm.mau_bins.groupby('cur_date').count().plot()
  