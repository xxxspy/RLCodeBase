import util
from robotNavigation import RobotNavigation
from robotNavigationExp import experiment
import numpy
from nWayCorridor import NWayCorridor

if __name__ == '__main__':
  width = 10
  height = 8
  # the time step that the agent receives the response
  responseTime = 5
  horizon = numpy.inf
  rocks = [(x, height - 1) for x in xrange(width)]

  rewardCandNum = 6
  terminalReward = None
  Domain = NWayCorridor

  experiment(Domain, width, height, responseTime, horizon, rewardCandNum, rocks, terminalReward)