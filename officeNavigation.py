import easyDomains
from consQueryAgents import ConsQueryAgent

LOCATION = 0
BOX1 = 1
BOX2 = 2
BOX3 = 3
#DOOR1 = 3
#DOOR2 = 4
SWITCH = 4

OPEN = 1
CLOSED = 0

STEPPED = 1
CLEAN = 0

ON = 1
OFF = 0 

def main():
  # specify the size of the domain, which are the robot's possible locations
  width = 5
  height = 3
  
  # some objects
  box1 = (2, 1)
  box2 = (2, 0)
  box3 = (0, 2)
  #door1 = (1, 1)
  #door2 = (3, 1)
  switch = (4, 2)
  
  # pairs of adjacent locations that are blocked by a wall
  #walls = [[(0, 2), (1, 2)], [(1, 0), (1, 1)], [(2, 0), (2, 1)], [(3, 0), (3, 1)], [(3, 2), (4, 2)]]
  walls = []
  
  # location, box1, box2, door1, door2, carpet, switch
  sSets = [[(x, y) for x in range(width) for y in range(height)],
           [0, 1], [0, 1], [0, 1], #boxes
           #[0, 1], [0, 1], #doors
           [0, 1]] #switch
  
  # the robot can change its locations and manipulate the switch
  cIndices = range(1, SWITCH) # location is not a constraint

  aSets = [(1, 0), (0, 1), #(-1, 0), (0, -1),
           #'openDoor', 'closeDoor',
           'turnOffSwitch']
 
  def move(s, a):  
    loc = s[LOCATION]
    if type(a) == tuple:
      sp = (loc[0] + a[0], loc[1] + a[1])
      if sp[0] >= 0 and sp[0] < width and sp[1] >= 0 and sp[1] < height:
        # so it's not out of the border
        if True: #not (s[DOOR1] == CLOSED and sp == door1 or s[DOOR2] == CLOSED and sp == door2):
          # doors are fine
          blockedByWall = any(loc in wall and sp in wall for wall in walls)
          if not blockedByWall: return sp
    return loc
  
  def stepOnBoxGen(idx, box):
    def stepOnBox(s, a):
      loc = s[LOCATION]
      boxState = s[idx]
      if loc == box: return STEPPED
      else: return boxState
    return stepOnBox
  
  def doorOpGen(idx, door):
    def doorOp(s, a):
      loc = s[LOCATION]
      doorState = s[idx]
      if loc in [(door[0] - 1, door[1]), (door[0], door[1])]:
        if a == 'closeDoor': doorState = CLOSED
        elif a == 'openDoor': doorState = OPEN
        # otherwise the door state is unchanged
      return doorState
    return doorOp
  
  def switchOp(s, a):
    loc = s[LOCATION]
    switchState = s[SWITCH]
    if loc == switch and a == 'turnOffSwitch': switchState = OFF 
    return switchState

  tFunc = [move,
           stepOnBoxGen(BOX1, box1), stepOnBoxGen(BOX2, box2), stepOnBoxGen(BOX3, box3),
           #doorOpGen(DOOR1, door1), doorOpGen(DOOR2, door2),
           switchOp]

  s0 = ((0, 0), # robot's location
        STEPPED, STEPPED, STEPPED,# CLEAN, CLEAN, CLEAN, # boxes are clean
        #OPEN, OPEN, # door 1 is open
        ON) # switch is on
  
  # there is a reward of -1 at any step except when goal is reached
  rFunc = lambda s, a: 10 if s[LOCATION] == switch and  s[SWITCH] == ON and a == 'turnOffSwitch' else -1
  
  gamma = 1

  # the domain handler
  officeNav = easyDomains.getFactoredMDP(sSets, aSets, rFunc, tFunc, s0, gamma)
  
  # sanity checks
  """
  print officeNav['T'](((0, 1), OPEN, CLOSED, ON), 'closeDoor', ((0, 1), CLOSED, CLOSED, ON))
  print officeNav['T'](((2, 1), OPEN, CLOSED, ON), 'openDoor', ((2, 1), OPEN, OPEN, ON))
  print officeNav['T'](((0, 1), OPEN, CLOSED, ON), (1, 0), ((1, 1), OPEN, CLOSED, ON))
  print officeNav['T'](((2, 1), OPEN, OPEN, ON), (1, 0), ((3, 1), OPEN, OPEN, ON))
  print officeNav['T'](((2, 1), OPEN, CLOSED, ON), (1, 0), ((2, 1), OPEN, CLOSED, ON))
  print officeNav['T'](((4, 2), OPEN, CLOSED, ON), 'turnOffSwitch', ((4, 2), OPEN, CLOSED, OFF))
  """

  agent = ConsQueryAgent(officeNav, cIndices)
  print agent.findIrrelevantFeats()

if __name__ == '__main__':
  main()
