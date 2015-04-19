from graphics import *

class Plotting:
  # rgb values of colors
  colorsValues = {'targs': (80, 77, 157), 'obsts': (153, 77, 79), 'segs': (200, 200, 200)}

  def __init__(self, mdp, dim = 800):
    self.mdp = mdp
    self.size = max(mdp.xBoundary[1] - mdp.xBoundary[0], mdp.yBoundary[1] - mdp.yBoundary[0])
    self.radius = mdp.radius / self.size * dim
    self.dim = dim
    # for plot human trajectory, keep the previous state here

    hColorsValues = {label: (r + 40, g + 40, b + 40) for label, (r, g, b) in self.colorsValues.items()}
    # object colors
    self.colors = {label: color_rgb(r, g, b) for label, (r, g, b) in self.colorsValues.items()}
    self.hColors = {label: color_rgb(r, g, b) for label, (r, g, b) in hColorsValues.items()}

    self.prevState = None
    # keep previous highlights here, redraw if un-highlighted
    self.prevHighlight = []

    def shift(loc):
      """
      shift to the scale of the GraphWin
      """
      return (1.0 * (loc[0] - mdp.xBoundary[0]) / self.size * dim, 1.0 * (loc[1] - mdp.yBoundary[0]) / self.size * dim)

    self.shift = shift
 
  def drawDomain(self):
    """
    Args:
      mdp: parsed from mat file.

    Return:
      win object
    """
    self.win = GraphWin('Domain', self.dim, self.dim) # give title and dimensions

    rect = Rectangle(Point(0, 0), Point(self.dim, self.dim))
    rect.setFill('grey')
    rect.draw(self.win)
   
    def drawObjects(label):
      """
      Plot the objects as separate dots.
      """
      for obj in self.mdp.objs[label]:
        # graphically increase the radius
        cir = Circle(Point(self.shift(obj)), self.radius)
        cir.setFill(self.colors[label])
        cir.draw(self.win)

    def drawSegments(label):
      """
      Plot the adjacent objects as segments.
      """
      prevObj = None
      color = self.colors['segs']
      for obj in self.mdp.objs[label]:
        if prevObj:
          # draw segments between waypoints
          line = Line(Point(self.shift(prevObj)), Point(self.shift(obj)))
          line.setWidth(3)
          line.setFill(color)
          line.draw(self.win)

          # draw a small circle at the waypoints
          cir = Circle(Point(self.shift(prevObj)), 5)
          cir.setFill(color)
          cir.draw(self.win)
        prevObj = obj
      
    drawObjects('targs')
    drawObjects('obsts')
    drawSegments('segs')

    return self.win

  def plotHumanPath(self, x):
    # display the corresponding state in graphics
    if self.prevState != None:
      # only draw lines, so ignore the first state
      loc, orient = self.prevState
      newLoc, newOrient = x

      humanColor = color_rgb(0, 255, 0)

      line = Line(Point(self.shift(loc)), Point(self.shift(newLoc)))
      line.setWidth(5)
      line.setFill(humanColor)
      line.draw(self.win)

      cir = Circle(Point(self.shift(newLoc)), 5)
      cir.setFill(humanColor)
      cir.draw(self.win)

    self.prevState = x

  def plotHighlightedObjects(self, l):
    for obj, label in self.prevHighlight:
      # clear previous highlights
      cir = Circle(Point(self.shift(obj)), self.radius)
      cir.setFill(self.colors[label])
      cir.draw(self.win)
    
    for obj, label in l:
      # draw new objects  
      cir = Circle(Point(self.shift(obj)), self.radius)
      cir.setFill(self.hColors[label])
      cir.draw(self.win)

def plotHumanWorldQFuncs(agent, category):
  """
  Print the values of states in heatmap
  """
  import matplotlib.pyplot as plt
  import featureExtractors

  distances = featureExtractors.distances[:-1]
  anglesArc = featureExtractors.anglesArc[:-1]
  angles = featureExtractors.angles[:-1]
  
  distances.reverse() # largest distance appears at top

  # here, reset the mapper so we can easily iterate over state, actions
  agent.setMapper(featureExtractors.discreteQTableCompressor)

  for act in ['L', 'R', 'SL', 'SR', 'G']:
    data = []
    for distance in distances:
      row = []
      for angle in anglesArc:
        row.append(agent.getQValue((distance, angle), act))
      data.append(row)

    plt.imshow(data, interpolation='none')
    plt.xticks(range(len(angles)), map(str, angles))
    plt.yticks(range(len(distances)), map(str, distances))
    plt.xlabel('Angle');
    plt.ylabel('Distance (meter)');
    plt.title('Q Table of Module ' + category + ', Action ' + act)
    
    plt.jet()
    plt.colorbar()

    plt.savefig(category + 'Q_' + act + '.png')
    plt.close()