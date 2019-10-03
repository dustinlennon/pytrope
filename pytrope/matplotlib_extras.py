import numpy as np
from numpy.random import Generator, PCG64

import pandas as pd

import matplotlib.ticker as mticker

import datetime


# ----

class ClippedFormatter(mticker.Formatter):
  def __init__(self, clip_range, formatter):
    formatter._usetex = False
    self.formatter = formatter    
    self.clip_range = clip_range
    self.__dict__.update( formatter.__dict__ )
    
  def __call__(self, x, pos=None):
    v = self.formatter(x, pos)
    cl = self.formatter(self.clip_range[0], pos)
    ch = self.formatter(self.clip_range[1], pos)
    if v == cl:
      v = r"$\leq {v}$".format(v=v) 
    elif v == ch:
      v = r"$\geq {v}$".format(v=v) 
    return v
  
  def set_locs(self, locs):
    self.formatter.set_locs(np.unique(np.append(locs, self.clip_range)))
  
  def format_ticks(self, values):
    self.set_locs(values)
    return [self(value, i) for i, value in enumerate(values)]

# ----

class ClippedLocator(mticker.Locator):
  def __init__(self, clip_range, locator):
    self.locator = locator
    self.clip_range = clip_range
    self.__dict__.update( locator.__dict__ )
    
  def __call__(self):
    locs = self.locator()
    return np.unique(np.append(locs, self.clip_range))

# ----

def jitter(s, rng=None, rel_jit = None, abs_jit = None):
  """
  Introduce either a relative or absolute uniform jitter 
  to the series.
  """

  # ensure that we can cast the input to a pandas Series
  s = pd.Series(s)
  
  if rng is None:
    rng = Generator(PCG64())
    
  if rel_jit is None and abs_jit is not None:
    m = -abs_jit / 2.
    M = abs_jit / 2.
  elif rel_jit is not None and abs_jit is None:
    r = s.max() - s.min()
    m = -rel_jit*r/2.
    M = rel_jit*r/2.
  else:
    raise ValueError("specify one of 'ajit' or 'rjit'")
   
  U = rng.uniform(m, M, len(s))
  return s + U

# utility: convert formatted string to date
stod = lambda s: datetime.datetime.strptime(s, "%Y-%m-%d").date()

# ----

def rescale_colorbar(cbar, ax):
  """
  Match the cbar height to that of ax
  """
  bax = ax.get_position().bounds
  bcb = list(cbar.ax.get_position().bounds)
  bcb[1::2] = bax[1::2]
  cbar.ax.set_position(bcb)
