import numpy as np
import pandas as pd

from numpy.random import Generator, PCG64

import matplotlib.ticker as mticker
import matplotlib.text as mtext

import datetime
import types
import re


# ----

class ClippedFormatter(mticker.Formatter):
  def __init__(self, clip_range, formatter):
    self.formatter = formatter    
    self.clip_range = clip_range
    self.__dict__.update( formatter.__dict__ )
    
  def __call__(self, x, pos=None):
    v = self.formatter(x, pos)
    cl = self.formatter(self.clip_range[0], pos)
    ch = self.formatter(self.clip_range[1], pos)

    v = v.strip("$")
    cl = cl.strip("$")
    ch = ch.strip("$")

    if self._usetex or self._useMathText:
      if v == cl:
        v = r"$\leq {v}$".format(v=v) 
      elif v == ch:
        v = r"$\geq {v}$".format(v=v) 
    else:
      if v == cl:
        v = r"{v}+".format(v=v) 
      elif v == ch:
        v = r"{v}+".format(v=v) 

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

def adjust_colorbar(cbar, ax):
  """
  Match the cbar height to that of ax
  """
  bax = ax.get_position().bounds
  bcb = list(cbar.ax.get_position().bounds)
  bcb[1::2] = bax[1::2]
  cbar.ax.set_position(bcb)

# ----

class MeasurableText(mtext.Text):
  def __init__(self, s, renderer, dpi, **kw):
    textobj = mtext.Text(0, 0, s, **kw)
    self.__dict__.update(textobj.__dict__)
    self.figure = types.SimpleNamespace()
    self.figure.dpi = None
    self._textobj = textobj
    self.r = renderer
    self.dpi = dpi

  def extent_tuple(self):
    extents = self.get_window_extent(self.r, dpi=self.dpi)
    return (extents.width, extents.height)

class MeasurableTextFactory(object):
  def __init__(self, renderer, dpi, **kw):
    self.kw = dict(kw)
    self.r = renderer
    self.dpi = dpi

  def build(self, s):
    return MeasurableText(s, self.r, self.dpi, **self.kw)


def add_caption(txt, ax, **kw):
  """
  Add a caption to the axes, passing kw through to the 
  underlying matplotlib.text.Text object  
  """

  fig = ax.figure
  txt = re.sub(r"\s+", " ", txt).strip()

  # Get the renderer; create the measurable text factory
  r = fig.canvas.get_renderer()
  Factory = MeasurableTextFactory(r, fig.dpi, **kw)

  # preprocess to get partial strings, string widths, and 
  # word-end boundaries
  pstr = []
  swidth = []
  wend = []
  for m in re.finditer(r'\s', txt):
    s = m.start()
    e = m.end()
    p = txt[:s]
    pstr.append(p)
    wend.append(e)
    swidth.append( Factory.build(p).extent_tuple() )

  pstr.append(txt)
  swidth.append( Factory.build(txt).extent_tuple() )
  wend.append( len(txt)+1 )

  # axes bbox values
  w = ax.bbox.width 
  x0 = ax.bbox.xmin
  y1 = ax.get_tightbbox(r).ymin

  # split the text into lines with width no larger than w
  smax = swidth[-1][0]
  bins = np.arange(0, w * np.ceil(smax / w) + 1, step=w)
  groups = np.digitize( [s[0] for s in swidth], bins )

  s = 0
  lines = []
  for g in np.unique(groups):
    e = np.array(wend)[groups == g].max()-1
    lines.append( txt[s:e] )
    s = e + 1

  # get extents of realigned text
  mt = Factory.build( "\n".join(lines) )
  tw, th = mt.extent_tuple()
  if th > y1:
    raise ValueError("text won't fit")

  # convert to appropiate coordinate system (pixels to normalized 
  # coordinates)
  xp = x0
  yp = (y1 - th) / 2
  xn, yn = fig.transFigure.inverted().transform(np.array([xp,yp]))

  # add the caption to the figure
  caption = fig.text(xn, yn, 
    mt.get_text(), 
    ha='left', va='bottom', 
    font_properties=mt.get_font_properties()
  )

  return caption  


# ----

if __name__ == '__main__':
  from matplotlib import cm, pyplot as plt
  import matplotlib.colors as mcolors  
  import matplotlib.text as mtext
  import numpy as np
  import pandas as pd
  import re
  import pytrope.matplotlib_extras as tmpe

  # Read the data
  url = "file:///home/dnlennon/Workspace/Repo/notebooks/20190923_UberII/bar.csv"
  df = pd.read_csv(url)

  # The raw 'x', 'y', and 'color' variables
  vx = df.all_trips
  vy = df.pc_trips
  vcolor = (1 - vy / vx)
  pcolor = 100 * vcolor

  # Default pandas plot
  # plt.rc('text', usetex=False)
  # df.plot.scatter('all_trips', 'pc_trips', vcolor, colormap=cmap)

  # matplotlib settings
  plt.rc("figure", figsize=(8,8))
  plt.rc('font', family = 'sans')

  # Clip x and y values
  clip_range = [0,11]
  cx = np.clip(vx, *clip_range)
  cy = np.clip(vy, *clip_range)

  # [pytrope.matplotlib_extras] Jitter the clipped x and y values
  jcx = tmpe.jitter(cx, abs_jit = 0.75)
  jcy = tmpe.jitter(cy, abs_jit = 0.75)

  # Use a different colormap; define a normalizer for percentages
  # on a [0,100] scale
  cmap  = cm.jet
  norm = mcolors.Normalize(vmin=0, vmax=100)

  # Create a scatter plot with a color index
  fig = plt.figure('main')
  fig.clf()
  ax  = fig.gca()
  scatter_kw = {
    'alpha' : 1,
    'c' : pcolor,
    'cmap' : cmap,
    'norm' : norm,
    'edgecolor' : None,
    's' : 4
  }
  ax.scatter(jcx, jcy, **scatter_kw)

  # labels
  ax.set_title('Visualizing a Filtering Effect')
  ax.set_xlabel('Total trips taken (jittered)')
  ax.set_ylabel('Trips taken in primary city (jittered)')
  ax.set_aspect(1.)

  # add a color bar
  scalar_mappable = cm.ScalarMappable(norm=norm, cmap=cmap)
  cbar = fig.colorbar(scalar_mappable, 
    ax=ax,
    pad=0.02,
    fraction=0.1,
    aspect=30
    )
  cbar.set_label("Percent of trips discarded by a 'primary trip' filter")

  # [pytrope.matplotlib_extras]: rescale the color bar
  tmpe.adjust_colorbar(cbar, ax)

  # annotate tick marks for clipped values
  for axis in [ax.xaxis, ax.yaxis]:
    formatter = axis.get_major_formatter()
    locator   = axis.get_major_locator()

    clipped_formatter = tmpe.ClippedFormatter(clip_range, formatter)
    clipped_locator   = tmpe.ClippedLocator(clip_range, locator)

    axis.set_major_formatter( clipped_formatter  )
    axis.set_major_locator( clipped_locator )

  # [pytrope.matplotlib_extras]: add a caption
  txt = """
    Figure 1: Each point denotes a binomial observation for each rider; a 'success' is
    the number of total trips taken in the primary city.    
  """
  tmpe.add_caption(txt, ax, fontsize=8)
