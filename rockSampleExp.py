import util
from tabularNavigation import TabularNavigation
from tabularNavigationExp import experiment
import getopt
import sys
import tabularNavigationExp
import random

if __name__ == '__main__':
  width = 10
  height = 10
  # the time step that the agent receives the response
  responseTime = 0
  horizon = height + width + 1
  rockType = 'default'
  extra = 0
  
  try:
    opts, args = getopt.getopt(sys.argv[1:], tabularNavigationExp.flags)
  except getopt.GetoptError:
    raise Exception('Unknown flag')
  for opt, arg in opts:
    if opt == '-t':
      rockType = arg
    elif opt == '-r':
      random.seed(int(arg))
  
  Domain = TabularNavigation
  
  def rewardGen(rewards, numerical): 
    def rewardFunc(s, a):
      if s in rewards:
        return numerical
      else:
        return 0
    return rewardFunc

  rewardSet = []
  if rockType == 'corner':
    rewardCandNum = 3
    rocks = [(0, height - 2), (width - 2, 0), (width - 2, height - 2)]
    for candId in xrange(rewardCandNum):
      rewardSet.append(rewardGen([rocks[candId]], 1))
  elif rockType == 'default':
    rewardCandNum = 5
    rocks = [(random.randint(0, width - 1), random.randint(0, height - 1)) for _ in xrange(10)]
    for candId in xrange(rewardCandNum):
      rewardSet.append(rewardGen(random.sample(rocks, 3), 1))
  else:
    raise Exception('Unknown rock type')

  initialPhi = [1.0 / rewardCandNum] * rewardCandNum

  terminalReward = util.Counter()

  experiment(Domain, width, height, responseTime, horizon, rewardCandNum, rewardSet, initialPhi, terminalReward)
